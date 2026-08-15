#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <optional>
#include <random>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
#include <tuple>
#include <vector>

namespace {

constexpr int kSize = 70;
constexpr int kHalf = 35;
constexpr int kBound = 4;
constexpr uint64_t kExpectedTaskCount = 730810;
constexpr std::array<int, 34> kLagPriority = {
    4,  5, 9,  17, 23, 1,  3,  19, 11, 14, 15, 13, 8,  10, 29, 7,  18,
    16, 2, 22, 20, 25, 12, 32, 6,  33, 24, 26, 34, 27, 30, 21, 31, 28,
};

struct alignas(8) Node {
  uint64_t lo = 1;
  uint64_t hi = 0;
  int8_t relation = 0;
  uint8_t padding[7]{};
};
static_assert(sizeof(Node) == 24);

struct alignas(8) BoundGPU {
  uint64_t fixed_lo = 0;
  uint64_t fixed_hi = 0;
  uint64_t group0_lo = 0;
  uint64_t group0_hi = 0;
  uint64_t group1_lo = 0;
  uint64_t group1_hi = 0;
  int16_t equal_lo = 0;
  int16_t equal_hi = 0;
  uint8_t fixed_count = 0;
  uint8_t free_edges = 0;
  uint8_t group_count = 0;
  uint8_t group0_length = 0;
  uint8_t group1_length = 0;
  uint8_t padding[3]{};
};
static_assert(sizeof(BoundGPU) == 64);

struct StepCounters {
  uint32_t output_count = 0;
  uint32_t nodes = 0;
  uint32_t cheap_prunes = 0;
  uint32_t exact_checks = 0;
  uint32_t exact_prunes = 0;
  uint32_t leaves = 0;
  uint32_t central_rejects = 0;
  uint32_t valid_leaves = 0;
};
static_assert(sizeof(StepCounters) == 32);

struct Totals {
  uint64_t nodes = 0;
  uint64_t leaves = 0;
  uint64_t central_rejects = 0;
  uint64_t valid_leaves = 0;
  uint64_t cheap_prunes = 0;
  uint64_t exact_checks = 0;
  uint64_t exact_prunes = 0;
};

struct State {
  uint64_t left = 1;
  uint64_t right = 1;
  uint8_t depth = 1;
  int8_t relation = 0;
};

uint64_t Mask64(int width) {
  if (width <= 0)
    return 0;
  if (width >= 64)
    return ~uint64_t{0};
  return (uint64_t{1} << width) - 1;
}

int Bit(const Node &node, int position) {
  if (position < 64)
    return static_cast<int>((node.lo >> position) & 1U);
  return static_cast<int>((node.hi >> (position - 64)) & 1U);
}

void SetBit(Node &node, int position, int value) {
  if (!value)
    return;
  if (position < 64)
    node.lo |= uint64_t{1} << position;
  else
    node.hi |= uint64_t{1} << (position - 64);
}

Node ToNode(const State &state) {
  Node node;
  node.lo = state.left;
  node.hi = 0;
  for (int offset = 0; offset < state.depth; ++offset) {
    const int position = kSize - state.depth + offset;
    SetBit(node, position, static_cast<int>((state.right >> offset) & 1U));
  }
  node.relation = state.relation;
  return node;
}

std::optional<State> ExtendState(const State &state, int left_bit,
                                 int right_bit) {
  State child = state;
  if (child.relation == 0 && left_bit != right_bit) {
    if (left_bit > right_bit)
      return std::nullopt;
    child.relation = -1;
  }
  child.left |= static_cast<uint64_t>(left_bit) << child.depth;
  child.right = (child.right << 1) | static_cast<uint64_t>(right_bit);
  ++child.depth;
  const int mismatches =
      __builtin_popcountll((child.left ^ child.right) & Mask64(child.depth));
  if (std::abs(static_cast<int>(child.depth) - 2 * mismatches) > kBound) {
    return std::nullopt;
  }
  return child;
}

std::optional<Node> ExtendNode(const Node &parent, int depth, int choice) {
  const int left_bit = choice >> 1;
  const int right_bit = choice & 1;
  Node child = parent;
  if (child.relation == 0 && left_bit != right_bit) {
    if (left_bit > right_bit)
      return std::nullopt;
    child.relation = -1;
  }
  SetBit(child, depth, left_bit);
  SetBit(child, kSize - 1 - depth, right_bit);
  const int child_depth = depth + 1;
  int mismatches = 0;
  const int lag = kSize - child_depth;
  for (int position = 0; position < child_depth; ++position) {
    mismatches += Bit(child, position) != Bit(child, position + lag);
  }
  if (std::abs(child_depth - 2 * mismatches) > kBound)
    return std::nullopt;
  return child;
}

std::array<std::array<BoundGPU, kSize>, kHalf + 1> BuildTemplates() {
  std::array<std::array<BoundGPU, kSize>, kHalf + 1> result{};
  for (int depth = 1; depth <= kHalf; ++depth) {
    std::array<uint8_t, kSize> assigned{};
    for (int position = 0; position < kSize; ++position) {
      assigned[position] = position < depth || position >= kSize - depth;
    }
    for (int lag = 1; lag < kSize; ++lag) {
      BoundGPU &entry = result[depth][lag];
      int constrained_edges = 0;
      for (int position = 0; position + lag < kSize; ++position) {
        if (assigned[position] && assigned[position + lag]) {
          ++entry.fixed_count;
          if (position < 64)
            entry.fixed_lo |= uint64_t{1} << position;
          else
            entry.fixed_hi |= uint64_t{1} << (position - 64);
        }
      }
      struct Group {
        int length = 0;
        uint64_t lo = 0;
        uint64_t hi = 0;
      };
      std::array<Group, 2> groups{};
      int group_count = 0;
      for (int residue = 0; residue < lag; ++residue) {
        int previous_fixed = -1;
        bool saw_unassigned = false;
        for (int position = residue; position < kSize; position += lag) {
          if (!assigned[position]) {
            saw_unassigned = true;
            continue;
          }
          if (saw_unassigned && previous_fixed >= 0) {
            const int length = (position - previous_fixed) / lag;
            entry.equal_lo +=
                static_cast<int16_t>((length % 2 == 0) ? -length : -length + 2);
            entry.equal_hi += static_cast<int16_t>(length);
            int group = -1;
            for (int index = 0; index < group_count; ++index) {
              if (groups[index].length == length)
                group = index;
            }
            if (group < 0) {
              if (group_count == 2)
                throw std::runtime_error("third gap group");
              group = group_count++;
              groups[group].length = length;
            }
            if (previous_fixed < 64) {
              groups[group].lo |= uint64_t{1} << previous_fixed;
            } else {
              groups[group].hi |= uint64_t{1} << (previous_fixed - 64);
            }
            constrained_edges += length;
          }
          previous_fixed = position;
          saw_unassigned = false;
        }
      }
      entry.group_count = static_cast<uint8_t>(group_count);
      if (group_count > 0) {
        entry.group0_length = static_cast<uint8_t>(groups[0].length);
        entry.group0_lo = groups[0].lo;
        entry.group0_hi = groups[0].hi;
      }
      if (group_count > 1) {
        entry.group1_length = static_cast<uint8_t>(groups[1].length);
        entry.group1_lo = groups[1].lo;
        entry.group1_hi = groups[1].hi;
      }
      const int remaining = (kSize - lag) - entry.fixed_count;
      const int free_edges = remaining - constrained_edges;
      if (free_edges < 0 || free_edges >= kSize) {
        throw std::runtime_error("invalid free-edge count");
      }
      entry.free_edges = static_cast<uint8_t>(free_edges);
    }
  }
  return result;
}

const auto kTemplates = BuildTemplates();

void AssertTemplateCoverage() {
  std::array<bool, kSize> present{};
  for (int lag : kLagPriority) {
    if (lag <= 0 || lag >= kSize || present[lag])
      throw std::runtime_error("invalid or duplicate active-lag priority");
    present[lag] = true;
  }
  for (int depth = 25; depth <= kHalf - 1; ++depth) {
    for (int lag = 1; lag < kSize; ++lag) {
      if (kTemplates[depth][lag].group_count != 0 && !present[lag])
        throw std::runtime_error("active bound missing from lag priority");
    }
  }
}

std::string ErrorText(NSError *error, std::string_view fallback) {
  if (!error)
    return std::string(fallback);
  NSString *description = [error localizedDescription];
  if (!description)
    return std::string(fallback);
  const char *text = [description UTF8String];
  return text ? std::string(text) : std::string(fallback);
}

int FixedCorrelation(const Node &node, const BoundGPU &entry, int lag) {
  int mismatches = 0;
  for (int position = 0; position + lag < kSize; ++position) {
    const bool selected = position < 64
                              ? ((entry.fixed_lo >> position) & 1U)
                              : ((entry.fixed_hi >> (position - 64)) & 1U);
    if (selected)
      mismatches += Bit(node, position) != Bit(node, position + lag);
  }
  return static_cast<int>(entry.fixed_count) - 2 * mismatches;
}

bool Intersects(int lo, int hi, int step) {
  int first = std::max(lo, -kBound);
  int residue = (first - lo) % step;
  if (residue < 0)
    residue += step;
  if (residue != 0)
    first += step - residue;
  return first <= std::min(hi, kBound);
}

bool SlowBoundFeasible(const Node &node, int depth, int lag) {
  int constrained_lo = 0;
  int constrained_hi = 0;
  int free_edges = 0;
  for (int residue = 0; residue < lag; ++residue) {
    int path_length = 0;
    std::array<int, kSize> fixed_offsets{};
    int fixed_count = 0;
    for (int position = residue; position < kSize; position += lag) {
      if (position < depth || position >= kSize - depth) {
        fixed_offsets[fixed_count++] = path_length;
      }
      ++path_length;
    }
    const int edge_count = path_length - 1;
    if (edge_count <= 0)
      continue;
    if (fixed_count < 2) {
      free_edges += edge_count;
      continue;
    }
    free_edges +=
        fixed_offsets[0] + edge_count - fixed_offsets[fixed_count - 1];
    for (int fixed = 0; fixed + 1 < fixed_count; ++fixed) {
      const int first_offset = fixed_offsets[fixed];
      const int second_offset = fixed_offsets[fixed + 1];
      const int length = second_offset - first_offset;
      const int first_position = residue + first_offset * lag;
      const int second_position = residue + second_offset * lag;
      const bool equal =
          Bit(node, first_position) == Bit(node, second_position);
      if (equal) {
        constrained_lo += (length % 2 == 0) ? -length : -length + 2;
        constrained_hi += length;
      } else {
        constrained_lo += (length % 2 == 1) ? -length : -length + 2;
        constrained_hi += length - 2;
      }
    }
  }
  if (free_edges > 0) {
    return Intersects(constrained_lo - free_edges, constrained_hi + free_edges,
                      2);
  }
  return Intersects(constrained_lo, constrained_hi, 4);
}

bool CompleteValid(const Node &node) {
  for (int lag = 1; lag < kSize; ++lag) {
    int correlation = 0;
    for (int position = 0; position + lag < kSize; ++position) {
      correlation += Bit(node, position) == Bit(node, position + lag) ? 1 : -1;
    }
    if (std::abs(correlation) > kBound)
      return false;
  }
  return true;
}

struct ExpandResult {
  std::vector<Node> children;
  StepCounters counters;
};

ExpandResult CpuExpandSlow(const std::vector<Node> &parents, int depth) {
  ExpandResult result;
  for (const Node &parent : parents) {
    for (int choice = 0; choice < 4; ++choice) {
      const auto child = ExtendNode(parent, depth, choice);
      if (!child)
        continue;
      const int child_depth = depth + 1;
      if (child_depth == kHalf) {
        ++result.counters.nodes;
        ++result.counters.leaves;
        if (CompleteValid(*child)) {
          ++result.counters.valid_leaves;
          result.children.push_back(*child);
        } else {
          ++result.counters.central_rejects;
        }
        continue;
      }
      bool cheap = true;
      for (int lag = kSize - child_depth - 1; lag >= 1; --lag) {
        const BoundGPU &entry = kTemplates[child_depth][lag];
        const int remaining = (kSize - lag) - entry.fixed_count;
        if (entry.fixed_count > kBound + remaining &&
            std::abs(FixedCorrelation(*child, entry, lag)) >
                kBound + remaining) {
          cheap = false;
          break;
        }
      }
      if (!cheap) {
        ++result.counters.cheap_prunes;
        continue;
      }
      ++result.counters.exact_checks;
      bool exact = true;
      for (int lag = 1; lag < kSize; ++lag) {
        if (!SlowBoundFeasible(*child, child_depth, lag)) {
          exact = false;
          break;
        }
      }
      if (!exact) {
        ++result.counters.exact_prunes;
        continue;
      }
      ++result.counters.nodes;
      result.children.push_back(*child);
    }
  }
  result.counters.output_count = static_cast<uint32_t>(result.children.size());
  return result;
}

std::string Bits(const Node &node) {
  std::string result;
  result.reserve(kSize);
  for (int index = 0; index < kSize; ++index) {
    result.push_back(Bit(node, index) ? '1' : '0');
  }
  return result;
}

std::string Transform(std::string_view bits, bool reverse, bool alternate,
                      bool negate) {
  std::string result;
  result.reserve(kSize);
  for (int index = 0; index < kSize; ++index) {
    const int source = reverse ? kSize - 1 - index : index;
    int value = bits[source] == '1';
    if (alternate && (index & 1))
      value ^= 1;
    if (negate)
      value ^= 1;
    result.push_back(value ? '1' : '0');
  }
  return result;
}

std::string Canonical(const Node &node) {
  const std::string bits = Bits(node);
  std::string best(kSize, '2');
  for (bool reverse : {false, true})
    for (bool alternate : {false, true})
      for (bool negate : {false, true})
        best = std::min(best, Transform(bits, reverse, alternate, negate));
  return best;
}

void MakeTasks(const State &state, int split_depth, std::vector<State> &tasks) {
  if (state.depth == split_depth) {
    tasks.push_back(state);
    return;
  }
  for (int left = 0; left < 2; ++left)
    for (int right = 0; right < 2; ++right)
      if (const auto child = ExtendState(state, left, right))
        MakeTasks(*child, split_depth, tasks);
}

int BorderDistance(const State &state, const std::string &bits) {
  int distance = 0;
  for (int index = 0; index < state.depth; ++index) {
    distance +=
        static_cast<int>((state.left >> index) & 1U) != bits[index] - '0';
    const int position = kSize - state.depth + index;
    distance +=
        static_cast<int>((state.right >> index) & 1U) != bits[position] - '0';
  }
  return distance;
}

std::vector<Node> BuildFrontier(const State &task, int target_depth,
                                uint64_t &nodes) {
  std::vector<State> current{task};
  nodes = 1;
  for (int depth = task.depth; depth < target_depth; ++depth) {
    std::vector<State> next;
    next.reserve(current.size() * 3);
    for (const State &state : current)
      for (int left = 0; left < 2; ++left)
        for (int right = 0; right < 2; ++right)
          if (const auto child = ExtendState(state, left, right))
            next.push_back(*child);
    nodes += next.size();
    current.swap(next);
  }
  std::vector<Node> result;
  result.reserve(current.size());
  for (const State &state : current)
    result.push_back(ToNode(state));
  return result;
}

const char *kMetalSource = R"METAL(
#include <metal_stdlib>
using namespace metal;

constant int N = 70;
constant int HALF = 35;
constant int BOUND = 4;
constant uchar priority_lags[34] = {
  4,5,9,17,23,1,3,19,11,14,15,13,8,10,29,7,18,16,2,22,20,25,12,32,
  6,33,24,26,34,27,30,21,31,28
};

struct Node { ulong lo; ulong hi; char relation; uchar padding[7]; };
struct BoundGPU {
  ulong fixed_lo; ulong fixed_hi; ulong group0_lo; ulong group0_hi;
  ulong group1_lo; ulong group1_hi; short equal_lo; short equal_hi;
  uchar fixed_count; uchar free_edges; uchar group_count;
  uchar group0_length; uchar group1_length; uchar padding[3];
};
struct StepCounters {
  atomic_uint output_count; atomic_uint nodes; atomic_uint cheap_prunes;
  atomic_uint exact_checks; atomic_uint exact_prunes; atomic_uint leaves;
  atomic_uint central_rejects; atomic_uint valid_leaves;
};

inline uint pc64(ulong value) {
  return popcount(uint(value)) + popcount(uint(value >> 32));
}
inline uint bit_at(Node node, uint position) {
  return position < 64 ? uint((node.lo >> position) & 1ul)
                       : uint((node.hi >> (position - 64)) & 1ul);
}
inline void set_bit(thread Node& node, uint position, uint value) {
  if (!value) return;
  if (position < 64) node.lo |= 1ul << position;
  else node.hi |= 1ul << (position - 64);
}
inline ulong mask64(uint width) {
  return width == 0 ? 0ul : (width >= 64 ? ~0ul : ((1ul << width) - 1ul));
}
inline void shift_right(ulong lo, ulong hi, uint shift,
                        thread ulong& out_lo, thread ulong& out_hi) {
  if (shift == 0) { out_lo = lo; out_hi = hi; }
  else if (shift < 64) {
    out_lo = (lo >> shift) | (hi << (64 - shift));
    out_hi = hi >> shift;
  } else { out_lo = hi >> (shift - 64); out_hi = 0; }
}
inline uint masked_mismatches(Node node, ulong mask_lo, ulong mask_hi,
                              uint distance) {
  ulong shifted_lo, shifted_hi;
  shift_right(node.lo, node.hi, distance, shifted_lo, shifted_hi);
  return pc64((node.lo ^ shifted_lo) & mask_lo) +
         pc64((node.hi ^ shifted_hi) & mask_hi);
}
inline int fixed_correlation(Node node, constant BoundGPU& entry, uint lag) {
  return int(entry.fixed_count) -
         2 * int(masked_mismatches(node, entry.fixed_lo, entry.fixed_hi, lag));
}
inline bool intersects(int lo, int hi, int step) {
  int first = max(lo, -BOUND);
  int residue = (first - lo) % step;
  if (residue < 0) residue += step;
  if (residue != 0) first += step - residue;
  return first <= min(hi, BOUND);
}
inline bool bound_feasible(Node node, constant BoundGPU& entry, uint lag) {
  int lo = fixed_correlation(node, entry, lag) + int(entry.equal_lo);
  int hi = fixed_correlation(node, entry, lag) + int(entry.equal_hi);
  if (entry.group_count > 0) {
    uint mismatches = masked_mismatches(
        node, entry.group0_lo, entry.group0_hi, lag * entry.group0_length);
    lo += (entry.group0_length % 2 == 0 ? 2 : -2) * int(mismatches);
    hi -= 2 * int(mismatches);
  }
  if (entry.group_count > 1) {
    uint mismatches = masked_mismatches(
        node, entry.group1_lo, entry.group1_hi, lag * entry.group1_length);
    lo += (entry.group1_length % 2 == 0 ? 2 : -2) * int(mismatches);
    hi -= 2 * int(mismatches);
  }
  if (entry.free_edges > 0)
    return intersects(lo - entry.free_edges, hi + entry.free_edges, 2);
  return intersects(lo, hi, 4);
}
inline bool complete_valid(Node node) {
  for (uint lag = 1; lag < N; ++lag) {
    uint overlap = N - lag;
    ulong mask_lo = overlap >= 64 ? ~0ul : mask64(overlap);
    ulong mask_hi = overlap <= 64 ? 0ul : mask64(overlap - 64);
    int corr = int(overlap) -
      2 * int(masked_mismatches(node, mask_lo, mask_hi, lag));
    if (abs(corr) > BOUND) return false;
  }
  return true;
}

kernel void expand_level(const device Node* parents [[buffer(0)]],
                         device Node* output [[buffer(1)]],
                         constant BoundGPU* templates [[buffer(2)]],
                         device StepCounters* counters [[buffer(3)]],
                         constant uint& parent_count [[buffer(4)]],
                         constant uint& depth [[buffer(5)]],
                         uint tid [[thread_position_in_grid]]) {
  uint total = parent_count * 4;
  if (tid >= total) return;
  Node child = parents[tid >> 2];
  uint choice = tid & 3;
  uint left_bit = choice >> 1;
  uint right_bit = choice & 1;
  if (child.relation == 0 && left_bit != right_bit) {
    if (left_bit > right_bit) return;
    child.relation = -1;
  }
  set_bit(child, depth, left_bit);
  set_bit(child, N - 1 - depth, right_bit);
  uint child_depth = depth + 1;
  uint outer_lag = N - child_depth;
  ulong outer_mask = mask64(child_depth);
  int outer_corr = int(child_depth) -
    2 * int(masked_mismatches(child, outer_mask, 0, outer_lag));
  if (abs(outer_corr) > BOUND) return;

  if (child_depth == HALF) {
    atomic_fetch_add_explicit(&counters->nodes, 1, memory_order_relaxed);
    atomic_fetch_add_explicit(&counters->leaves, 1, memory_order_relaxed);
    if (!complete_valid(child)) {
      atomic_fetch_add_explicit(&counters->central_rejects, 1,
                                memory_order_relaxed);
      return;
    }
    atomic_fetch_add_explicit(&counters->valid_leaves, 1, memory_order_relaxed);
    uint slot = atomic_fetch_add_explicit(&counters->output_count, 1,
                                          memory_order_relaxed);
    output[slot] = child;
    return;
  }

  for (int lag = N - int(child_depth) - 1; lag >= 1; --lag) {
    constant BoundGPU& entry = templates[child_depth * N + lag];
    int remaining = (N - lag) - int(entry.fixed_count);
    if (int(entry.fixed_count) > BOUND + remaining &&
        abs(fixed_correlation(child, entry, lag)) > BOUND + remaining) {
      atomic_fetch_add_explicit(&counters->cheap_prunes, 1,
                                memory_order_relaxed);
      return;
    }
  }
  atomic_fetch_add_explicit(&counters->exact_checks, 1, memory_order_relaxed);
  for (uint index = 0; index < 34; ++index) {
    uint lag = priority_lags[index];
    constant BoundGPU& entry = templates[child_depth * N + lag];
    if (entry.group_count != 0 && !bound_feasible(child, entry, lag)) {
      atomic_fetch_add_explicit(&counters->exact_prunes, 1,
                                memory_order_relaxed);
      return;
    }
  }
  atomic_fetch_add_explicit(&counters->nodes, 1, memory_order_relaxed);
  uint slot = atomic_fetch_add_explicit(&counters->output_count, 1,
                                        memory_order_relaxed);
  output[slot] = child;
}
)METAL";

class MetalEngine {
public:
  MetalEngine() {
    const auto begin = std::chrono::steady_clock::now();
    AssertTemplateCoverage();
    device_ = MTLCreateSystemDefaultDevice();
    if (!device_)
      throw std::runtime_error("Metal device unavailable");
    NSError *error = nil;
    NSString *source = [NSString stringWithUTF8String:kMetalSource];
    if (!source)
      throw std::runtime_error("Metal source string allocation failed");
    id<MTLLibrary> library = [device_ newLibraryWithSource:source
                                                   options:nil
                                                     error:&error];
    if (!library) {
      throw std::runtime_error(
          ErrorText(error, "Metal library compilation failed"));
    }
    id<MTLFunction> function = [library newFunctionWithName:@"expand_level"];
    if (!function)
      throw std::runtime_error("Metal kernel function unavailable");
    pipeline_ = [device_ newComputePipelineStateWithFunction:function
                                                       error:&error];
    if (!pipeline_) {
      throw std::runtime_error(
          ErrorText(error, "Metal pipeline creation failed"));
    }
    queue_ = [device_ newCommandQueue];
    templates_ = [device_ newBufferWithBytes:kTemplates.data()
                                      length:sizeof(kTemplates)
                                     options:MTLResourceStorageModeShared];
    if (!queue_ || !templates_)
      throw std::runtime_error("Metal queue/template allocation failed");
    compile_seconds_ =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - begin)
            .count();
  }

  double compile_seconds() const { return compile_seconds_; }
  std::string device_name() const {
    NSString *name = [device_ name];
    const char *text = name ? [name UTF8String] : nullptr;
    return text ? std::string(text) : std::string("unknown Metal device");
  }
  uint64_t max_buffer_length() const { return device_.maxBufferLength; }
  bool has_unified_memory() const { return device_.hasUnifiedMemory; }
  uint64_t thread_execution_width() const {
    return pipeline_.threadExecutionWidth;
  }

  ExpandResult Expand(const std::vector<Node> &parents, int depth,
                      double &kernel_seconds) {
    if (parents.empty())
      return {};
    ExpandResult result;
    // commandBuffer/computeCommandEncoder are autoreleased.  A shard can run
    // hundreds of levels, so drain them (and their resource references) after
    // each completed dispatch instead of retaining them until process exit.
    @autoreleasepool {
      if (parents.size() > UINT32_MAX / 4)
        throw std::runtime_error(
            "frontier exceeds 32-bit atomic output capacity");
      const size_t output_capacity = parents.size() * 4;
      const size_t input_bytes = parents.size() * sizeof(Node);
      const size_t output_bytes = output_capacity * sizeof(Node);
      if (input_bytes > device_.maxBufferLength ||
          output_bytes > device_.maxBufferLength)
        throw std::runtime_error(
            "frontier exceeds Metal maximum buffer length");
      id<MTLBuffer> input =
          [device_ newBufferWithBytes:parents.data()
                               length:input_bytes
                              options:MTLResourceStorageModeShared];
      id<MTLBuffer> output =
          [device_ newBufferWithLength:output_bytes
                               options:MTLResourceStorageModeShared];
      id<MTLBuffer> counters =
          [device_ newBufferWithLength:sizeof(StepCounters)
                               options:MTLResourceStorageModeShared];
      if (!input || !output || !counters)
        throw std::runtime_error("Metal frontier allocation failed");
      std::memset([counters contents], 0, sizeof(StepCounters));
      uint32_t parent_count = static_cast<uint32_t>(parents.size());
      uint32_t depth_value = static_cast<uint32_t>(depth);
      const auto begin = std::chrono::steady_clock::now();
      id<MTLCommandBuffer> command = [queue_ commandBuffer];
      id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
      if (!command || !encoder)
        throw std::runtime_error("Metal command allocation failed");
      [encoder setComputePipelineState:pipeline_];
      [encoder setBuffer:input offset:0 atIndex:0];
      [encoder setBuffer:output offset:0 atIndex:1];
      [encoder setBuffer:templates_ offset:0 atIndex:2];
      [encoder setBuffer:counters offset:0 atIndex:3];
      [encoder setBytes:&parent_count length:sizeof(parent_count) atIndex:4];
      [encoder setBytes:&depth_value length:sizeof(depth_value) atIndex:5];
      const NSUInteger threads = parents.size() * 4;
      const NSUInteger width =
          std::min<NSUInteger>(256, pipeline_.maxTotalThreadsPerThreadgroup);
      [encoder dispatchThreads:MTLSizeMake(threads, 1, 1)
          threadsPerThreadgroup:MTLSizeMake(width, 1, 1)];
      [encoder endEncoding];
      [command commit];
      [command waitUntilCompleted];
      kernel_seconds += std::chrono::duration<double>(
                            std::chrono::steady_clock::now() - begin)
                            .count();
      if (command.status == MTLCommandBufferStatusError) {
        throw std::runtime_error(
            ErrorText(command.error, "Metal command execution failed"));
      }
      result.counters = *static_cast<StepCounters *>([counters contents]);
      if (result.counters.output_count > output_capacity) {
        throw std::runtime_error("GPU output counter exceeded capacity");
      }
      if (depth + 1 == kHalf) {
        if (result.counters.nodes != result.counters.leaves ||
            result.counters.leaves != result.counters.central_rejects +
                                          result.counters.valid_leaves ||
            result.counters.output_count != result.counters.valid_leaves)
          throw std::runtime_error("GPU leaf counter invariant failed");
      } else if (result.counters.output_count != result.counters.nodes ||
                 result.counters.leaves != 0 ||
                 result.counters.central_rejects != 0 ||
                 result.counters.valid_leaves != 0) {
        throw std::runtime_error("GPU nonleaf counter invariant failed");
      }
      const Node *values = static_cast<const Node *>([output contents]);
      result.children.assign(values, values + result.counters.output_count);
    }
    return result;
  }

private:
  id<MTLDevice> device_;
  id<MTLComputePipelineState> pipeline_;
  id<MTLCommandQueue> queue_;
  id<MTLBuffer> templates_;
  double compile_seconds_ = 0;
};

bool SameNodes(std::vector<Node> first, std::vector<Node> second) {
  auto key = [](const Node &node) {
    return std::tuple(node.lo, node.hi, node.relation);
  };
  std::sort(first.begin(), first.end(),
            [&](const Node &a, const Node &b) { return key(a) < key(b); });
  std::sort(second.begin(), second.end(),
            [&](const Node &a, const Node &b) { return key(a) < key(b); });
  if (first.size() != second.size())
    return false;
  for (size_t index = 0; index < first.size(); ++index) {
    if (key(first[index]) != key(second[index]))
      return false;
  }
  return true;
}

void AssertCounters(const StepCounters &expected,
                    const StepCounters &observed) {
  if (expected.output_count != observed.output_count ||
      expected.nodes != observed.nodes ||
      expected.cheap_prunes != observed.cheap_prunes ||
      expected.exact_checks != observed.exact_checks ||
      expected.exact_prunes != observed.exact_prunes ||
      expected.leaves != observed.leaves ||
      expected.central_rejects != observed.central_rejects ||
      expected.valid_leaves != observed.valid_leaves) {
    throw std::runtime_error("CPU/Metal step counter mismatch");
  }
}

Node RandomPath(std::mt19937_64 &rng, int depth) {
  State state;
  while (state.depth < depth) {
    const int start = static_cast<int>(rng() & 3U);
    bool found = false;
    for (int offset = 0; offset < 4; ++offset) {
      const int choice = (start + offset) & 3;
      if (const auto child = ExtendState(state, choice >> 1, choice & 1)) {
        state = *child;
        found = true;
        break;
      }
    }
    if (!found)
      return RandomPath(rng, depth);
  }
  return ToNode(state);
}

void SelfTest(MetalEngine &engine) {
  std::mt19937_64 rng(0x12124930ULL);
  double kernel_seconds = 0;
  for (int depth = 24; depth < kHalf; ++depth) {
    std::vector<Node> parents;
    for (int trial = 0; trial < 128; ++trial)
      parents.push_back(RandomPath(rng, depth));
    const ExpandResult cpu = CpuExpandSlow(parents, depth);
    const ExpandResult gpu = engine.Expand(parents, depth, kernel_seconds);
    AssertCounters(cpu.counters, gpu.counters);
    if (!SameNodes(cpu.children, gpu.children)) {
      throw std::runtime_error("CPU/Metal random-cube child mismatch");
    }
  }
  const std::array<std::string_view, 3> fixtures = {
      "1001011001011001010100110011001100001010110101000000000010111100011111",
      "1010110101101010101110011001110110010111100111100110110110000000001111",
      "1000000101010100010010000011011011110011100011010010001100110111101001",
  };
  for (std::string_view bits : fixtures) {
    Node node{};
    node.lo = 0;
    node.hi = 0;
    for (int position = 0; position < kSize; ++position)
      SetBit(node, position, bits[position] == '1');
    if (!CompleteValid(node))
      throw std::runtime_error("invalid public fixture");
    std::vector<Node> parent{node};
    // At depth 34 clear the two central fixture bits, then require that the
    // exact fixture appears among Metal's valid depth-35 completions.
    const int left = 34;
    const int right = 35;
    parent[0].lo &= ~(uint64_t{1} << left);
    parent[0].lo &= ~(uint64_t{1} << right);
    parent[0].relation = -1;
    const ExpandResult gpu = engine.Expand(parent, 34, kernel_seconds);
    if (std::none_of(gpu.children.begin(), gpu.children.end(),
                     [&](const Node &child) { return Bits(child) == bits; })) {
      throw std::runtime_error("Metal rejected a public PSL-4 fixture");
    }
  }
  std::cerr << "SELFTEST random_parents=" << 128 * (kHalf - 24)
            << " fixtures=3 kernel_seconds=" << kernel_seconds << "\n";
}

struct RunResult {
  Totals totals;
  std::set<std::string> answers;
  std::vector<uint64_t> frontier_sizes;
  double compile_seconds = 0;
  double task_seconds = 0;
  double frontier_seconds = 0;
  double metal_seconds = 0;
  double total_seconds = 0;
  uint64_t task_index = 0;
  uint64_t peak_frontier = 0;
  uint64_t peak_dispatch_children = 0;
  uint64_t metal_dispatches = 0;
};

uint64_t SplitMix64(uint64_t value) {
  value += 0x9e3779b97f4a7c15ULL;
  value = (value ^ (value >> 30U)) * 0xbf58476d1ce4e5b9ULL;
  value = (value ^ (value >> 27U)) * 0x94d049bb133111ebULL;
  return value ^ (value >> 31U);
}

RunResult RunTask(MetalEngine &engine, const State &task, uint64_t task_index,
                  int switch_depth) {
  const auto total_begin = std::chrono::steady_clock::now();
  const auto frontier_begin = std::chrono::steady_clock::now();
  uint64_t pre_nodes = 0;
  std::vector<Node> frontier = BuildFrontier(task, switch_depth, pre_nodes);
  const double frontier_seconds =
      std::chrono::duration<double>(std::chrono::steady_clock::now() -
                                    frontier_begin)
          .count();

  RunResult result;
  result.frontier_seconds = frontier_seconds;
  result.task_index = task_index;
  result.totals.nodes = pre_nodes;
  result.frontier_sizes.push_back(frontier.size());
  result.peak_frontier = frontier.size();
  for (int depth = switch_depth; depth < kHalf; ++depth) {
    result.peak_dispatch_children =
        std::max<uint64_t>(result.peak_dispatch_children, frontier.size() * 4);
    if (!frontier.empty())
      ++result.metal_dispatches;
    ExpandResult step = engine.Expand(frontier, depth, result.metal_seconds);
    result.totals.nodes += step.counters.nodes;
    result.totals.leaves += step.counters.leaves;
    result.totals.central_rejects += step.counters.central_rejects;
    result.totals.valid_leaves += step.counters.valid_leaves;
    result.totals.cheap_prunes += step.counters.cheap_prunes;
    result.totals.exact_checks += step.counters.exact_checks;
    result.totals.exact_prunes += step.counters.exact_prunes;
    frontier.swap(step.children);
    result.frontier_sizes.push_back(frontier.size());
    result.peak_frontier =
        std::max<uint64_t>(result.peak_frontier, frontier.size());
  }
  for (const Node &node : frontier) {
    if (!CompleteValid(node))
      throw std::runtime_error("Metal leaf failed independent host replay");
    result.answers.insert(Canonical(node));
  }
  result.total_seconds = std::chrono::duration<double>(
                             std::chrono::steady_clock::now() - total_begin)
                             .count();
  return result;
}

struct BatchResult {
  std::vector<RunResult> tasks;
  double compile_seconds = 0;
  double task_generation_seconds = 0;
  double total_seconds = 0;
  uint64_t candidate_tasks = 0;
  uint64_t selected_before_limit = 0;
  uint64_t max_tasks = 0;
  uint64_t virtual_shards = 0;
  uint64_t virtual_shard = 0;
  bool truncated = false;
  std::string selection_mode;
};

BatchResult RunSelection(MetalEngine &engine, const std::string &near_bits,
                         int64_t explicit_task, uint64_t virtual_shards,
                         uint64_t virtual_shard, uint64_t max_tasks,
                         int switch_depth) {
  const auto total_begin = std::chrono::steady_clock::now();
  const auto generation_begin = std::chrono::steady_clock::now();
  std::vector<State> tasks;
  MakeTasks(State{}, 12, tasks);
  if (tasks.size() != kExpectedTaskCount)
    throw std::runtime_error("split-depth-12 task universe drifted");
  if (SplitMix64(1) != 0x910A2DEC89025CC1ULL)
    throw std::runtime_error("SplitMix64 shard mapping drifted");
  const double generation_seconds =
      std::chrono::duration<double>(std::chrono::steady_clock::now() -
                                    generation_begin)
          .count();
  std::vector<uint64_t> selected;
  if (explicit_task >= 0) {
    if (static_cast<uint64_t>(explicit_task) >= tasks.size())
      throw std::runtime_error("explicit task index out of range");
    selected.push_back(static_cast<uint64_t>(explicit_task));
  } else if (virtual_shards != 0) {
    for (uint64_t index = 0; index < tasks.size(); ++index) {
      if (SplitMix64(index) % virtual_shards == virtual_shard)
        selected.push_back(index);
    }
  } else {
    uint64_t best_index = 0;
    int best_distance = kSize + 1;
    for (uint64_t index = 0; index < tasks.size(); ++index) {
      const int distance = BorderDistance(tasks[index], near_bits);
      if (distance < best_distance) {
        best_distance = distance;
        best_index = index;
      }
    }
    selected.push_back(best_index);
  }
  BatchResult result;
  result.compile_seconds = engine.compile_seconds();
  result.task_generation_seconds = generation_seconds;
  result.candidate_tasks = tasks.size();
  result.selected_before_limit = selected.size();
  result.max_tasks = max_tasks;
  result.virtual_shards = virtual_shards;
  result.virtual_shard = virtual_shard;
  result.truncated = max_tasks != 0 && selected.size() > max_tasks;
  result.selection_mode =
      explicit_task >= 0
          ? "task-index"
          : (virtual_shards != 0 ? "virtual-shard" : "nearest-border");
  if (result.truncated)
    selected.resize(max_tasks);
  for (uint64_t index : selected)
    result.tasks.push_back(RunTask(engine, tasks[index], index, switch_depth));
  result.total_seconds = std::chrono::duration<double>(
                             std::chrono::steady_clock::now() - total_begin)
                             .count();
  return result;
}

void PrintBatchJson(const BatchResult &batch, const MetalEngine &engine) {
  Totals totals;
  std::set<std::string> answers;
  uint64_t peak_frontier = 0;
  uint64_t peak_dispatch_children = 0;
  uint64_t metal_dispatches = 0;
  double frontier_seconds = 0;
  double metal_seconds = 0;
  std::cout << "{\n  \"schema\": \"psl4-metal-bfs-batch-v1\",\n";
  std::cout << "  \"device\": \"" << engine.device_name() << "\",\n";
  std::cout << "  \"max_buffer_length\": " << engine.max_buffer_length()
            << ",\n";
  std::cout << "  \"has_unified_memory\": "
            << (engine.has_unified_memory() ? "true" : "false") << ",\n";
  std::cout << "  \"thread_execution_width\": "
            << engine.thread_execution_width() << ",\n";
  std::cout << "  \"compile_seconds\": " << batch.compile_seconds << ",\n";
  std::cout << "  \"task_generation_seconds\": "
            << batch.task_generation_seconds << ",\n";
  std::cout << "  \"selection_mode\": \"" << batch.selection_mode << "\",\n";
  std::cout << "  \"candidate_tasks\": " << batch.candidate_tasks << ",\n";
  std::cout << "  \"selected_before_limit\": " << batch.selected_before_limit
            << ",\n";
  std::cout << "  \"max_tasks\": " << batch.max_tasks << ",\n";
  std::cout << "  \"truncated\": " << (batch.truncated ? "true" : "false")
            << ",\n";
  std::cout << "  \"split_depth\": 12,\n";
  std::cout << "  \"strong_switch_depth\": 24,\n";
  std::cout << "  \"strong_exact_stride\": 1,\n";
  std::cout << "  \"virtual_shards\": " << batch.virtual_shards << ",\n";
  std::cout << "  \"virtual_shard\": " << batch.virtual_shard << ",\n";
  std::cout << "  \"tasks\": [\n";
  for (size_t index = 0; index < batch.tasks.size(); ++index) {
    const RunResult &task = batch.tasks[index];
    totals.nodes += task.totals.nodes;
    totals.leaves += task.totals.leaves;
    totals.central_rejects += task.totals.central_rejects;
    totals.valid_leaves += task.totals.valid_leaves;
    totals.cheap_prunes += task.totals.cheap_prunes;
    totals.exact_checks += task.totals.exact_checks;
    totals.exact_prunes += task.totals.exact_prunes;
    answers.insert(task.answers.begin(), task.answers.end());
    peak_frontier = std::max(peak_frontier, task.peak_frontier);
    peak_dispatch_children =
        std::max(peak_dispatch_children, task.peak_dispatch_children);
    metal_dispatches += task.metal_dispatches;
    frontier_seconds += task.frontier_seconds;
    metal_seconds += task.metal_seconds;
    std::cout << "    {\"task_index\": " << task.task_index
              << ", \"nodes\": " << task.totals.nodes
              << ", \"leaves\": " << task.totals.leaves
              << ", \"central_rejects\": " << task.totals.central_rejects
              << ", \"valid_leaves\": " << task.totals.valid_leaves
              << ", \"strong_cheap_prunes\": " << task.totals.cheap_prunes
              << ", \"exact_checks\": " << task.totals.exact_checks
              << ", \"exact_prunes\": " << task.totals.exact_prunes
              << ", \"frontier_seconds\": " << task.frontier_seconds
              << ", \"metal_seconds\": " << task.metal_seconds
              << ", \"metal_dispatches\": " << task.metal_dispatches
              << ", \"total_seconds\": " << task.total_seconds
              << ", \"peak_frontier\": " << task.peak_frontier
              << ", \"answers\": [";
    bool first_task_answer = true;
    for (const std::string &answer : task.answers) {
      if (!first_task_answer)
        std::cout << ", ";
      first_task_answer = false;
      std::cout << "\"" << answer << "\"";
    }
    std::cout << "]}";
    if (index + 1 != batch.tasks.size())
      std::cout << ',';
    std::cout << '\n';
  }
  std::cout << "  ],\n  \"aggregate\": {\n";
  std::cout << "    \"task_count\": " << batch.tasks.size() << ",\n";
  std::cout << "    \"nodes\": " << totals.nodes << ",\n";
  std::cout << "    \"leaves\": " << totals.leaves << ",\n";
  std::cout << "    \"central_rejects\": " << totals.central_rejects << ",\n";
  std::cout << "    \"valid_leaves\": " << totals.valid_leaves << ",\n";
  std::cout << "    \"strong_cheap_prunes\": " << totals.cheap_prunes << ",\n";
  std::cout << "    \"exact_checks\": " << totals.exact_checks << ",\n";
  std::cout << "    \"exact_prunes\": " << totals.exact_prunes << ",\n";
  std::cout << "    \"frontier_seconds\": " << frontier_seconds << ",\n";
  std::cout << "    \"metal_seconds\": " << metal_seconds << ",\n";
  std::cout << "    \"metal_dispatches\": " << metal_dispatches << ",\n";
  std::cout << "    \"peak_frontier\": " << peak_frontier << ",\n";
  std::cout << "    \"peak_dispatch_children\": " << peak_dispatch_children
            << ",\n";
  std::cout << "    \"total_seconds_excluding_compile\": "
            << batch.total_seconds << ",\n";
  std::cout << "    \"total_seconds_including_compile\": "
            << batch.total_seconds + batch.compile_seconds << ",\n";
  std::cout << "    \"classes\": " << answers.size() << "\n  },\n";
  std::cout << "  \"answers\": [";
  bool first = true;
  for (const std::string &answer : answers) {
    if (!first)
      std::cout << ", ";
    first = false;
    std::cout << "\"" << answer << "\"";
  }
  std::cout << "]\n}\n";
}

} // namespace

int main(int argc, char **argv) {
  @autoreleasepool {
    try {
      bool self_test = false;
      int switch_depth = 24;
      int64_t explicit_task = -1;
      uint64_t virtual_shards = 0;
      uint64_t virtual_shard = 0;
      uint64_t max_tasks = 0;
      std::string near_bits = "100101100101100101010011001100110000101011010100"
                              "0000000010111100011111";
      for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "--self-test")
          self_test = true;
        else if (argument == "--switch-depth" && index + 1 < argc)
          switch_depth = std::stoi(argv[++index]);
        else if (argument == "--near-bits" && index + 1 < argc)
          near_bits = argv[++index];
        else if (argument == "--task-index" && index + 1 < argc)
          explicit_task = std::stoll(argv[++index]);
        else if (argument == "--task-shards" && index + 1 < argc)
          virtual_shards = std::stoull(argv[++index]);
        else if (argument == "--task-shard" && index + 1 < argc)
          virtual_shard = std::stoull(argv[++index]);
        else if (argument == "--max-tasks" && index + 1 < argc)
          max_tasks = std::stoull(argv[++index]);
        else
          throw std::runtime_error("unknown or incomplete argument: " +
                                   argument);
      }
      if (switch_depth != 24)
        throw std::runtime_error(
            "switch depth must be exactly 24 for frozen-engine equivalence");
      if (near_bits.size() != kSize ||
          near_bits.find_first_not_of("01") != std::string::npos)
        throw std::runtime_error("near-bits must contain exactly 70 bits");
      if (virtual_shards == 0 && virtual_shard != 0)
        throw std::runtime_error("task-shard requires task-shards");
      if (virtual_shards != 0 && virtual_shard >= virtual_shards)
        throw std::runtime_error("task-shard is outside task-shards");
      if (explicit_task >= 0 && virtual_shards != 0)
        throw std::runtime_error(
            "task-index and task-shards are mutually exclusive");
      MetalEngine engine;
      if (self_test)
        SelfTest(engine);
      const BatchResult result =
          RunSelection(engine, near_bits, explicit_task, virtual_shards,
                       virtual_shard, max_tasks, switch_depth);
      PrintBatchJson(result, engine);
      return 0;
    } catch (const std::exception &error) {
      std::cerr << "error: " << error.what() << "\n";
      return 2;
    }
  }
}

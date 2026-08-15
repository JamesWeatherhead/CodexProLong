#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <mutex>
#include <optional>
#include <random>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <vector>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace {

constexpr int kSize = 70;
constexpr int kHalf = kSize / 2;
constexpr int kBound = 4;

struct State {
  // Left bit i is code position i. Right is the normal-order suffix: bit zero
  // is the current innermost assigned position and bit depth-1 is position 69.
  uint64_t left = 1;
  uint64_t right = 1;
  uint8_t depth = 1;
  // -1: left is already lexicographically smaller than reversed right.
  //  0: equal so far. +1 is rejected and never stored.
  int8_t reversal_relation = 0;
};

struct StrongState {
  std::array<int8_t, kSize> values{};
  std::array<uint8_t, kSize> assigned{};
  std::array<int16_t, kSize> correlation{};
  uint8_t depth = 0;
  int even_sum = 0;
  int odd_sum = 0;
  std::array<std::array<int8_t, 5>, 6> modulus_sum{};
};

struct StrongDelta {
  struct Change {
    uint8_t lag = 0;
    int8_t product = 0;
  };
  uint8_t position = 0;
  uint8_t count = 0;
  std::array<Change, kSize> changes{};
};

struct Edge {
  uint8_t left = 0;
  uint8_t right = 0;
};

struct Gap {
  uint8_t left = 0;
  uint8_t right = 0;
  uint8_t length = 0;
};

struct GapGroup {
  uint8_t length = 0;
  uint8_t count = 0;
  unsigned __int128 left_mask = 0;
};

struct BoundTemplate {
  uint8_t fixed_edge_count = 0;
  uint8_t gap_count = 0;
  uint8_t free_edges = 0;
  uint8_t gap_group_count = 0;
  int16_t equal_gap_lo = 0;
  int16_t equal_gap_hi = 0;
  std::array<Edge, kSize> fixed_edges{};
  std::array<Gap, kSize> gaps{};
  std::array<GapGroup, 2> gap_groups{};
};

struct AttainableRange {
  bool feasible = false;
  int first = 0;
  int last = 0;
};

struct Counters {
  uint64_t nodes = 0;
  uint64_t leaves = 0;
  uint64_t central_rejects = 0;
  uint64_t strong_cheap_prunes = 0;
  uint64_t exact_checks = 0;
  uint64_t exact_prunes = 0;
  bool truncated = false;
};

struct Options {
  int split_depth = 12;
  int threads = 0;
  uint64_t max_tasks = 0;
  uint64_t node_limit = 0;
  uint64_t task_shards = 1;
  uint64_t task_shard = 0;
  int exact_start_depth = 0;
  int exact_stride = 1;
  int moment_depth = 0;
  int strong_switch_depth = 0;
  int strong_exact_stride = 1;
  std::string near_bits;
  std::string journal;
  bool self_test = false;
};

uint64_t SplitMix64(uint64_t value) {
  value += 0x9e3779b97f4a7c15ULL;
  value = (value ^ (value >> 30U)) * 0xbf58476d1ce4e5b9ULL;
  value = (value ^ (value >> 27U)) * 0x94d049bb133111ebULL;
  return value ^ (value >> 31U);
}

std::mutex output_mutex;
std::mutex answer_mutex;
std::set<std::string> global_answers;
std::atomic<uint64_t> total_nodes{0};
std::atomic<uint64_t> total_leaves{0};
std::atomic<uint64_t> total_strong_cheap_prunes{0};
std::atomic<uint64_t> total_exact_checks{0};
std::atomic<uint64_t> total_exact_prunes{0};
std::atomic<uint64_t> tasks_finished{0};
int g_exact_start_depth = 0;
int g_exact_stride = 1;
int g_moment_depth = 0;
int g_strong_switch_depth = 0;
int g_strong_exact_stride = 1;

uint64_t Mask64(int width) {
  if (width == 64) {
    return ~uint64_t{0};
  }
  return (uint64_t{1} << width) - 1;
}

unsigned __int128 Mask128(int width) {
  if (width == 128) {
    return ~static_cast<unsigned __int128>(0);
  }
  return (static_cast<unsigned __int128>(1) << width) - 1;
}

int Popcount128(unsigned __int128 value) {
  return __builtin_popcountll(static_cast<uint64_t>(value)) +
         __builtin_popcountll(static_cast<uint64_t>(value >> 64));
}

int NewlyDeterminedCorrelation(uint64_t left, uint64_t right, int depth) {
  const int mismatches = __builtin_popcountll((left ^ right) & Mask64(depth));
  return depth - 2 * mismatches;
}

inline int ValueAt(const State& state, int position) {
  if (position < state.depth) {
    return ((state.left >> position) & 1U) != 0 ? 1 : -1;
  }
  const int right_start = kSize - state.depth;
  if (position >= right_start) {
    return ((state.right >> (position - right_start)) & 1U) != 0 ? 1 : -1;
  }
  throw std::runtime_error("requested an unassigned position");
}

inline unsigned __int128 PartialCode(const State& state) {
  return static_cast<unsigned __int128>(state.left) |
         (static_cast<unsigned __int128>(state.right)
          << (kSize - state.depth));
}

std::array<std::array<BoundTemplate, kSize>, kHalf + 1>
BuildBoundTemplates() {
  std::array<std::array<BoundTemplate, kSize>, kHalf + 1> templates{};
  for (int depth = 1; depth <= kHalf; ++depth) {
    std::array<uint8_t, kSize> assigned{};
    for (int position = 0; position < kSize; ++position) {
      assigned[position] = static_cast<uint8_t>(
          position < depth || position >= kSize - depth);
    }
    for (int lag = 1; lag < kSize; ++lag) {
      BoundTemplate& entry = templates[depth][lag];
      int determined_edges = 0;
      for (int position = 0; position + lag < kSize; ++position) {
        if (assigned[position] && assigned[position + lag]) {
          entry.fixed_edges[entry.fixed_edge_count++] = {
              static_cast<uint8_t>(position),
              static_cast<uint8_t>(position + lag)};
          ++determined_edges;
        }
      }

      int constrained_edges = 0;
      for (int residue = 0; residue < lag && residue < kSize; ++residue) {
        int previous_fixed = -1;
        bool saw_unassigned = false;
        for (int position = residue; position < kSize; position += lag) {
          if (!assigned[position]) {
            saw_unassigned = true;
            continue;
          }
          if (saw_unassigned && previous_fixed >= 0) {
            const int length = (position - previous_fixed) / lag;
            if (length < 2) {
              throw std::runtime_error("invalid constrained gap");
            }
            entry.gaps[entry.gap_count++] = {
                static_cast<uint8_t>(previous_fixed),
                static_cast<uint8_t>(position),
                static_cast<uint8_t>(length)};
            entry.equal_gap_lo +=
                static_cast<int16_t>((length % 2 == 0) ? -length
                                                       : -length + 2);
            entry.equal_gap_hi += static_cast<int16_t>(length);
            int group_index = -1;
            for (int group = 0; group < entry.gap_group_count; ++group) {
              if (entry.gap_groups[group].length == length) {
                group_index = group;
                break;
              }
            }
            if (group_index < 0) {
              if (entry.gap_group_count >= entry.gap_groups.size()) {
                throw std::runtime_error("too many gap-length groups");
              }
              group_index = entry.gap_group_count++;
              entry.gap_groups[group_index].length =
                  static_cast<uint8_t>(length);
            }
            GapGroup& group = entry.gap_groups[group_index];
            ++group.count;
            group.left_mask |= static_cast<unsigned __int128>(1)
                               << previous_fixed;
            constrained_edges += length;
          }
          previous_fixed = position;
          saw_unassigned = false;
        }
      }
      const int remaining_edges = (kSize - lag) - determined_edges;
      const int free_edges = remaining_edges - constrained_edges;
      if (free_edges < 0 || free_edges >= kSize) {
        throw std::runtime_error("invalid free-edge count");
      }
      entry.free_edges = static_cast<uint8_t>(free_edges);
    }
  }
  return templates;
}

const auto kBoundTemplates = BuildBoundTemplates();

AttainableRange IntersectProgression(int lo, int hi, int step,
                                     int target_lo, int target_hi) {
  int first = std::max(lo, target_lo);
  int residue = (first - lo) % step;
  if (residue < 0) {
    residue += step;
  }
  if (residue != 0) {
    first += step - residue;
  }
  const int upper = std::min(hi, target_hi);
  if (first > upper) {
    return {};
  }
  const int last = first + ((upper - first) / step) * step;
  return {true, first, last};
}

AttainableRange BoundRange(const State& state, int lag) {
  const BoundTemplate& entry = kBoundTemplates[state.depth][lag];
  int constrained_lo = 0;
  int constrained_hi = 0;
  for (uint8_t index = 0; index < entry.fixed_edge_count; ++index) {
    const Edge& edge = entry.fixed_edges[index];
    const int product = ValueAt(state, edge.left) * ValueAt(state, edge.right);
    constrained_lo += product;
    constrained_hi += product;
  }
  for (uint8_t index = 0; index < entry.gap_count; ++index) {
    const Gap& gap = entry.gaps[index];
    const int endpoint_product =
        ValueAt(state, gap.left) * ValueAt(state, gap.right);
    const int length = gap.length;
    if (endpoint_product == 1) {
      constrained_lo += (length % 2 == 0) ? -length : -length + 2;
      constrained_hi += length;
    } else {
      constrained_lo += (length % 2 == 1) ? -length : -length + 2;
      constrained_hi += length - 2;
    }
  }
  if (entry.free_edges > 0) {
    return IntersectProgression(constrained_lo - entry.free_edges,
                                constrained_hi + entry.free_edges, 2,
                                -kBound, kBound);
  }
  return IntersectProgression(constrained_lo, constrained_hi, 4, -kBound,
                              kBound);
}

AttainableRange SlowBoundRange(const State& state, int lag) {
  int constrained_lo = 0;
  int constrained_hi = 0;
  int free_edges = 0;
  for (int residue = 0; residue < lag && residue < kSize; ++residue) {
    int path_length = 0;
    std::array<int, kSize> fixed_offsets{};
    int fixed_count = 0;
    for (int position = residue; position < kSize; position += lag) {
      if (position < state.depth || position >= kSize - state.depth) {
        fixed_offsets[fixed_count++] = path_length;
      }
      ++path_length;
    }
    const int edge_count = path_length - 1;
    if (edge_count <= 0) {
      continue;
    }
    if (fixed_count < 2) {
      free_edges += edge_count;
      continue;
    }
    free_edges += fixed_offsets[0] +
                  (edge_count - fixed_offsets[fixed_count - 1]);
    for (int fixed = 0; fixed + 1 < fixed_count; ++fixed) {
      const int first_offset = fixed_offsets[fixed];
      const int second_offset = fixed_offsets[fixed + 1];
      const int length = second_offset - first_offset;
      const int first_position = residue + first_offset * lag;
      const int second_position = residue + second_offset * lag;
      const int endpoint_product =
          ValueAt(state, first_position) * ValueAt(state, second_position);
      if (endpoint_product == 1) {
        constrained_lo += (length % 2 == 0) ? -length : -length + 2;
        constrained_hi += length;
      } else {
        constrained_lo += (length % 2 == 1) ? -length : -length + 2;
        constrained_hi += length - 2;
      }
    }
  }
  if (free_edges > 0) {
    return IntersectProgression(constrained_lo - free_edges,
                                constrained_hi + free_edges, 2,
                                -kBound, kBound);
  }
  return IntersectProgression(constrained_lo, constrained_hi, 4, -kBound,
                              kBound);
}

bool MomentFeasible(const State& state, int even_lo, int even_hi, int odd_lo,
                    int odd_hi) {
  int assigned_even = 0;
  int assigned_odd = 0;
  int remaining_even = 0;
  int remaining_odd = 0;
  for (int position = 0; position < kSize; ++position) {
    if (position < state.depth || position >= kSize - state.depth) {
      if (position & 1) {
        assigned_odd += ValueAt(state, position);
      } else {
        assigned_even += ValueAt(state, position);
      }
    } else if (position & 1) {
      ++remaining_odd;
    } else {
      ++remaining_even;
    }
  }
  for (int even = assigned_even - remaining_even;
       even <= assigned_even + remaining_even; even += 2) {
    for (int odd = assigned_odd - remaining_odd;
         odd <= assigned_odd + remaining_odd; odd += 2) {
      const int even_target = (even * even + odd * odd - kSize) / 2;
      const int odd_target = even * odd;
      if (even_target >= even_lo && even_target <= even_hi &&
          odd_target >= odd_lo && odd_target <= odd_hi) {
        return true;
      }
    }
  }
  return false;
}

bool ModulusMomentFeasible(const State& state, int modulus,
                           int correlation_lo, int correlation_hi) {
  int square_lo = 0;
  int square_hi = 0;
  for (int residue = 0; residue < modulus; ++residue) {
    int assigned_sum = 0;
    int remaining = 0;
    for (int position = residue; position < kSize; position += modulus) {
      if (position < state.depth || position >= kSize - state.depth) {
        assigned_sum += ValueAt(state, position);
      } else {
        ++remaining;
      }
    }
    const int lo = assigned_sum - remaining;
    const int hi = assigned_sum + remaining;
    int minimum_absolute = 0;
    if (lo > 0) {
      minimum_absolute = lo;
    } else if (hi < 0) {
      minimum_absolute = -hi;
    } else if ((lo % 2) != 0) {
      minimum_absolute = 1;
    }
    square_lo += minimum_absolute * minimum_absolute;
    square_hi += std::max(lo * lo, hi * hi);
  }
  const int target_lo = (square_lo - kSize) / 2;
  const int target_hi = (square_hi - kSize) / 2;
  return target_lo <= correlation_hi && target_hi >= correlation_lo;
}

bool ExactFutureFeasible(const State& state) {
  int even_lo = 0;
  int even_hi = 0;
  int odd_lo = 0;
  int odd_hi = 0;
  std::array<int, 6> divisible_lo{};
  std::array<int, 6> divisible_hi{};
  const bool use_moments =
      g_moment_depth > 0 && state.depth >= g_moment_depth;
  for (int lag = kSize - 1; lag >= 1; --lag) {
    const AttainableRange range = BoundRange(state, lag);
    if (!range.feasible) {
      return false;
    }
    if (lag & 1) {
      odd_lo += range.first;
      odd_hi += range.last;
    } else {
      even_lo += range.first;
      even_hi += range.last;
    }
    if (use_moments) {
      for (int modulus = 3; modulus <= 5; ++modulus) {
        if (lag % modulus == 0) {
          divisible_lo[modulus] += range.first;
          divisible_hi[modulus] += range.last;
        }
      }
    }
  }
  if (use_moments &&
      !MomentFeasible(state, even_lo, even_hi, odd_lo, odd_hi)) {
    return false;
  }
  if (use_moments) {
    for (int modulus = 3; modulus <= 5; ++modulus) {
      if (!ModulusMomentFeasible(state, modulus, divisible_lo[modulus],
                                 divisible_hi[modulus])) {
        return false;
      }
    }
  }
  return true;
}

StrongDelta StrongAssign(StrongState& state, int position, int value) {
  StrongDelta delta;
  delta.position = static_cast<uint8_t>(position);
  state.values[position] = static_cast<int8_t>(value);
  for (int other = 0; other < kSize; ++other) {
    if (!state.assigned[other]) {
      continue;
    }
    const int lag = std::abs(position - other);
    const int product = value * state.values[other];
    state.correlation[lag] += product;
    delta.changes[delta.count++] = {
        static_cast<uint8_t>(lag), static_cast<int8_t>(product)};
  }
  state.assigned[position] = 1;
  if (g_moment_depth > 0) {
    if (position & 1) {
      state.odd_sum += value;
    } else {
      state.even_sum += value;
    }
    for (int modulus = 3; modulus <= 5; ++modulus) {
      state.modulus_sum[modulus][position % modulus] += value;
    }
  }
  return delta;
}

void StrongUndo(StrongState& state, const StrongDelta& delta) {
  if (g_moment_depth > 0) {
    if (delta.position & 1) {
      state.odd_sum -= state.values[delta.position];
    } else {
      state.even_sum -= state.values[delta.position];
    }
    for (int modulus = 3; modulus <= 5; ++modulus) {
      state.modulus_sum[modulus][delta.position % modulus] -=
          state.values[delta.position];
    }
  }
  state.assigned[delta.position] = 0;
  for (uint8_t index = 0; index < delta.count; ++index) {
    const StrongDelta::Change& change = delta.changes[index];
    state.correlation[change.lag] -= change.product;
  }
}

StrongState MakeStrongState(const State& state) {
  StrongState strong;
  for (int position = 0; position < kSize; ++position) {
    if (position < state.depth || position >= kSize - state.depth) {
      StrongAssign(strong, position, ValueAt(state, position));
    }
  }
  strong.depth = state.depth;
  return strong;
}

AttainableRange StrongBoundRange(const StrongState& state,
                                 unsigned __int128 code, int lag) {
  const BoundTemplate& entry = kBoundTemplates[state.depth][lag];
  int constrained_lo = state.correlation[lag] + entry.equal_gap_lo;
  int constrained_hi = state.correlation[lag] + entry.equal_gap_hi;
  for (uint8_t index = 0; index < entry.gap_group_count; ++index) {
    const GapGroup& group = entry.gap_groups[index];
    const int distance = lag * group.length;
    const unsigned __int128 differences = code ^ (code >> distance);
    const int mismatches = Popcount128(differences & group.left_mask);
    constrained_lo += (group.length % 2 == 0 ? 2 : -2) * mismatches;
    constrained_hi -= 2 * mismatches;
  }
  if (entry.free_edges > 0) {
    return IntersectProgression(constrained_lo - entry.free_edges,
                                constrained_hi + entry.free_edges, 2,
                                -kBound, kBound);
  }
  return IntersectProgression(constrained_lo, constrained_hi, 4, -kBound,
                              kBound);
}

bool StrongMomentFeasible(const StrongState& state, int even_lo, int even_hi,
                          int odd_lo, int odd_hi) {
  int remaining_even = 0;
  int remaining_odd = 0;
  for (int position = state.depth; position < kSize - state.depth;
       ++position) {
    if (position & 1) {
      ++remaining_odd;
    } else {
      ++remaining_even;
    }
  }
  for (int even = state.even_sum - remaining_even;
       even <= state.even_sum + remaining_even; even += 2) {
    for (int odd = state.odd_sum - remaining_odd;
         odd <= state.odd_sum + remaining_odd; odd += 2) {
      const int even_target = (even * even + odd * odd - kSize) / 2;
      const int odd_target = even * odd;
      if (even_target >= even_lo && even_target <= even_hi &&
          odd_target >= odd_lo && odd_target <= odd_hi) {
        return true;
      }
    }
  }
  return false;
}

bool StrongModulusMomentFeasible(const StrongState& state, int modulus,
                                 int correlation_lo, int correlation_hi) {
  int square_lo = 0;
  int square_hi = 0;
  for (int residue = 0; residue < modulus; ++residue) {
    int remaining = 0;
    for (int position = state.depth; position < kSize - state.depth;
         ++position) {
      remaining += position % modulus == residue;
    }
    const int lo = state.modulus_sum[modulus][residue] - remaining;
    const int hi = state.modulus_sum[modulus][residue] + remaining;
    int minimum_absolute = 0;
    if (lo > 0) {
      minimum_absolute = lo;
    } else if (hi < 0) {
      minimum_absolute = -hi;
    } else if ((lo % 2) != 0) {
      minimum_absolute = 1;
    }
    square_lo += minimum_absolute * minimum_absolute;
    square_hi += std::max(lo * lo, hi * hi);
  }
  const int target_lo = (square_lo - kSize) / 2;
  const int target_hi = (square_hi - kSize) / 2;
  return target_lo <= correlation_hi && target_hi >= correlation_lo;
}

bool ExactStrongFeasible(const StrongState& state, unsigned __int128 code) {
  int even_lo = 0;
  int even_hi = 0;
  int odd_lo = 0;
  int odd_hi = 0;
  std::array<int, 6> divisible_lo{};
  std::array<int, 6> divisible_hi{};
  const bool use_moments =
      g_moment_depth > 0 && state.depth >= g_moment_depth;
  for (int lag = kSize - 1; lag >= 1; --lag) {
    const AttainableRange range = StrongBoundRange(state, code, lag);
    if (!range.feasible) {
      return false;
    }
    if (lag & 1) {
      odd_lo += range.first;
      odd_hi += range.last;
    } else {
      even_lo += range.first;
      even_hi += range.last;
    }
    if (use_moments) {
      for (int modulus = 3; modulus <= 5; ++modulus) {
        if (lag % modulus == 0) {
          divisible_lo[modulus] += range.first;
          divisible_hi[modulus] += range.last;
        }
      }
    }
  }
  if (use_moments &&
      !StrongMomentFeasible(state, even_lo, even_hi, odd_lo, odd_hi)) {
    return false;
  }
  if (use_moments) {
    for (int modulus = 3; modulus <= 5; ++modulus) {
      if (!StrongModulusMomentFeasible(state, modulus,
                                       divisible_lo[modulus],
                                       divisible_hi[modulus])) {
        return false;
      }
    }
  }
  return true;
}

bool StrongCheapFeasible(const StrongState& state) {
  for (int lag = kSize - 1; lag >= 1; --lag) {
    const int remaining =
        (kSize - lag) - kBoundTemplates[state.depth][lag].fixed_edge_count;
    if (std::abs(state.correlation[lag]) > kBound + remaining) {
      return false;
    }
  }
  return true;
}

bool ShouldCheckExact(int depth) {
  return g_exact_start_depth > 0 && depth >= g_exact_start_depth &&
         depth < kHalf &&
         (depth - g_exact_start_depth) % g_exact_stride == 0;
}

unsigned __int128 CompleteCode(const State& state) {
  if (state.depth != kHalf) {
    throw std::runtime_error("attempted to assemble an incomplete code");
  }
  return static_cast<unsigned __int128>(state.left) |
         (static_cast<unsigned __int128>(state.right) << kHalf);
}

bool CompleteValid(const State& state) {
  const unsigned __int128 code = CompleteCode(state);
  for (int shift = 1; shift < kSize; ++shift) {
    const int overlap = kSize - shift;
    const auto differences = (code ^ (code >> shift)) & Mask128(overlap);
    const int correlation = overlap - 2 * Popcount128(differences);
    if (std::abs(correlation) > kBound) {
      return false;
    }
  }
  return true;
}

std::array<int, kSize> ToValues(const State& state) {
  const unsigned __int128 code = CompleteCode(state);
  std::array<int, kSize> values{};
  for (int index = 0; index < kSize; ++index) {
    values[index] = ((code >> index) & 1) != 0 ? 1 : -1;
  }
  return values;
}

std::string Transform(const std::array<int, kSize>& values, bool reverse,
                      bool alternate, bool negate) {
  std::string result;
  result.reserve(kSize);
  for (int index = 0; index < kSize; ++index) {
    const int source = reverse ? kSize - 1 - index : index;
    int value = values[source];
    if (alternate && (index & 1)) {
      value = -value;
    }
    if (negate) {
      value = -value;
    }
    result.push_back(value > 0 ? '1' : '0');
  }
  return result;
}

std::string Canonical(const State& state) {
  const auto values = ToValues(state);
  std::string best(kSize, '2');
  for (bool reverse : {false, true}) {
    for (bool alternate : {false, true}) {
      for (bool negate : {false, true}) {
        best = std::min(best, Transform(values, reverse, alternate, negate));
      }
    }
  }
  return best;
}

std::optional<State> Extend(const State& state, int left_bit, int right_bit) {
  State child = state;
  if (child.reversal_relation == 0 && left_bit != right_bit) {
    if (left_bit > right_bit) {
      return std::nullopt;
    }
    child.reversal_relation = -1;
  }
  child.left |= static_cast<uint64_t>(left_bit) << child.depth;
  child.right = (child.right << 1) | static_cast<uint64_t>(right_bit);
  ++child.depth;
  if (std::abs(NewlyDeterminedCorrelation(child.left, child.right,
                                          child.depth)) > kBound) {
    return std::nullopt;
  }
  return child;
}

void SearchStrongBody(const State& state, StrongState& strong,
                      Counters& counters, std::set<std::string>& answers,
                      uint64_t node_limit) {
  if (state.depth == kHalf) {
    ++counters.leaves;
    if (!CompleteValid(state)) {
      ++counters.central_rejects;
      return;
    }
    answers.insert(Canonical(state));
    return;
  }

  const int left_position = state.depth;
  const int right_position = kSize - 1 - state.depth;
  for (int left_bit : {0, 1}) {
    for (int right_bit : {0, 1}) {
      const auto child = Extend(state, left_bit, right_bit);
      if (!child) {
        continue;
      }
      const StrongDelta left_delta =
          StrongAssign(strong, left_position, left_bit ? 1 : -1);
      const StrongDelta right_delta =
          StrongAssign(strong, right_position, right_bit ? 1 : -1);
      ++strong.depth;

      bool feasible = true;
      if (child->depth < kHalf) {
        if (!StrongCheapFeasible(strong)) {
          ++counters.strong_cheap_prunes;
          feasible = false;
        } else if ((child->depth - g_strong_switch_depth - 1) %
                       g_strong_exact_stride ==
                   0) {
          ++counters.exact_checks;
          feasible = ExactStrongFeasible(strong, PartialCode(*child));
          if (!feasible) {
            ++counters.exact_prunes;
          }
        }
      }
      if (feasible) {
        if (node_limit != 0 && counters.nodes >= node_limit) {
          counters.truncated = true;
        } else {
          ++counters.nodes;
          SearchStrongBody(*child, strong, counters, answers, node_limit);
        }
      }

      --strong.depth;
      StrongUndo(strong, right_delta);
      StrongUndo(strong, left_delta);
      if (counters.truncated) {
        return;
      }
    }
  }
}

void Search(const State& state, Counters& counters,
            std::set<std::string>& answers, uint64_t node_limit) {
  if (node_limit != 0 && counters.nodes >= node_limit) {
    counters.truncated = true;
    return;
  }
  ++counters.nodes;
  if (g_strong_switch_depth > 0 &&
      state.depth >= g_strong_switch_depth) {
    StrongState strong = MakeStrongState(state);
    SearchStrongBody(state, strong, counters, answers, node_limit);
    return;
  }
  if (state.depth == kHalf) {
    ++counters.leaves;
    if (!CompleteValid(state)) {
      ++counters.central_rejects;
      return;
    }
    answers.insert(Canonical(state));
    return;
  }
  for (int left_bit : {0, 1}) {
    for (int right_bit : {0, 1}) {
      if (const auto child = Extend(state, left_bit, right_bit)) {
        bool feasible = true;
        if (ShouldCheckExact(child->depth)) {
          ++counters.exact_checks;
          feasible = ExactFutureFeasible(*child);
          if (!feasible) {
            ++counters.exact_prunes;
          }
        }
        if (feasible) {
          Search(*child, counters, answers, node_limit);
        }
        if (counters.truncated) {
          return;
        }
      }
    }
  }
}

void MakeTasks(const State& state, int split_depth, std::vector<State>& tasks) {
  if (state.depth == split_depth) {
    tasks.push_back(state);
    return;
  }
  for (int left_bit : {0, 1}) {
    for (int right_bit : {0, 1}) {
      if (const auto child = Extend(state, left_bit, right_bit)) {
        if (!ShouldCheckExact(child->depth) || ExactFutureFeasible(*child)) {
          MakeTasks(*child, split_depth, tasks);
        }
      }
    }
  }
}

int BorderDistance(const State& state, const std::string& bits) {
  int distance = 0;
  for (int index = 0; index < state.depth; ++index) {
    const int left_target = bits[index] == '1';
    const int left_value = (state.left >> index) & 1;
    distance += left_target != left_value;

    const int position = kSize - state.depth + index;
    const int right_target = bits[position] == '1';
    const int right_value = (state.right >> index) & 1;
    distance += right_target != right_value;
  }
  return distance;
}

std::vector<std::string> Split(const std::string& text, char separator) {
  std::stringstream stream(text);
  std::vector<std::string> fields;
  std::string field;
  while (std::getline(stream, field, separator)) {
    fields.push_back(field);
  }
  return fields;
}

std::unordered_set<uint64_t> LoadJournal(const std::string& path) {
  std::unordered_set<uint64_t> completed;
  if (path.empty()) {
    return completed;
  }
  std::ifstream input(path);
  std::string line;
  while (std::getline(input, line)) {
    const auto fields = Split(line, '\t');
    if (fields.size() < 11 || fields[0] != "TASK" ||
        fields[10] != "COMPLETE") {
      continue;
    }
    completed.insert(std::stoull(fields[1]));
    if (!fields[9].empty() && fields[9] != "-") {
      for (const auto& answer : Split(fields[9], ',')) {
        global_answers.insert(answer);
      }
    }
  }
  return completed;
}

void AppendJournal(const std::string& path, uint64_t task_index,
                   const Counters& counters, double elapsed,
                   const std::set<std::string>& answers) {
  if (path.empty()) {
    return;
  }
  std::lock_guard<std::mutex> lock(output_mutex);
  std::ofstream output(path, std::ios::app);
  if (!output) {
    throw std::runtime_error("cannot append journal: " + path);
  }
  output << "TASK\t" << task_index << '\t' << counters.nodes << '\t'
         << counters.leaves << '\t' << counters.central_rejects << '\t'
         << counters.strong_cheap_prunes << '\t' << counters.exact_checks
         << '\t' << counters.exact_prunes << '\t' << elapsed << '\t';
  if (answers.empty()) {
    output << '-';
  } else {
    bool first = true;
    for (const auto& answer : answers) {
      if (!first) {
        output << ',';
      }
      first = false;
      output << answer;
    }
  }
  output << '\t' << (counters.truncated ? "TRUNCATED" : "COMPLETE") << '\n';
  output.flush();
}

Options ParseOptions(int argc, char** argv) {
  Options options;
  for (int index = 1; index < argc; ++index) {
    const std::string argument = argv[index];
    auto require_value = [&]() -> std::string {
      if (++index >= argc) {
        throw std::runtime_error("missing value after " + argument);
      }
      return argv[index];
    };
    if (argument == "--split-depth") {
      options.split_depth = std::stoi(require_value());
    } else if (argument == "--threads") {
      options.threads = std::stoi(require_value());
    } else if (argument == "--max-tasks") {
      options.max_tasks = std::stoull(require_value());
    } else if (argument == "--node-limit") {
      options.node_limit = std::stoull(require_value());
    } else if (argument == "--task-shards") {
      options.task_shards = std::stoull(require_value());
    } else if (argument == "--task-shard") {
      options.task_shard = std::stoull(require_value());
    } else if (argument == "--exact-start-depth") {
      options.exact_start_depth = std::stoi(require_value());
    } else if (argument == "--exact-stride") {
      options.exact_stride = std::stoi(require_value());
    } else if (argument == "--moment-depth") {
      options.moment_depth = std::stoi(require_value());
    } else if (argument == "--strong-switch-depth") {
      options.strong_switch_depth = std::stoi(require_value());
    } else if (argument == "--strong-exact-stride") {
      options.strong_exact_stride = std::stoi(require_value());
    } else if (argument == "--near-bits") {
      options.near_bits = require_value();
    } else if (argument == "--journal") {
      options.journal = require_value();
    } else if (argument == "--self-test") {
      options.self_test = true;
    } else {
      throw std::runtime_error("unknown argument: " + argument);
    }
  }
  if (options.split_depth < 1 || options.split_depth > kHalf) {
    throw std::runtime_error("split depth must be in [1,35]");
  }
  if (options.exact_start_depth < 0 ||
      options.exact_start_depth >= kHalf) {
    throw std::runtime_error("exact start depth must be zero or in [1,34]");
  }
  if (options.exact_stride < 1 || options.exact_stride >= kHalf) {
    throw std::runtime_error("exact stride must be in [1,34]");
  }
  if (options.moment_depth < 0 || options.moment_depth > kHalf) {
    throw std::runtime_error("moment depth must be zero or in [1,35]");
  }
  if (options.strong_switch_depth < 0 ||
      options.strong_switch_depth >= kHalf) {
    throw std::runtime_error("strong switch depth must be zero or in [1,34]");
  }
  if (options.strong_exact_stride < 1 ||
      options.strong_exact_stride >= kHalf) {
    throw std::runtime_error("strong exact stride must be in [1,34]");
  }
  if (options.task_shards == 0 || options.task_shard >= options.task_shards) {
    throw std::runtime_error(
        "task shards must be positive and task shard must be in range");
  }
  if (options.exact_start_depth > 0 && options.strong_switch_depth > 0) {
    throw std::runtime_error(
        "sampled exact checks and strong-state switching are mutually exclusive");
  }
  if (!options.near_bits.empty() &&
      (options.near_bits.size() != kSize ||
       options.near_bits.find_first_not_of("01") != std::string::npos)) {
    throw std::runtime_error("near-bits must contain exactly 70 binary digits");
  }
  return options;
}

void SelfTest() {
  std::mt19937_64 generator(0x12124930ULL);
  for (int trial = 0; trial < 20000; ++trial) {
    State state;
    state.depth = static_cast<uint8_t>(1 + generator() % kHalf);
    state.left = 0;
    state.right = 0;
    for (int index = 0; index < state.depth; ++index) {
      state.left |= (generator() & 1U) << index;
      state.right |= (generator() & 1U) << index;
    }
    const StrongState strong = MakeStrongState(state);
    for (int lag = 1; lag < kSize; ++lag) {
      const AttainableRange expected = SlowBoundRange(state, lag);
      const AttainableRange observed = BoundRange(state, lag);
      const AttainableRange incremental =
          StrongBoundRange(strong, PartialCode(state), lag);
      if (expected.feasible != observed.feasible ||
          expected.first != observed.first || expected.last != observed.last ||
          expected.feasible != incremental.feasible ||
          expected.first != incremental.first ||
          expected.last != incremental.last) {
        std::ostringstream message;
        message << "bound-template mismatch trial=" << trial
                << " depth=" << static_cast<int>(state.depth)
                << " lag=" << lag;
        throw std::runtime_error(message.str());
      }
    }
  }

  // Three 70-bit reference classes are transcribed from the public PSL-4
  // constructions routed in literature.json (Leukhin--Potekhin,
  // Dimitrov--Baitcheva--Nikolov, and the PslRK/Mertens record). They are
  // correctness fixtures only: the search never uses them to generate or
  // prune candidates.
  const std::array<std::string_view, 3> known_psl4 = {
      "1001011001011001010100110011001100001010110101000000000010111100011111",
      "1010110101101010101110011001110110010111100111100110110110000000001111",
      "1000000101010100010010000011011011110011100011010010001100110111101001",
  };
  const int saved_moment_depth = g_moment_depth;
  g_moment_depth = 30;
  for (const std::string_view known : known_psl4) {
    State state;
    state.left = static_cast<uint64_t>(known[0] == '1');
    state.right = static_cast<uint64_t>(known[kSize - 1] == '1');
    state.depth = 1;
    if (!ExactFutureFeasible(state)) {
      throw std::runtime_error("known PSL-4 seed rejected at depth one");
    }
    for (int depth = 1; depth < kHalf; ++depth) {
      state.left |= static_cast<uint64_t>(known[depth] == '1') << depth;
      state.right =
          (state.right << 1) |
          static_cast<uint64_t>(known[kSize - 1 - depth] == '1');
      ++state.depth;
      const StrongState strong = MakeStrongState(state);
      if (!ExactFutureFeasible(state) ||
          !ExactStrongFeasible(strong, PartialCode(state))) {
        std::ostringstream message;
        message << "known PSL-4 seed rejected at depth="
                << static_cast<int>(state.depth);
        throw std::runtime_error(message.str());
      }
    }
    if (!CompleteValid(state) || Canonical(state).size() != kSize) {
      throw std::runtime_error("known PSL-4 seed rejected at leaf");
    }
  }
  g_moment_depth = saved_moment_depth;
  std::cerr << "self-test OK: 20000 partial states x 69 lags; 3 PSL-4 classes\n";
}

}  // namespace

int main(int argc, char** argv) {
  try {
    const Options options = ParseOptions(argc, argv);
    g_exact_start_depth = options.exact_start_depth;
    g_exact_stride = options.exact_stride;
    g_moment_depth = options.moment_depth;
    g_strong_switch_depth = options.strong_switch_depth;
    g_strong_exact_stride = options.strong_exact_stride;
    if (options.self_test) {
      SelfTest();
      return 0;
    }
#ifdef _OPENMP
    if (options.threads > 0) {
      omp_set_num_threads(options.threads);
    }
#endif
    std::vector<State> tasks;
    MakeTasks(State{}, options.split_depth, tasks);
    const auto completed = LoadJournal(options.journal);
    std::vector<uint64_t> pending;
    pending.reserve(tasks.size());
    for (uint64_t index = 0; index < tasks.size(); ++index) {
      if (!completed.contains(index) &&
          SplitMix64(index) % options.task_shards == options.task_shard) {
        pending.push_back(index);
      }
    }
    if (!options.near_bits.empty()) {
      std::stable_sort(pending.begin(), pending.end(), [&](uint64_t left,
                                                           uint64_t right) {
        return BorderDistance(tasks[left], options.near_bits) <
               BorderDistance(tasks[right], options.near_bits);
      });
    }
    if (options.max_tasks != 0 && pending.size() > options.max_tasks) {
      pending.resize(options.max_tasks);
    }

    std::cerr << "tasks_total=" << tasks.size()
              << " completed=" << completed.size()
              << " pending=" << pending.size()
              << " split_depth=" << options.split_depth
              << " exact_start_depth=" << options.exact_start_depth
              << " exact_stride=" << options.exact_stride
              << " moment_depth=" << options.moment_depth
              << " strong_switch_depth=" << options.strong_switch_depth
              << " strong_exact_stride=" << options.strong_exact_stride
              << " task_shard=" << options.task_shard << '/'
              << options.task_shards
              << " node_limit=" << options.node_limit << '\n';
    const auto started = std::chrono::steady_clock::now();

#pragma omp parallel for schedule(dynamic, 1)
    for (uint64_t pending_index = 0; pending_index < pending.size();
         ++pending_index) {
      const uint64_t task_index = pending[pending_index];
      Counters counters;
      std::set<std::string> answers;
      const auto task_started = std::chrono::steady_clock::now();
      Search(tasks[task_index], counters, answers, options.node_limit);
      const double elapsed = std::chrono::duration<double>(
                                 std::chrono::steady_clock::now() - task_started)
                                 .count();
      AppendJournal(options.journal, task_index, counters, elapsed, answers);
      {
        std::lock_guard<std::mutex> lock(answer_mutex);
        global_answers.insert(answers.begin(), answers.end());
      }
      total_nodes.fetch_add(counters.nodes, std::memory_order_relaxed);
      total_leaves.fetch_add(counters.leaves, std::memory_order_relaxed);
      total_strong_cheap_prunes.fetch_add(counters.strong_cheap_prunes,
                                          std::memory_order_relaxed);
      total_exact_checks.fetch_add(counters.exact_checks,
                                   std::memory_order_relaxed);
      total_exact_prunes.fetch_add(counters.exact_prunes,
                                   std::memory_order_relaxed);
      const uint64_t done = tasks_finished.fetch_add(1) + 1;
      std::lock_guard<std::mutex> lock(output_mutex);
      std::cerr << "task=" << task_index << " progress=" << done << '/'
                << pending.size() << " nodes=" << counters.nodes
                << " leaves=" << counters.leaves
                << " strong_cheap_prunes=" << counters.strong_cheap_prunes
                << " exact_checks=" << counters.exact_checks
                << " exact_prunes=" << counters.exact_prunes
                << " seconds=" << elapsed
                << " status=" << (counters.truncated ? "TRUNCATED" : "COMPLETE")
                << " answers=" << answers.size() << '\n';
    }

    const double elapsed = std::chrono::duration<double>(
                               std::chrono::steady_clock::now() - started)
                               .count();
    std::cerr << "DONE tasks=" << pending.size()
              << " nodes=" << total_nodes.load()
              << " leaves=" << total_leaves.load()
              << " strong_cheap_prunes="
              << total_strong_cheap_prunes.load()
              << " exact_checks=" << total_exact_checks.load()
              << " exact_prunes=" << total_exact_prunes.load()
              << " classes=" << global_answers.size()
              << " seconds=" << elapsed << '\n';
    for (const auto& answer : global_answers) {
      std::cout << answer << '\n';
    }
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return 2;
  }
}

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
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
#include <string_view>
#include <unordered_set>
#include <utility>
#include <vector>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace {

constexpr int kSize = 70;
constexpr int kBound = 4;

struct State {
  std::array<int8_t, kSize> values{};
  std::array<uint8_t, kSize> assigned{};
  std::array<int16_t, kSize> correlation{};
  std::array<uint8_t, kSize> determined{};
  int depth = 0;
  int even_sum = 0;
  int odd_sum = 0;
  std::array<std::array<int8_t, 5>, 6> modulus_sum{};
  // -1 means the fixed prefix is lexicographically smaller than its reverse;
  // 0 means equal so far. +1 is rejected and never stored.
  int reversal_relation = 0;
};

struct Delta {
  struct Change {
    uint8_t lag = 0;
    int8_t product = 0;
  };
  uint8_t position = 0;
  uint8_t count = 0;
  std::array<Change, kSize> correlation_changes{};
};

struct Gap {
  uint8_t left = 0;
  uint8_t right = 0;
  uint8_t length = 0;
};

struct LagTemplate {
  uint8_t free_edges = 0;
  uint8_t gap_count = 0;
  std::array<Gap, kSize> gaps{};
};

struct Counters {
  uint64_t nodes = 0;
  uint64_t cheap_prunes = 0;
  uint64_t exact_prunes = 0;
};

struct Options {
  int split_depth = 9;
  int threads = 0;
  uint64_t max_tasks = 0;
  uint64_t shuffle_seed = 0;
  int moment_depth = 0;
  std::string near_bits;
  bool self_test = false;
  std::string journal = "runs/psl4-length70.jsonl";
};

std::mutex journal_mutex;
std::mutex answer_mutex;
std::set<std::string> global_classes;
std::atomic<uint64_t> tasks_finished{0};
std::atomic<uint64_t> total_nodes{0};
std::atomic<uint64_t> total_cheap_prunes{0};
std::atomic<uint64_t> total_exact_prunes{0};
int g_moment_depth = 0;

inline Delta Assign(State& state, int position, int value) {
  Delta delta;
  delta.position = static_cast<uint8_t>(position);
  state.values[position] = static_cast<int8_t>(value);
  for (int other = 0; other < kSize; ++other) {
    if (!state.assigned[other]) {
      continue;
    }
    const int lag = std::abs(position - other);
    const int product = value * state.values[other];
    state.correlation[lag] += product;
    ++state.determined[lag];
    delta.correlation_changes[delta.count++] = {
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

inline void Undo(State& state, const Delta& delta) {
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
    const auto& change = delta.correlation_changes[index];
    state.correlation[change.lag] -= change.product;
    --state.determined[change.lag];
  }
}

bool CheapFeasible(const State& state) {
  for (int lag = kSize - 1; lag >= 1; --lag) {
    const int remaining = (kSize - lag) - state.determined[lag];
    if (std::abs(state.correlation[lag]) > kBound + remaining) {
      return false;
    }
  }
  return true;
}

bool ProgressionIntersects(int lo, int hi, int step, int target_lo,
                           int target_hi) {
  int first = std::max(lo, target_lo);
  int residue = (first - lo) % step;
  if (residue < 0) {
    residue += step;
  }
  if (residue != 0) {
    first += step - residue;
  }
  return first <= std::min(hi, target_hi);
}

struct AttainableRange {
  bool feasible = false;
  int first = 0;
  int last = 0;
};

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

std::array<std::array<LagTemplate, kSize>, kSize / 2 + 1>
BuildLagTemplates() {
  std::array<std::array<LagTemplate, kSize>, kSize / 2 + 1> templates{};
  for (int depth = 1; depth <= kSize / 2; ++depth) {
    std::array<uint8_t, kSize> assigned{};
    for (int position = 0; position < kSize; ++position) {
      assigned[position] =
          static_cast<uint8_t>(position < depth || position >= kSize - depth);
    }
    for (int lag = 1; lag < kSize; ++lag) {
      LagTemplate& entry = templates[depth][lag];
      int determined_edges = 0;
      for (int position = 0; position + lag < kSize; ++position) {
        determined_edges += assigned[position] && assigned[position + lag];
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
              throw std::runtime_error("invalid precomputed constrained gap");
            }
            entry.gaps[entry.gap_count++] = {
                static_cast<uint8_t>(previous_fixed),
                static_cast<uint8_t>(position), static_cast<uint8_t>(length)};
            constrained_edges += length;
          }
          previous_fixed = position;
          saw_unassigned = false;
        }
      }
      const int remaining_edges = (kSize - lag) - determined_edges;
      const int free_edges = remaining_edges - constrained_edges;
      if (free_edges < 0 || free_edges >= kSize) {
        throw std::runtime_error("invalid precomputed free-edge count");
      }
      entry.free_edges = static_cast<uint8_t>(free_edges);
    }
  }
  return templates;
}

const auto kLagTemplates = BuildLagTemplates();

// Compute the exact set of attainable values for one lag under the current
// partial assignment. The lag graph is a disjoint union of paths. Between two
// fixed vertices, the parity of negative edge-products is fixed by the endpoint
// product, giving a contiguous arithmetic progression with step four. Tails
// with fewer than two fixed endpoints are free; one free edge merges the total
// into a contiguous step-two progression.
bool LagFeasibleSlow(const State& state, int lag) {
  int constrained_lo = 0;
  int constrained_hi = 0;
  int free_edges = 0;

  for (int residue = 0; residue < lag && residue < kSize; ++residue) {
    int path_length = 0;
    std::array<int, kSize> fixed_offsets{};
    int fixed_count = 0;
    for (int vertex = residue; vertex < kSize; vertex += lag) {
      if (state.assigned[vertex]) {
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
      const int first_vertex = residue + first_offset * lag;
      const int second_vertex = residue + second_offset * lag;
      const int endpoint_product =
          state.values[first_vertex] * state.values[second_vertex];

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
    return ProgressionIntersects(constrained_lo - free_edges,
                                 constrained_hi + free_edges, 2, -kBound,
                                 kBound);
  }
  return ProgressionIntersects(constrained_lo, constrained_hi, 4, -kBound,
                               kBound);
}

inline AttainableRange LagRange(const State& state, int lag) {
  const LagTemplate& entry = kLagTemplates[state.depth][lag];
  int constrained_lo = state.correlation[lag];
  int constrained_hi = state.correlation[lag];
  for (uint8_t index = 0; index < entry.gap_count; ++index) {
    const Gap& gap = entry.gaps[index];
    const int endpoint_product =
        state.values[gap.left] * state.values[gap.right];
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

inline bool LagFeasible(const State& state, int lag) {
  return LagRange(state, lag).feasible;
}

// The even- and odd-index spin sums jointly determine two global moments of
// the aperiodic correlations.  Writing e=sum(x_0,x_2,...) and
// o=sum(x_1,x_3,...), every completion must satisfy
//
//   sum_{k even, k>0} C_k = (e^2 + o^2 - N) / 2,
//   sum_{k odd}       C_k = e o.
//
// Per-lag path feasibility is exact but independent across lags.  These two
// identities cheaply reject combinations of individually feasible lag ranges
// that no binary completion can realize.  Apply the check only late enough
// that enumerating the remaining possible (e,o) pairs is inexpensive.
bool MomentFeasible(const State& state, int even_lo, int even_hi, int odd_lo,
                    int odd_hi) {
  if (g_moment_depth <= 0 || state.depth < g_moment_depth) {
    return true;
  }
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
      const int even_target =
          (even * even + odd * odd - kSize) / 2;
      const int odd_target = even * odd;
      if (even_target >= even_lo && even_target <= even_hi &&
          odd_target >= odd_lo && odd_target <= odd_hi) {
        return true;
      }
    }
  }
  return false;
}

// For every modulus m, grouping spins by index modulo m gives another exact
// correlation identity:
//
//   sum_{k > 0, m | k} C_k = (sum_r y_r^2 - N) / 2,
//
// where y_r is the final spin sum in residue class r.  Interval bounds on the
// possible y_r squares provide three cheap, independent necessary conditions.
bool ModulusMomentFeasible(const State& state, int modulus,
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

bool ExactFeasible(const State& state) {
  int even_lo = 0;
  int even_hi = 0;
  int odd_lo = 0;
  int odd_hi = 0;
  std::array<int, 6> divisible_lo{};
  std::array<int, 6> divisible_hi{};
  const bool use_moments =
      g_moment_depth > 0 && state.depth >= g_moment_depth;
  for (int lag = kSize - 1; lag >= 1; --lag) {
    const AttainableRange range = LagRange(state, lag);
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
  if (!MomentFeasible(state, even_lo, even_hi, odd_lo, odd_hi)) {
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

void SelfTestLagTemplates() {
  std::mt19937_64 generator(0x12124930ULL);
  for (int trial = 0; trial < 20000; ++trial) {
    const int target_depth = 1 + static_cast<int>(generator() % (kSize / 2));
    State state;
    Assign(state, 0, 1);
    Assign(state, kSize - 1, 1);
    state.depth = 1;
    while (state.depth < target_depth) {
      const int left = state.depth;
      const int right = kSize - 1 - state.depth;
      Assign(state, left, (generator() & 1U) ? 1 : -1);
      Assign(state, right, (generator() & 1U) ? 1 : -1);
      ++state.depth;
    }
    for (int lag = 1; lag < kSize; ++lag) {
      const bool expected = LagFeasibleSlow(state, lag);
      const bool actual = LagFeasible(state, lag);
      if (expected != actual) {
        std::ostringstream message;
        message << "lag template mismatch trial=" << trial
                << " depth=" << state.depth << " lag=" << lag
                << " expected=" << expected << " actual=" << actual;
        throw std::runtime_error(message.str());
      }
    }
  }
  const std::array<std::string_view, 3> known_psl4 = {
      "1001011001011001010100110011001100001010110101000000000010111100011111",
      "1010110101101010101110011001110110010111100111100110110110000000001111",
      "1000000101010100010010000011011011110011100011010010001100110111101001",
  };
  const int saved_moment_depth = g_moment_depth;
  g_moment_depth = 30;
  for (const std::string_view bits : known_psl4) {
    bool checked = false;
    for (bool reverse : {false, true}) {
      for (bool alternate : {false, true}) {
        for (bool negate : {false, true}) {
          std::array<int8_t, kSize> values{};
          for (int index = 0; index < kSize; ++index) {
            const int source = reverse ? kSize - 1 - index : index;
            int value = bits[source] == '1' ? 1 : -1;
            if (alternate && (index & 1)) {
              value = -value;
            }
            if (negate) {
              value = -value;
            }
            values[index] = static_cast<int8_t>(value);
          }
          if (values.front() != 1 || values.back() != 1 ||
              std::lexicographical_compare(values.rbegin(), values.rend(),
                                           values.begin(), values.end())) {
            continue;
          }
          State state;
          Assign(state, 0, values[0]);
          Assign(state, kSize - 1, values[kSize - 1]);
          state.depth = 1;
          for (int depth = 1; depth < kSize / 2; ++depth) {
            Assign(state, depth, values[depth]);
            Assign(state, kSize - 1 - depth, values[kSize - 1 - depth]);
            ++state.depth;
            if (!ExactFeasible(state)) {
              std::ostringstream message;
              message << "global moment bound rejected known PSL4 class at depth="
                      << state.depth;
              throw std::runtime_error(message.str());
            }
          }
          checked = true;
          break;
        }
        if (checked) {
          break;
        }
      }
      if (checked) {
        break;
      }
    }
    if (!checked) {
      throw std::runtime_error("no normalized representative for known PSL4 class");
    }
  }
  g_moment_depth = saved_moment_depth;
  std::cerr << "self-test OK: 20000 partial states x 69 lags\n";
}

std::string Transform(const State& state, bool reverse, bool alternate,
                      bool negate) {
  std::string result;
  result.reserve(kSize);
  for (int index = 0; index < kSize; ++index) {
    const int source = reverse ? kSize - 1 - index : index;
    int value = state.values[source];
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
  std::string best(kSize, '2');
  for (bool reverse : {false, true}) {
    for (bool alternate : {false, true}) {
      for (bool negate : {false, true}) {
        best = std::min(best,
                        Transform(state, reverse, alternate, negate));
      }
    }
  }
  return best;
}

bool CompleteValid(const State& state) {
  for (int lag = 1; lag < kSize; ++lag) {
    int correlation = 0;
    for (int index = 0; index + lag < kSize; ++index) {
      correlation += state.values[index] * state.values[index + lag];
    }
    if (std::abs(correlation) > kBound) {
      return false;
    }
  }
  return true;
}

void Search(State& state, Counters& counters, std::set<std::string>& answers) {
  ++counters.nodes;
  if (state.depth == kSize / 2) {
    if (!CompleteValid(state)) {
      throw std::runtime_error("exact bound admitted an invalid leaf");
    }
    answers.insert(Canonical(state));
    return;
  }

  const int left = state.depth;
  const int right = kSize - 1 - state.depth;
  for (int left_value : {-1, 1}) {
    for (int right_value : {-1, 1}) {
      int next_relation = state.reversal_relation;
      if (next_relation == 0 && left_value != right_value) {
        if (left_value > right_value) {
          continue;
        }
        next_relation = -1;
      }

      const int previous_relation = state.reversal_relation;
      Delta left_delta = Assign(state, left, left_value);
      Delta right_delta = Assign(state, right, right_value);
      ++state.depth;
      state.reversal_relation = next_relation;
      if (!CheapFeasible(state)) {
        ++counters.cheap_prunes;
      } else if (!ExactFeasible(state)) {
        ++counters.exact_prunes;
      } else {
        Search(state, counters, answers);
      }
      state.reversal_relation = previous_relation;
      --state.depth;
      Undo(state, right_delta);
      Undo(state, left_delta);
    }
  }
}

void MakeTasks(State& state, int split_depth, std::vector<State>& tasks) {
  if (state.depth == split_depth) {
    tasks.push_back(state);
    return;
  }
  const int left = state.depth;
  const int right = kSize - 1 - state.depth;
  for (int left_value : {-1, 1}) {
    for (int right_value : {-1, 1}) {
      int next_relation = state.reversal_relation;
      if (next_relation == 0 && left_value != right_value) {
        if (left_value > right_value) {
          continue;
        }
        next_relation = -1;
      }
      const int previous_relation = state.reversal_relation;
      Delta left_delta = Assign(state, left, left_value);
      Delta right_delta = Assign(state, right, right_value);
      ++state.depth;
      state.reversal_relation = next_relation;
      if (CheapFeasible(state) && ExactFeasible(state)) {
        MakeTasks(state, split_depth, tasks);
      }
      state.reversal_relation = previous_relation;
      --state.depth;
      Undo(state, right_delta);
      Undo(state, left_delta);
    }
  }
}

std::vector<std::string> Split(std::string_view text, char separator) {
  std::vector<std::string> values;
  std::stringstream stream{std::string(text)};
  std::string value;
  while (std::getline(stream, value, separator)) {
    values.push_back(value);
  }
  return values;
}

std::unordered_set<uint64_t> LoadJournal(const std::string& path) {
  std::unordered_set<uint64_t> completed;
  std::ifstream input(path);
  std::string line;
  while (std::getline(input, line)) {
    const auto fields = Split(line, '\t');
    if (fields.size() < 7 || fields[0] != "TASK") {
      continue;
    }
    const uint64_t index = std::stoull(fields[1]);
    completed.insert(index);
    if (!fields[6].empty() && fields[6] != "-") {
      for (const std::string& key : Split(fields[6], ',')) {
        if (key.size() == kSize) {
          global_classes.insert(key);
        }
      }
    }
  }
  return completed;
}

void AppendTask(const std::string& path, uint64_t index,
                const Counters& counters, double elapsed,
                const std::set<std::string>& answers) {
  std::lock_guard<std::mutex> lock(journal_mutex);
  std::ofstream output(path, std::ios::app);
  if (!output) {
    throw std::runtime_error("cannot append journal: " + path);
  }
  output << "TASK\t" << index << '\t' << counters.nodes << '\t'
         << counters.cheap_prunes << '\t' << counters.exact_prunes << '\t'
         << elapsed << '\t';
  if (answers.empty()) {
    output << '-';
  } else {
    bool first = true;
    for (const std::string& answer : answers) {
      if (!first) {
        output << ',';
      }
      first = false;
      output << answer;
    }
  }
  output << '\n';
  output.flush();
  if (!output) {
    throw std::runtime_error("failed to flush journal: " + path);
  }
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
    } else if (argument == "--shuffle-seed") {
      options.shuffle_seed = std::stoull(require_value());
    } else if (argument == "--moment-depth") {
      options.moment_depth = std::stoi(require_value());
    } else if (argument == "--near-bits") {
      options.near_bits = require_value();
    } else if (argument == "--self-test") {
      options.self_test = true;
    } else if (argument == "--journal") {
      options.journal = require_value();
    } else {
      throw std::runtime_error("unknown argument: " + argument);
    }
  }
  if (options.split_depth < 1 || options.split_depth > kSize / 2) {
    throw std::runtime_error("split depth must be in [1,35]");
  }
  if (options.moment_depth < 0 || options.moment_depth > kSize / 2) {
    throw std::runtime_error("moment depth must be zero or in [1,35]");
  }
  if (!options.near_bits.empty() &&
      (options.near_bits.size() != kSize ||
       options.near_bits.find_first_not_of("01") != std::string::npos)) {
    throw std::runtime_error("near-bits must contain exactly 70 binary digits");
  }
  return options;
}

int BorderDistance(const State& state, const std::string& bits) {
  int distance = 0;
  for (int position = 0; position < kSize; ++position) {
    if (!state.assigned[position]) {
      continue;
    }
    const int target = bits[position] == '1' ? 1 : -1;
    distance += state.values[position] != target;
  }
  return distance;
}

}  // namespace

int main(int argc, char** argv) {
  try {
    const Options options = ParseOptions(argc, argv);
    g_moment_depth = options.moment_depth;
    if (options.self_test) {
      SelfTestLagTemplates();
      return 0;
    }
#ifdef _OPENMP
    if (options.threads > 0) {
      omp_set_num_threads(options.threads);
    }
#endif

    State root;
    // Negation fixes the first endpoint. For even length, alternation then fixes
    // the last endpoint without changing the PSL constraint.
    Assign(root, 0, 1);
    Assign(root, kSize - 1, 1);
    root.depth = 1;

    std::vector<State> tasks;
    MakeTasks(root, options.split_depth, tasks);
    const auto completed = LoadJournal(options.journal);
    std::vector<uint64_t> pending;
    for (uint64_t index = 0; index < tasks.size(); ++index) {
      if (!completed.contains(index)) {
        pending.push_back(index);
      }
    }
    if (options.shuffle_seed != 0) {
      std::mt19937_64 generator(options.shuffle_seed);
      std::shuffle(pending.begin(), pending.end(), generator);
    }
    if (!options.near_bits.empty()) {
      std::stable_sort(pending.begin(), pending.end(),
                       [&](uint64_t left, uint64_t right) {
                         return BorderDistance(tasks[left], options.near_bits) <
                                BorderDistance(tasks[right], options.near_bits);
                       });
    }
    if (options.max_tasks > 0 && pending.size() > options.max_tasks) {
      pending.resize(options.max_tasks);
    }

    std::cerr << "tasks_total=" << tasks.size()
              << " completed=" << completed.size()
              << " pending_this_run=" << pending.size()
              << " split_depth=" << options.split_depth
              << " shuffle_seed=" << options.shuffle_seed
              << " near_seed=" << !options.near_bits.empty()
              << " classes_restored=" << global_classes.size() << '\n';
    const auto started = std::chrono::steady_clock::now();

#pragma omp parallel for schedule(dynamic, 1)
    for (uint64_t pending_index = 0; pending_index < pending.size();
         ++pending_index) {
      const uint64_t task_index = pending[pending_index];
      State state = tasks[task_index];
      Counters counters;
      std::set<std::string> answers;
      const auto task_started = std::chrono::steady_clock::now();
      Search(state, counters, answers);
      const double task_elapsed = std::chrono::duration<double>(
                                      std::chrono::steady_clock::now() -
                                      task_started)
                                      .count();
      AppendTask(options.journal, task_index, counters, task_elapsed, answers);
      {
        std::lock_guard<std::mutex> lock(answer_mutex);
        global_classes.insert(answers.begin(), answers.end());
      }
      total_nodes.fetch_add(counters.nodes, std::memory_order_relaxed);
      total_cheap_prunes.fetch_add(counters.cheap_prunes,
                                   std::memory_order_relaxed);
      total_exact_prunes.fetch_add(counters.exact_prunes,
                                   std::memory_order_relaxed);
      const uint64_t done = tasks_finished.fetch_add(1) + 1;
      if ((done & 63U) == 0 || done == pending.size()) {
        const double elapsed = std::chrono::duration<double>(
                                   std::chrono::steady_clock::now() - started)
                                   .count();
        std::lock_guard<std::mutex> lock(answer_mutex);
        std::cerr << "progress=" << done << '/' << pending.size()
                  << " nodes=" << total_nodes.load()
                  << " cheap_prunes=" << total_cheap_prunes.load()
                  << " exact_prunes=" << total_exact_prunes.load()
                  << " classes=" << global_classes.size()
                  << " elapsed=" << elapsed << '\n';
      }
    }

    const double elapsed = std::chrono::duration<double>(
                               std::chrono::steady_clock::now() - started)
                               .count();
    std::cerr << "DONE processed=" << pending.size()
              << " tasks_total=" << tasks.size()
              << " nodes=" << total_nodes.load()
              << " cheap_prunes=" << total_cheap_prunes.load()
              << " exact_prunes=" << total_exact_prunes.load()
              << " classes=" << global_classes.size()
              << " elapsed=" << elapsed << '\n';
    for (const std::string& answer : global_classes) {
      std::cout << answer << '\n';
    }
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return 2;
  }
}

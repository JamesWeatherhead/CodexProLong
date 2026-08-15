#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <mutex>
#include <set>
#include <string>
#include <vector>

#ifdef _OPENMP
#include <omp.h>
#endif

// Exact outside-in branch-and-bound for all length-70 +/-1 sequences whose
// aperiodic autocorrelations have absolute value at most four.
namespace {
constexpr int N = 70;

struct State {
  std::array<int8_t, N> a{};
  std::array<uint8_t, N> used{};
  std::array<int16_t, N> corr{};
  std::array<uint8_t, N> determined{};
  int depth = 0;  // number of fixed pairs at the two ends
};

std::atomic<uint64_t> nodes{0};
std::atomic<uint64_t> prunes{0};
std::atomic<uint64_t> tasks_done{0};
std::mutex answer_mu;
std::set<std::string> answer_classes;

struct Delta {
  int p;
  std::vector<std::pair<int, int>> changes;  // lag, product
};

Delta assign(State& s, int p, int value) {
  Delta d{p, {}};
  s.a[p] = static_cast<int8_t>(value);
  for (int q = 0; q < N; ++q) {
    if (!s.used[q]) continue;
    int lag = std::abs(p - q);
    int product = value * s.a[q];
    s.corr[lag] += product;
    ++s.determined[lag];
    d.changes.emplace_back(lag, product);
  }
  s.used[p] = 1;
  return d;
}

void undo(State& s, const Delta& d) {
  s.used[d.p] = 0;
  for (const auto& [lag, product] : d.changes) {
    s.corr[lag] -= product;
    --s.determined[lag];
  }
}

bool feasible(const State& s) {
  for (int lag = 1; lag < N; ++lag) {
    int remaining = (N - lag) - s.determined[lag];
    if (std::abs(s.corr[lag]) > 4 + remaining) return false;
  }
  return true;
}

std::string transformed(const State& s, bool reverse, bool alternate,
                        bool negate) {
  std::string out;
  out.reserve(N);
  for (int i = 0; i < N; ++i) {
    int j = reverse ? N - 1 - i : i;
    int v = s.a[j];
    if (alternate && (i & 1)) v = -v;
    if (negate) v = -v;
    out.push_back(v > 0 ? '1' : '0');
  }
  return out;
}

std::string canonical(const State& s) {
  std::string best(N, '2');
  for (bool r : {false, true})
    for (bool a : {false, true})
      for (bool n : {false, true})
        best = std::min(best, transformed(s, r, a, n));
  return best;
}

void dfs(State& s) {
  nodes.fetch_add(1, std::memory_order_relaxed);
  if (s.depth == N / 2) {
    std::string key = canonical(s);
    std::lock_guard<std::mutex> lock(answer_mu);
    if (answer_classes.insert(key).second) {
      std::cout << "FOUND class=" << answer_classes.size() << " bits=" << key
                << std::endl;
    }
    return;
  }

  int left = s.depth;
  int right = N - 1 - s.depth;
  for (int lv : {-1, 1}) {
    for (int rv : {-1, 1}) {
      // Reversal symmetry after fixed equal endpoints: at the first differing
      // inner pair require left < right. Equal prefixes remain undecided.
      if (s.depth == 1 && lv > rv) continue;
      Delta dl = assign(s, left, lv);
      Delta dr = assign(s, right, rv);
      ++s.depth;
      if (feasible(s)) {
        dfs(s);
      } else {
        prunes.fetch_add(1, std::memory_order_relaxed);
      }
      --s.depth;
      undo(s, dr);
      undo(s, dl);
    }
  }
}

void make_tasks(State& s, int split_depth, std::vector<State>& tasks) {
  if (s.depth == split_depth) {
    tasks.push_back(s);
    return;
  }
  int left = s.depth;
  int right = N - 1 - s.depth;
  for (int lv : {-1, 1}) {
    for (int rv : {-1, 1}) {
      if (s.depth == 1 && lv > rv) continue;
      Delta dl = assign(s, left, lv);
      Delta dr = assign(s, right, rv);
      ++s.depth;
      if (feasible(s)) make_tasks(s, split_depth, tasks);
      --s.depth;
      undo(s, dr);
      undo(s, dl);
    }
  }
}
}  // namespace

int main(int argc, char** argv) {
  int split_depth = argc > 1 ? std::atoi(argv[1]) : 8;
  State root;
  // Global sign + alternation normalize both endpoints for even N.
  assign(root, 0, 1);
  assign(root, N - 1, 1);
  root.depth = 1;

  std::vector<State> tasks;
  make_tasks(root, split_depth, tasks);
  std::cerr << "tasks=" << tasks.size() << " split_depth=" << split_depth
            << std::endl;
  auto start = std::chrono::steady_clock::now();

#pragma omp parallel for schedule(dynamic, 1)
  for (size_t i = 0; i < tasks.size(); ++i) {
    State local = tasks[i];
    dfs(local);
    uint64_t done = tasks_done.fetch_add(1) + 1;
    if ((done & 255) == 0 || done == tasks.size()) {
      double sec = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
      std::cerr << "progress=" << done << "/" << tasks.size()
                << " nodes=" << nodes.load() << " prunes=" << prunes.load()
                << " classes=" << answer_classes.size() << " sec=" << sec
                << std::endl;
    }
  }

  double sec = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
  std::cerr << "DONE nodes=" << nodes.load() << " prunes=" << prunes.load()
            << " classes=" << answer_classes.size() << " sec=" << sec
            << std::endl;
  return answer_classes.size() == 72 ? 0 : 2;
}

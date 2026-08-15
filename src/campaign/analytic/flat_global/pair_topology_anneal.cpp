// Global centered-pair topology search for EinsteinArena flat-polynomials.
//
// The 70 coefficients are represented by 35 four-state centered pairs:
//   (++), (--), (+-), (-+).
// Equal pairs are cosine terms and opposite pairs are sine terms after the
// harmless global half-integer phase.  Every chain is initialized outside the
// exhausted radius-six incumbent ball and is forbidden from re-entering any
// incumbent symmetry ball.  Large topology moves discover a basin; small
// moves only polish after that global jump.

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <mutex>
#include <numeric>
#include <random>
#include <string>
#include <thread>
#include <vector>

using PairState = std::array<uint8_t, 35>;
using Coeffs = std::array<int8_t, 70>;

namespace {

constexpr double kPi = 3.141592653589793238462643383279502884;
constexpr double kNorm = 8.426149773176359;  // sqrt(71)
constexpr double kLeader = 1.2807274949642549;
constexpr double kGate = 1.280726494964255;

constexpr Coeffs kIncumbent = {
    -1, 1,-1, 1,-1, 1,-1, 1,-1, 1, 1, 1, 1, 1, 1,-1,-1,-1,
    -1,-1,-1,-1,-1, 1, 1,-1,-1, 1, 1,-1,-1, 1,-1, 1, 1,-1,
     1, 1,-1,-1, 1, 1, 1, 1, 1, 1,-1,-1, 1, 1, 1, 1, 1,-1,
    -1, 1, 1, 1,-1,-1, 1,-1, 1, 1,-1, 1,-1, 1, 1,-1};

constexpr Coeffs kOldLeader = {
    -1,-1, 1,-1,-1, 1,-1,-1, 1,-1,-1, 1,-1,-1, 1,-1,-1, 1,
     1, 1,-1, 1, 1, 1, 1, 1,-1,-1, 1, 1, 1,-1, 1, 1,-1, 1,
    -1, 1,-1,-1, 1,-1, 1, 1, 1, 1,-1, 1, 1, 1,-1,-1,-1, 1,
    -1, 1,-1, 1,-1,-1,-1, 1, 1, 1, 1, 1, 1,-1,-1,-1};

struct Tables {
  int grid = 0;
  // [pair][state][grid], separated real and imaginary planes.
  std::vector<float> re;
  std::vector<float> im;

  size_t index(int pair, int state, int point) const {
    return (static_cast<size_t>(pair) * 4 + state) * grid + point;
  }
};

struct Score {
  double objective = std::numeric_limits<double>::infinity();
  double max2 = std::numeric_limits<double>::infinity();
};

struct SharedBest {
  std::mutex mutex;
  PairState state{};
  Coeffs coefficients{};
  double fine_score = std::numeric_limits<double>::infinity();
  double coarse_score = std::numeric_limits<double>::infinity();
  double objective = std::numeric_limits<double>::infinity();
  uint64_t proposals = 0;
  uint64_t accepted = 0;
  uint64_t validations = 0;
  int min_incumbent_distance = 0;
  std::string source = "no-distant-candidate-yet";
};

PairState to_state(const Coeffs& c) {
  PairState out{};
  for (int j = 0; j < 35; ++j) {
    const int left = c[j];
    const int right = c[69 - j];
    if (left == 1 && right == 1) out[j] = 0;
    else if (left == -1 && right == -1) out[j] = 1;
    else if (left == 1 && right == -1) out[j] = 2;
    else out[j] = 3;
  }
  return out;
}

Coeffs to_coefficients(const PairState& state) {
  Coeffs out{};
  for (int j = 0; j < 35; ++j) {
    switch (state[j]) {
      case 0: out[j] = 1; out[69 - j] = 1; break;
      case 1: out[j] = -1; out[69 - j] = -1; break;
      case 2: out[j] = 1; out[69 - j] = -1; break;
      default: out[j] = -1; out[69 - j] = 1; break;
    }
  }
  return out;
}

std::vector<Coeffs> incumbent_orbit() {
  std::vector<Coeffs> out;
  for (int reverse = 0; reverse < 2; ++reverse) {
    for (int sign : {-1, 1}) {
      for (int alternating = 0; alternating < 2; ++alternating) {
        Coeffs z{};
        for (int j = 0; j < 70; ++j) {
          const int src = reverse ? 69 - j : j;
          const int alt = alternating && (j & 1) ? -1 : 1;
          z[j] = static_cast<int8_t>(sign * alt * kIncumbent[src]);
        }
        out.push_back(z);
      }
    }
  }
  return out;
}

int minimum_distance(const Coeffs& c, const std::vector<Coeffs>& orbit) {
  int best = 70;
  for (const auto& z : orbit) {
    int distance = 0;
    for (int j = 0; j < 70; ++j) distance += c[j] != z[j];
    best = std::min(best, distance);
  }
  return best;
}

Tables make_tables(int grid) {
  Tables t;
  t.grid = grid;
  t.re.resize(static_cast<size_t>(35) * 4 * grid);
  t.im.resize(static_cast<size_t>(35) * 4 * grid);
  for (int j = 0; j < 35; ++j) {
    const double d = 34.5 - j;
    for (int k = 0; k < grid; ++k) {
      const double theta = 2.0 * kPi * k / grid;
      const float cosine = static_cast<float>(2.0 * std::cos(d * theta));
      const float sine = static_cast<float>(2.0 * std::sin(d * theta));
      t.re[t.index(j, 0, k)] = cosine;
      t.re[t.index(j, 1, k)] = -cosine;
      t.re[t.index(j, 2, k)] = 0.0f;
      t.re[t.index(j, 3, k)] = 0.0f;
      t.im[t.index(j, 0, k)] = 0.0f;
      t.im[t.index(j, 1, k)] = 0.0f;
      t.im[t.index(j, 2, k)] = sine;
      t.im[t.index(j, 3, k)] = -sine;
    }
  }
  return t;
}

void build_curve(const PairState& state, const Tables& table,
                 std::vector<float>& re, std::vector<float>& im) {
  std::fill(re.begin(), re.end(), 0.0f);
  std::fill(im.begin(), im.end(), 0.0f);
  for (int j = 0; j < 35; ++j) {
    const size_t base = table.index(j, state[j], 0);
    for (int k = 0; k < table.grid; ++k) {
      re[k] += table.re[base + k];
      im[k] += table.im[base + k];
    }
  }
}

Score curve_score(const std::vector<float>& re, const std::vector<float>& im) {
  // A shallow top-eight bundle discourages peak swapping while preserving the
  // literal maximum as the dominant term.
  std::array<float, 8> top{};
  for (size_t k = 0; k < re.size(); ++k) {
    const float value = re[k] * re[k] + im[k] * im[k];
    if (value <= top[7]) continue;
    int p = 7;
    while (p > 0 && value > top[p - 1]) {
      top[p] = top[p - 1];
      --p;
    }
    top[p] = value;
  }
  double mean = 0.0;
  for (float x : top) mean += x;
  mean /= top.size();
  return {static_cast<double>(top[0]) + 0.025 * mean,
          static_cast<double>(top[0])};
}

Score proposed_score(const PairState& state, const std::vector<int>& changed,
                     const std::vector<uint8_t>& replacements,
                     const Tables& table, const std::vector<float>& re,
                     const std::vector<float>& im) {
  std::array<float, 8> top{};
  for (int k = 0; k < table.grid; ++k) {
    float rr = re[k];
    float ii = im[k];
    for (size_t q = 0; q < changed.size(); ++q) {
      const int j = changed[q];
      rr += table.re[table.index(j, replacements[q], k)] -
            table.re[table.index(j, state[j], k)];
      ii += table.im[table.index(j, replacements[q], k)] -
            table.im[table.index(j, state[j], k)];
    }
    const float value = rr * rr + ii * ii;
    if (value <= top[7]) continue;
    int p = 7;
    while (p > 0 && value > top[p - 1]) {
      top[p] = top[p - 1];
      --p;
    }
    top[p] = value;
  }
  double mean = 0.0;
  for (float x : top) mean += x;
  mean /= top.size();
  return {static_cast<double>(top[0]) + 0.025 * mean,
          static_cast<double>(top[0])};
}

void apply_change(PairState& state, const std::vector<int>& changed,
                  const std::vector<uint8_t>& replacements,
                  const Tables& table, std::vector<float>& re,
                  std::vector<float>& im) {
  for (size_t q = 0; q < changed.size(); ++q) {
    const int j = changed[q];
    const uint8_t old = state[j];
    const uint8_t fresh = replacements[q];
    for (int k = 0; k < table.grid; ++k) {
      re[k] += table.re[table.index(j, fresh, k)] -
               table.re[table.index(j, old, k)];
      im[k] += table.im[table.index(j, fresh, k)] -
               table.im[table.index(j, old, k)];
    }
    state[j] = fresh;
  }
}

double dense_score(const Coeffs& c, int grid) {
  double best2 = 0.0;
  for (int k = 0; k < grid; ++k) {
    const double theta = 2.0 * kPi * k / grid;
    const double zr = std::cos(theta);
    const double zi = std::sin(theta);
    double pr = c[0];
    double pi = 0.0;
    for (int j = 1; j < 70; ++j) {
      const double nr = pr * zr - pi * zi + c[j];
      pi = pr * zi + pi * zr;
      pr = nr;
    }
    best2 = std::max(best2, pr * pr + pi * pi);
  }
  return std::sqrt(best2) / kNorm;
}

int legendre(int a, int p) {
  a %= p;
  if (a < 0) a += p;
  if (a == 0) return 0;
  int64_t result = 1;
  int64_t base = a;
  int exponent = (p - 1) / 2;
  while (exponent) {
    if (exponent & 1) result = result * base % p;
    base = base * base % p;
    exponent >>= 1;
  }
  return result == 1 ? 1 : -1;
}

bool prime(int p) {
  if (p < 2) return false;
  for (int d = 2; d * d <= p; ++d) if (p % d == 0) return false;
  return true;
}

std::vector<PairState> make_seeds(const Tables& table) {
  std::vector<PairState> seeds{to_state(kIncumbent), to_state(kOldLeader)};

  // Shifted Fekete/Legendre families around and above the target length.
  for (int p = 67; p <= 257; ++p) {
    if (!prime(p)) continue;
    for (int shift = 0; shift < p; ++shift) {
      for (int zero_sign : {-1, 1}) {
        Coeffs c{};
        for (int j = 0; j < 70; ++j) {
          int value = legendre(j + shift, p);
          c[j] = value == 0 ? zero_sign : value;
        }
        seeds.push_back(to_state(c));
      }
    }
  }

  // Rudin-Shapiro length-128 windows and their pair-topology recombinations
  // with the incumbent signs.
  std::vector<int> p{1}, q{1};
  for (int level = 0; level < 7; ++level) {
    std::vector<int> np = p, nq = p;
    np.insert(np.end(), q.begin(), q.end());
    for (int x : q) nq.push_back(-x);
    p.swap(np); q.swap(nq);
  }
  for (const auto* source : {&p, &q}) {
    for (int start = 0; start + 70 <= 128; ++start) {
      Coeffs c{};
      for (int j = 0; j < 70; ++j) c[j] = (*source)[start + j];
      seeds.push_back(to_state(c));
      PairState mixed = to_state(kIncumbent);
      const PairState rs = to_state(c);
      for (int j = 0; j < 35; ++j) {
        // Preserve the RS cosine/sine type while retaining incumbent left sign.
        const bool rs_symmetric = rs[j] < 2;
        const bool incumbent_left_positive = mixed[j] == 0 || mixed[j] == 2;
        mixed[j] = rs_symmetric
            ? (incumbent_left_positive ? 0 : 1)
            : (incumbent_left_positive ? 2 : 3);
      }
      seeds.push_back(mixed);
    }
  }

  // Retain only the best distinct coarse seeds.
  struct Ranked { double value; PairState state; };
  std::vector<Ranked> ranked;
  std::vector<float> re(table.grid), im(table.grid);
  for (const auto& state : seeds) {
    build_curve(state, table, re, im);
    ranked.push_back({curve_score(re, im).objective, state});
  }
  std::sort(ranked.begin(), ranked.end(),
            [](const Ranked& a, const Ranked& b) { return a.value < b.value; });
  std::vector<PairState> result;
  for (const auto& row : ranked) {
    if (std::find(result.begin(), result.end(), row.state) == result.end()) {
      result.push_back(row.state);
      if (result.size() == 128) break;
    }
  }
  return result;
}

void atomic_checkpoint(const std::string& path, const SharedBest& best,
                       uint64_t seed, int grid, int threads, double elapsed,
                       bool complete) {
  const std::string temporary = path + ".tmp";
  std::ofstream out(temporary, std::ios::trunc);
  out << std::setprecision(17);
  out << "{\n";
  out << "  \"schema\": 1,\n";
  out << "  \"complete\": " << (complete ? "true" : "false") << ",\n";
  out << "  \"verifier_sha256\": \"ff991bd84aec2b5b5d44f58a68dba00f961e01d517ec1de3225e0902f0f2fce2\",\n";
  out << "  \"leader_score\": " << kLeader << ",\n";
  out << "  \"gate_score\": " << kGate << ",\n";
  out << "  \"seed\": " << seed << ",\n";
  out << "  \"grid\": " << grid << ",\n";
  out << "  \"threads\": " << threads << ",\n";
  out << "  \"elapsed_seconds\": " << elapsed << ",\n";
  out << "  \"proposals\": " << best.proposals << ",\n";
  out << "  \"accepted\": " << best.accepted << ",\n";
  out << "  \"fine_validations\": " << best.validations << ",\n";
  out << "  \"best_fine_score\": " << best.fine_score << ",\n";
  out << "  \"best_coarse_score\": " << best.coarse_score << ",\n";
  out << "  \"best_objective\": " << best.objective << ",\n";
  out << "  \"minimum_incumbent_orbit_distance\": "
      << best.min_incumbent_distance << ",\n";
  out << "  \"source\": \"" << best.source << "\",\n";
  out << "  \"coefficients\": [";
  for (int j = 0; j < 70; ++j) {
    if (j) out << ',';
    out << static_cast<int>(best.coefficients[j]);
  }
  out << "]\n}\n";
  out.close();
  std::rename(temporary.c_str(), path.c_str());
}

}  // namespace

int main(int argc, char** argv) {
  int seconds = 180;
  int threads = std::max(1u, std::thread::hardware_concurrency());
  int grid = 1024;
  uint64_t master_seed = 2026081501ULL;
  std::string checkpoint = "pair_topology_checkpoint.json";
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    if (arg == "--seconds" && i + 1 < argc) seconds = std::atoi(argv[++i]);
    else if (arg == "--threads" && i + 1 < argc) threads = std::atoi(argv[++i]);
    else if (arg == "--grid" && i + 1 < argc) grid = std::atoi(argv[++i]);
    else if (arg == "--seed" && i + 1 < argc) master_seed = std::strtoull(argv[++i], nullptr, 10);
    else if (arg == "--checkpoint" && i + 1 < argc) checkpoint = argv[++i];
    else {
      std::cerr << "unknown/incomplete argument: " << arg << "\n";
      return 2;
    }
  }
  if (seconds < 1 || threads < 1 || grid < 128) return 2;

  const Tables table = make_tables(grid);
  const auto orbit = incumbent_orbit();
  const auto seeds = make_seeds(table);
  std::cerr << "pair seeds=" << seeds.size() << " grid=" << grid
            << " threads=" << threads << " seconds=" << seconds << "\n";

  SharedBest best;
  best.state = to_state(kIncumbent);
  best.coefficients = kIncumbent;

  std::atomic<bool> stop{false};
  std::atomic<uint64_t> proposals{0}, accepted{0}, validations{0};
  const auto began = std::chrono::steady_clock::now();
  const auto deadline = began + std::chrono::seconds(seconds);
  std::vector<std::thread> workers;

  for (int worker = 0; worker < threads; ++worker) {
    workers.emplace_back([&, worker] {
      std::mt19937_64 rng(master_seed + 0x9e3779b97f4a7c15ULL * (worker + 1));
      std::uniform_real_distribution<double> uniform(0.0, 1.0);
      std::uniform_int_distribution<int> pair_pick(0, 34);
      std::uniform_int_distribution<int> state_pick(0, 3);
      std::vector<float> re(grid), im(grid);
      uint64_t local_proposals = 0, local_accepted = 0;

      while (!stop.load(std::memory_order_relaxed)) {
        PairState state = seeds[rng() % seeds.size()];
        // Mandatory global basin jump: alter 8--20 distinct pair states.
        const int jump = 8 + static_cast<int>(rng() % 13);
        std::vector<int> changed;
        while (static_cast<int>(changed.size()) < jump) {
          const int j = pair_pick(rng);
          if (std::find(changed.begin(), changed.end(), j) == changed.end()) changed.push_back(j);
        }
        for (int j : changed) {
          uint8_t fresh = state_pick(rng);
          while (fresh == state[j]) fresh = state_pick(rng);
          state[j] = fresh;
        }
        Coeffs coefficients = to_coefficients(state);
        if (minimum_distance(coefficients, orbit) < 7) continue;
        build_curve(state, table, re, im);
        Score score = curve_score(re, im);

        constexpr int kEpoch = 160000;
        for (int step = 0; step < kEpoch && !stop.load(std::memory_order_relaxed); ++step) {
          const double fraction = static_cast<double>(step) / (kEpoch - 1);
          const double temperature = 5.0 * std::pow(0.0008, fraction) + 0.002;
          int count;
          const double draw = uniform(rng);
          if (draw < 0.06) count = 7 + static_cast<int>(rng() % 8);       // topology hop
          else if (draw < 0.28) count = 2 + static_cast<int>(rng() % 4);  // bundle move
          else count = 1;                                                 // distant-basin polish

          changed.clear();
          while (static_cast<int>(changed.size()) < count) {
            const int j = pair_pick(rng);
            if (std::find(changed.begin(), changed.end(), j) == changed.end()) changed.push_back(j);
          }
          std::vector<uint8_t> replacements;
          replacements.reserve(changed.size());
          for (int j : changed) {
            uint8_t fresh = state_pick(rng);
            while (fresh == state[j]) fresh = state_pick(rng);
            replacements.push_back(fresh);
          }
          PairState proposed_state = state;
          for (size_t q = 0; q < changed.size(); ++q) proposed_state[changed[q]] = replacements[q];
          const Coeffs proposed_coefficients = to_coefficients(proposed_state);
          if (minimum_distance(proposed_coefficients, orbit) < 7) continue;

          const Score proposed = proposed_score(state, changed, replacements, table, re, im);
          ++local_proposals;
          const double delta = proposed.objective - score.objective;
          if (delta <= 0.0 || uniform(rng) < std::exp(-delta / temperature)) {
            apply_change(state, changed, replacements, table, re, im);
            score = proposed;
            ++local_accepted;

            const double coarse = std::sqrt(score.max2) / kNorm;
            bool should_validate = coarse < 1.50;
            {
              std::lock_guard<std::mutex> lock(best.mutex);
              should_validate = should_validate &&
                  (coarse < best.coarse_score || score.objective < best.objective);
            }
            if (should_validate) {
              ++validations;
              const Coeffs candidate = to_coefficients(state);
              const double fine = dense_score(candidate, 65536);
              std::lock_guard<std::mutex> lock(best.mutex);
              if (fine < best.fine_score ||
                  (fine == best.fine_score && score.objective < best.objective)) {
                best.state = state;
                best.coefficients = candidate;
                best.fine_score = fine;
                best.coarse_score = coarse;
                best.objective = score.objective;
                best.min_incumbent_distance = minimum_distance(candidate, orbit);
                best.source = "centered-pair-global-anneal-worker-" + std::to_string(worker);
                std::cerr << std::setprecision(17)
                          << "NEW fine=" << fine << " coarse=" << coarse
                          << " dist=" << best.min_incumbent_distance
                          << " proposals=" << (proposals.load() + local_proposals) << "\n";
                if (fine < kGate - 2e-8) stop.store(true);
              }
            }
          }
          if ((local_proposals & 0x3fff) == 0) {
            proposals.fetch_add(local_proposals); local_proposals = 0;
            accepted.fetch_add(local_accepted); local_accepted = 0;
            if (std::chrono::steady_clock::now() >= deadline) stop.store(true);
          }
        }
      }
      proposals.fetch_add(local_proposals);
      accepted.fetch_add(local_accepted);
    });
  }

  while (!stop.load()) {
    std::this_thread::sleep_for(std::chrono::seconds(2));
    if (std::chrono::steady_clock::now() >= deadline) stop.store(true);
    SharedBest snapshot;
    {
      std::lock_guard<std::mutex> lock(best.mutex);
      best.proposals = proposals.load();
      best.accepted = accepted.load();
      best.validations = validations.load();
      atomic_checkpoint(checkpoint, best, master_seed, grid, threads,
          std::chrono::duration<double>(std::chrono::steady_clock::now() - began).count(), false);
    }
  }
  for (auto& thread : workers) thread.join();
  {
    std::lock_guard<std::mutex> lock(best.mutex);
    best.proposals = proposals.load();
    best.accepted = accepted.load();
    best.validations = validations.load();
    atomic_checkpoint(checkpoint, best, master_seed, grid, threads,
        std::chrono::duration<double>(std::chrono::steady_clock::now() - began).count(), true);
    std::cout << std::setprecision(17) << "best_fine=" << best.fine_score
              << " coarse=" << best.coarse_score
              << " distance=" << best.min_incumbent_distance
              << " proposals=" << best.proposals
              << " validations=" << best.validations << "\n";
  }
  return 0;
}

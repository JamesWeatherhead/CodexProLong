// Heuristic search on the first *unclosed* Hamming shells (r >= 7) around
// the live flat-polynomial incumbent.  Radius <= 6 is deliberately excluded:
// that ball was already exhaustively certified empty.  Swap moves preserve a
// shell, so every evaluated construction is globally outside the certificate.

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

using Coeffs = std::array<int8_t, 70>;
constexpr double kPi = 3.141592653589793238462643383279502884;
constexpr double kNorm = 8.426149773176359;
constexpr double kLeader = 1.2807274949642549;
constexpr double kGate = 1.280726494964255;
constexpr Coeffs kLeaderCoefficients = {
    -1, 1,-1, 1,-1, 1,-1, 1,-1, 1, 1, 1, 1, 1, 1,-1,-1,-1,
    -1,-1,-1,-1,-1, 1, 1,-1,-1, 1, 1,-1,-1, 1,-1, 1, 1,-1,
     1, 1,-1,-1, 1, 1, 1, 1, 1, 1,-1,-1, 1, 1, 1, 1, 1,-1,
    -1, 1, 1, 1,-1,-1, 1,-1, 1, 1,-1, 1,-1, 1, 1,-1};

struct Tables {
  int points = 0;
  std::vector<float> re, im;
  size_t at(int coefficient, int point) const {
    return static_cast<size_t>(coefficient) * points + point;
  }
};

struct Score { double objective, max2; };

struct Best {
  std::mutex mutex;
  Coeffs coefficients = kLeaderCoefficients;
  double witness_score = std::numeric_limits<double>::infinity();
  double fine_score = std::numeric_limits<double>::infinity();
  double objective = std::numeric_limits<double>::infinity();
  int radius = 0;
  uint64_t proposals = 0, accepted = 0, validations = 0;
};

Tables make_tables(int uniform_grid) {
  // Uniform coverage plus literal million-grid locations of the incumbent's
  // strongest peak bundles.  The latter remove the sampling slack that made a
  // coarse-only radius-six survivor misleading in the completed audit.
  std::vector<double> angles;
  angles.reserve(uniform_grid + 32);
  for (int k = 0; k < uniform_grid; ++k)
    angles.push_back(2.0 * kPi * k / uniform_grid);
  constexpr int literal_indices[] = {
      54327, 131846, 154894, 256809, 278884, 344454, 377831, 415768,
      466443, 533556, 584231, 622168, 655545, 721115, 73032, 743190,
      845105, 868153, 926967, 945672};
  for (int index : literal_indices)
    angles.push_back(2.0 * kPi * index / 999999.0);

  Tables table;
  table.points = static_cast<int>(angles.size());
  table.re.resize(static_cast<size_t>(70) * table.points);
  table.im.resize(static_cast<size_t>(70) * table.points);
  for (int j = 0; j < 70; ++j) {
    const int exponent = 69 - j;
    for (int k = 0; k < table.points; ++k) {
      table.re[table.at(j, k)] = std::cos(exponent * angles[k]);
      table.im[table.at(j, k)] = std::sin(exponent * angles[k]);
    }
  }
  return table;
}

void build_curve(const std::array<uint8_t, 70>& flipped, const Tables& table,
                 std::vector<float>& re, std::vector<float>& im) {
  std::fill(re.begin(), re.end(), 0.0f);
  std::fill(im.begin(), im.end(), 0.0f);
  for (int j = 0; j < 70; ++j) {
    const float sign = flipped[j] ? -kLeaderCoefficients[j] : kLeaderCoefficients[j];
    for (int k = 0; k < table.points; ++k) {
      re[k] += sign * table.re[table.at(j, k)];
      im[k] += sign * table.im[table.at(j, k)];
    }
  }
}

Score score_curve(const std::vector<float>& re, const std::vector<float>& im) {
  std::array<float, 12> top{};
  for (size_t k = 0; k < re.size(); ++k) {
    const float value = re[k] * re[k] + im[k] * im[k];
    if (value <= top.back()) continue;
    int p = static_cast<int>(top.size()) - 1;
    while (p > 0 && value > top[p - 1]) { top[p] = top[p - 1]; --p; }
    top[p] = value;
  }
  double mean = std::accumulate(top.begin(), top.end(), 0.0) / top.size();
  return {top[0] + 0.02 * mean, top[0]};
}

Score proposed_score(const std::vector<int>& turn_off,
                     const std::vector<int>& turn_on,
                     const Tables& table, const std::vector<float>& re,
                     const std::vector<float>& im) {
  std::array<float, 12> top{};
  for (int k = 0; k < table.points; ++k) {
    float rr = re[k], ii = im[k];
    for (int j : turn_off) {
      const float delta = 2.0f * kLeaderCoefficients[j];
      rr += delta * table.re[table.at(j, k)];
      ii += delta * table.im[table.at(j, k)];
    }
    for (int j : turn_on) {
      const float delta = -2.0f * kLeaderCoefficients[j];
      rr += delta * table.re[table.at(j, k)];
      ii += delta * table.im[table.at(j, k)];
    }
    const float value = rr * rr + ii * ii;
    if (value <= top.back()) continue;
    int p = static_cast<int>(top.size()) - 1;
    while (p > 0 && value > top[p - 1]) { top[p] = top[p - 1]; --p; }
    top[p] = value;
  }
  double mean = std::accumulate(top.begin(), top.end(), 0.0) / top.size();
  return {top[0] + 0.02 * mean, top[0]};
}

void apply(std::array<uint8_t, 70>& flipped,
           const std::vector<int>& turn_off, const std::vector<int>& turn_on,
           const Tables& table, std::vector<float>& re, std::vector<float>& im) {
  for (int j : turn_off) {
    const float delta = 2.0f * kLeaderCoefficients[j];
    for (int k = 0; k < table.points; ++k) {
      re[k] += delta * table.re[table.at(j, k)];
      im[k] += delta * table.im[table.at(j, k)];
    }
    flipped[j] = 0;
  }
  for (int j : turn_on) {
    const float delta = -2.0f * kLeaderCoefficients[j];
    for (int k = 0; k < table.points; ++k) {
      re[k] += delta * table.re[table.at(j, k)];
      im[k] += delta * table.im[table.at(j, k)];
    }
    flipped[j] = 1;
  }
}

Coeffs coefficients(const std::array<uint8_t, 70>& flipped) {
  Coeffs result{};
  for (int j = 0; j < 70; ++j)
    result[j] = flipped[j] ? -kLeaderCoefficients[j] : kLeaderCoefficients[j];
  return result;
}

double dense_score(const Coeffs& c, int grid) {
  double best2 = 0.0;
  for (int k = 0; k < grid; ++k) {
    const double theta = 2.0 * kPi * k / grid;
    const double zr = std::cos(theta), zi = std::sin(theta);
    double pr = c[0], pi = 0.0;
    for (int j = 1; j < 70; ++j) {
      const double nr = pr * zr - pi * zi + c[j];
      pi = pr * zi + pi * zr;
      pr = nr;
    }
    best2 = std::max(best2, pr * pr + pi * pi);
  }
  return std::sqrt(best2) / kNorm;
}

void checkpoint(const std::string& path, const Best& best, uint64_t seed,
                int grid, int threads, double elapsed, bool complete) {
  std::ofstream out(path + ".tmp", std::ios::trunc);
  out << std::setprecision(17)
      << "{\n  \"schema\": 1,\n  \"complete\": " << (complete ? "true" : "false")
      << ",\n  \"verifier_sha256\": \"ff991bd84aec2b5b5d44f58a68dba00f961e01d517ec1de3225e0902f0f2fce2\",\n"
      << "  \"leader_score\": " << kLeader << ",\n"
      << "  \"gate_score\": " << kGate << ",\n"
      << "  \"seed\": " << seed << ",\n  \"uniform_grid\": " << grid
      << ",\n  \"threads\": " << threads << ",\n  \"elapsed_seconds\": " << elapsed
      << ",\n  \"proposals\": " << best.proposals << ",\n  \"accepted\": " << best.accepted
      << ",\n  \"validations\": " << best.validations
      << ",\n  \"best_radius\": " << best.radius
      << ",\n  \"best_witness_score\": " << best.witness_score
      << ",\n  \"best_fine_score\": " << best.fine_score
      << ",\n  \"best_objective\": " << best.objective << ",\n  \"coefficients\": [";
  for (int j = 0; j < 70; ++j) { if (j) out << ','; out << int(best.coefficients[j]); }
  out << "]\n}\n";
  out.close();
  std::rename((path + ".tmp").c_str(), path.c_str());
}

int main(int argc, char** argv) {
  int seconds = 180, threads = std::max(1u, std::thread::hardware_concurrency());
  int grid = 1024;
  uint64_t seed = 2026081503ULL;
  std::string path = "radius_frontier_checkpoint.json";
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    if (arg == "--seconds" && i + 1 < argc) seconds = std::atoi(argv[++i]);
    else if (arg == "--threads" && i + 1 < argc) threads = std::atoi(argv[++i]);
    else if (arg == "--grid" && i + 1 < argc) grid = std::atoi(argv[++i]);
    else if (arg == "--seed" && i + 1 < argc) seed = std::strtoull(argv[++i], nullptr, 10);
    else if (arg == "--checkpoint" && i + 1 < argc) path = argv[++i];
    else return 2;
  }
  const Tables table = make_tables(grid);
  Best best;
  std::atomic<bool> stop{false};
  std::atomic<uint64_t> proposals{0}, accepted{0}, validations{0};
  const auto began = std::chrono::steady_clock::now();
  const auto deadline = began + std::chrono::seconds(seconds);
  std::vector<std::thread> pool;

  for (int worker = 0; worker < threads; ++worker) {
    pool.emplace_back([&, worker] {
      const int radius = 7 + worker % 8;  // two chains per shell with 16 cores
      std::mt19937_64 rng(seed + 0x9e3779b97f4a7c15ULL * (worker + 1));
      std::uniform_real_distribution<double> uniform(0.0, 1.0);
      uint64_t local_proposals = 0, local_accepted = 0;
      std::vector<float> re(table.points), im(table.points);

      while (!stop.load(std::memory_order_relaxed)) {
        std::array<uint8_t, 70> flipped{};
        std::array<int, 70> order{};
        std::iota(order.begin(), order.end(), 0);
        std::shuffle(order.begin(), order.end(), rng);
        for (int j = 0; j < radius; ++j) flipped[order[j]] = 1;
        build_curve(flipped, table, re, im);
        Score score = score_curve(re, im);

        constexpr int kEpoch = 120000;
        for (int step = 0; step < kEpoch && !stop.load(std::memory_order_relaxed); ++step) {
          const double fraction = double(step) / (kEpoch - 1);
          const double temperature = 6.0 * std::pow(0.0005, fraction) + 0.001;
          const int swaps = uniform(rng) < 0.12 ? 2 : 1;
          std::vector<int> off, on;
          while (int(off.size()) < swaps) {
            int j = rng() % 70;
            if (flipped[j] && std::find(off.begin(), off.end(), j) == off.end()) off.push_back(j);
          }
          while (int(on.size()) < swaps) {
            int j = rng() % 70;
            if (!flipped[j] && std::find(on.begin(), on.end(), j) == on.end()) on.push_back(j);
          }
          const Score fresh = proposed_score(off, on, table, re, im);
          ++local_proposals;
          const double delta = fresh.objective - score.objective;
          if (delta <= 0.0 || uniform(rng) < std::exp(-delta / temperature)) {
            apply(flipped, off, on, table, re, im);
            score = fresh;
            ++local_accepted;
            const double witness = std::sqrt(score.max2) / kNorm;
            bool validate = witness < 1.40;
            {
              std::lock_guard<std::mutex> lock(best.mutex);
              validate = validate && (witness < best.witness_score || score.objective < best.objective);
            }
            if (validate) {
              ++validations;
              const Coeffs c = coefficients(flipped);
              const double fine = dense_score(c, 65536);
              std::lock_guard<std::mutex> lock(best.mutex);
              if (fine < best.fine_score) {
                best.coefficients = c;
                best.witness_score = witness;
                best.fine_score = fine;
                best.objective = score.objective;
                best.radius = radius;
                std::cerr << std::setprecision(17) << "NEW r=" << radius
                          << " witness=" << witness << " fine=" << fine
                          << " proposals=" << proposals.load() + local_proposals << "\n";
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
    std::lock_guard<std::mutex> lock(best.mutex);
    best.proposals = proposals.load(); best.accepted = accepted.load(); best.validations = validations.load();
    checkpoint(path, best, seed, grid, threads,
        std::chrono::duration<double>(std::chrono::steady_clock::now() - began).count(), false);
  }
  for (auto& t : pool) t.join();
  {
    std::lock_guard<std::mutex> lock(best.mutex);
    best.proposals = proposals.load(); best.accepted = accepted.load(); best.validations = validations.load();
    checkpoint(path, best, seed, grid, threads,
        std::chrono::duration<double>(std::chrono::steady_clock::now() - began).count(), true);
    std::cout << std::setprecision(17) << "best_radius=" << best.radius
              << " witness=" << best.witness_score << " fine=" << best.fine_score
              << " proposals=" << best.proposals << " validations=" << best.validations << "\n";
  }
}

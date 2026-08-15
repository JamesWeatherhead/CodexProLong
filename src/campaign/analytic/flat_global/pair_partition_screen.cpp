// Exhaustive centered-pair sign screen for a fixed global pair-type topology.
//
// With center 34.5, an equal-sign pair contributes +/-2 cos(d theta) and an
// opposite-sign pair contributes +/-2i sin(d theta).  For the incumbent's
// 16-cos/19-sin topology, all 2^16 and 2^19 signings can therefore be ranked
// independently before a bounded Cartesian combination screen.  This is a
// global sign-basin search, not a local coefficient-flip search.

#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <limits>
#include <queue>
#include <string>
#include <thread>
#include <utility>
#include <vector>

namespace {
constexpr int N = 70;
constexpr double PI = 3.141592653589793238462643383279502884;
constexpr std::array<int8_t, N> LEADER = {
    -1, 1,-1, 1,-1, 1,-1, 1,-1, 1, 1, 1, 1, 1, 1,-1,-1,-1,
    -1,-1,-1,-1,-1, 1, 1,-1,-1, 1, 1,-1,-1, 1,-1, 1, 1,-1,
     1, 1,-1,-1, 1, 1, 1, 1, 1, 1,-1,-1, 1, 1, 1, 1, 1,-1,
    -1, 1, 1, 1,-1,-1, 1,-1, 1, 1,-1, 1,-1, 1, 1,-1};
constexpr std::array<int8_t, N> OLD_LEADER = {
    -1,-1, 1,-1,-1, 1,-1,-1, 1,-1,-1, 1,-1,-1, 1,-1,-1, 1,
     1, 1,-1, 1, 1, 1, 1, 1,-1,-1, 1, 1, 1,-1, 1, 1,-1, 1,
    -1, 1,-1,-1, 1,-1, 1, 1, 1, 1,-1, 1, 1, 1,-1,-1,-1, 1,
    -1, 1,-1, 1,-1,-1,-1, 1, 1, 1, 1, 1, 1,-1,-1,-1};
constexpr std::array<int8_t, N> PSL4_EXAMPLE = {
    -1,-1,-1,-1,-1, 1, 1, 1,-1,-1,-1,-1, 1,-1, 1, 1, 1, 1,
     1, 1, 1, 1, 1, 1,-1, 1,-1, 1,-1,-1, 1,-1, 1,-1, 1, 1,
     1, 1,-1,-1, 1, 1,-1,-1, 1, 1,-1,-1, 1, 1,-1, 1,-1, 1,
    -1, 1, 1,-1,-1, 1,-1, 1, 1,-1,-1, 1,-1, 1, 1,-1};

struct Candidate {
  float component_max;
  uint32_t mask;
};
struct WorseFirst {
  bool operator()(const Candidate& a, const Candidate& b) const {
    return a.component_max < b.component_max;
  }
};

struct Combined {
  float max2;
  uint32_t cos_mask;
  uint32_t sin_mask;
  int pair_distance;
};

std::vector<Candidate> enumerate_component(const std::vector<int>& pairs,
                                           bool sine, int grid, int keep,
                                           uint32_t incumbent_mask,
                                           uint64_t& better_than_incumbent,
                                           float& incumbent_max) {
  const int bits = static_cast<int>(pairs.size());
  const uint32_t total = uint32_t{1} << bits;
  std::vector<float> basis(static_cast<size_t>(bits) * grid);
  std::vector<float> curve(grid, 0.0f);
  for (int q = 0; q < bits; ++q) {
    const double d = 34.5 - pairs[q];
    for (int k = 0; k < grid; ++k) {
      double theta = 2.0 * PI * k / grid;
      float v = static_cast<float>(2.0 * (sine ? std::sin(d * theta)
                                                : std::cos(d * theta)));
      basis[static_cast<size_t>(q) * grid + k] = v;
      curve[k] -= v;  // binary mask zero means sign -1
    }
  }

  auto score = [&]() {
    float best = 0.0f;
    for (float x : curve) best = std::max(best, std::abs(x));
    return best;
  };

  // Determine the incumbent component score first for an exact rank count.
  std::vector<float> incumbent_curve(grid, 0.0f);
  for (int q = 0; q < bits; ++q) {
    float sign = ((incumbent_mask >> q) & 1U) ? 1.0f : -1.0f;
    const float* b = &basis[static_cast<size_t>(q) * grid];
    for (int k = 0; k < grid; ++k) incumbent_curve[k] += sign * b[k];
  }
  incumbent_max = 0.0f;
  for (float x : incumbent_curve) incumbent_max = std::max(incumbent_max, std::abs(x));

  std::priority_queue<Candidate, std::vector<Candidate>, WorseFirst> heap;
  uint32_t previous_gray = 0;
  better_than_incumbent = 0;
  for (uint32_t ordinal = 0; ordinal < total; ++ordinal) {
    uint32_t gray = ordinal ^ (ordinal >> 1);
    if (ordinal) {
      uint32_t changed = gray ^ previous_gray;
      int q = std::countr_zero(changed);
      float delta = ((gray >> q) & 1U) ? 2.0f : -2.0f;
      const float* b = &basis[static_cast<size_t>(q) * grid];
      for (int k = 0; k < grid; ++k) curve[k] += delta * b[k];
    }
    previous_gray = gray;
    float value = score();
    if (value < incumbent_max - 1e-5f) ++better_than_incumbent;
    if (static_cast<int>(heap.size()) < keep) {
      heap.push({value, gray});
    } else if (value < heap.top().component_max) {
      heap.pop();
      heap.push({value, gray});
    }
  }
  std::vector<Candidate> out;
  out.reserve(heap.size());
  while (!heap.empty()) {
    out.push_back(heap.top());
    heap.pop();
  }
  std::sort(out.begin(), out.end(), [](auto& a, auto& b) {
    return a.component_max < b.component_max;
  });
  return out;
}

uint32_t incumbent_mask_for(const std::vector<int>& pairs, bool sine,
                            const std::array<int8_t, N>& base) {
  uint32_t mask = 0;
  for (size_t q = 0; q < pairs.size(); ++q) {
    int j = pairs[q];
    int left = base[j], right = base[N - 1 - j];
    int sign = sine ? left : left;  // (+,-) is +sin; equal (+,+) is +cos.
    if (sign > 0) mask |= uint32_t{1} << q;
    if (sine && left == right) std::abort();
    if (!sine && left != right) std::abort();
  }
  return mask;
}

std::vector<float> make_basis(const std::vector<int>& pairs, bool sine,
                              int grid) {
  std::vector<float> basis(static_cast<size_t>(pairs.size()) * grid);
  for (size_t q = 0; q < pairs.size(); ++q) {
    double d = 34.5 - pairs[q];
    for (int k = 0; k < grid; ++k) {
      double theta = 2.0 * PI * k / grid;
      basis[q * grid + k] = static_cast<float>(
          2.0 * (sine ? std::sin(d * theta) : std::cos(d * theta)));
    }
  }
  return basis;
}

void build_component(uint32_t mask, const std::vector<float>& basis, int bits,
                     int grid, std::vector<float>& curve) {
  std::fill(curve.begin(), curve.end(), 0.0f);
  for (int q = 0; q < bits; ++q) {
    float sign = ((mask >> q) & 1U) ? 1.0f : -1.0f;
    const float* b = &basis[static_cast<size_t>(q) * grid];
    for (int k = 0; k < grid; ++k) curve[k] += sign * b[k];
  }
}

Combined optimize_sine_for_cos(
    uint32_t cos_mask, const std::vector<float>& cos_basis,
    const std::vector<float>& sin_basis, int cos_bits, int sin_bits, int grid,
    uint32_t inc_cos, uint32_t inc_sin, int minimum_pair_distance) {
  std::vector<float> real(grid), imag(grid, 0.0f), real2(grid);
  build_component(cos_mask, cos_basis, cos_bits, grid, real);
  for (int k = 0; k < grid; ++k) real2[k] = real[k] * real[k];
  // Gray mask zero is the all-negative sine signing.
  for (int q = 0; q < sin_bits; ++q) {
    const float* b = &sin_basis[static_cast<size_t>(q) * grid];
    for (int k = 0; k < grid; ++k) imag[k] -= b[k];
  }

  Combined best{std::numeric_limits<float>::infinity(), cos_mask, 0, 999};
  uint32_t previous_gray = 0;
  const uint32_t total = uint32_t{1} << sin_bits;
  for (uint32_t ordinal = 0; ordinal < total; ++ordinal) {
    uint32_t gray = ordinal ^ (ordinal >> 1);
    if (ordinal) {
      int q = std::countr_zero(gray ^ previous_gray);
      float delta = ((gray >> q) & 1U) ? 2.0f : -2.0f;
      const float* b = &sin_basis[static_cast<size_t>(q) * grid];
      for (int k = 0; k < grid; ++k) imag[k] += delta * b[k];
    }
    previous_gray = gray;
    int distance = std::popcount(cos_mask ^ inc_cos) +
                   std::popcount(gray ^ inc_sin);
    if (distance < minimum_pair_distance) continue;
    float value = 0.0f;
    for (int k = 0; k < grid; ++k) {
      value = std::max(value, real2[k] + imag[k] * imag[k]);
      if (value >= best.max2) break;
    }
    if (value < best.max2) best = {value, cos_mask, gray, distance};
  }
  return best;
}

double fine_score(const Combined& c, const std::vector<int>& cosine_pairs,
                  const std::vector<int>& sine_pairs, int grid) {
  auto cb = make_basis(cosine_pairs, false, grid);
  auto sb = make_basis(sine_pairs, true, grid);
  std::vector<float> re(grid), im(grid);
  build_component(c.cos_mask, cb, cosine_pairs.size(), grid, re);
  build_component(c.sin_mask, sb, sine_pairs.size(), grid, im);
  double best2 = 0.0;
  for (int k = 0; k < grid; ++k)
    best2 = std::max(best2, double(re[k]) * re[k] + double(im[k]) * im[k]);
  return std::sqrt(best2) / std::sqrt(71.0);
}

std::array<int8_t, N> coefficients(
    const Combined& c, const std::vector<int>& cosine_pairs,
    const std::vector<int>& sine_pairs) {
  std::array<int8_t, N> out{};
  for (size_t q = 0; q < cosine_pairs.size(); ++q) {
    int v = ((c.cos_mask >> q) & 1U) ? 1 : -1;
    int j = cosine_pairs[q];
    out[j] = out[N - 1 - j] = v;
  }
  for (size_t q = 0; q < sine_pairs.size(); ++q) {
    int v = ((c.sin_mask >> q) & 1U) ? 1 : -1;
    int j = sine_pairs[q];
    out[j] = v;
    out[N - 1 - j] = -v;
  }
  return out;
}
}  // namespace

int main(int argc, char** argv) {
  int grid = argc > 1 ? std::atoi(argv[1]) : 2048;
  int keep_cos = argc > 2 ? std::atoi(argv[2]) : 4096;
  int keep_sin = argc > 3 ? std::atoi(argv[3]) : 8192;
  std::string topology = argc > 4 ? argv[4] : "current";
  std::array<int8_t, N> base = LEADER;
  bool enforce_current_radius = true;
  if (topology == "old") {
    base = OLD_LEADER;
    enforce_current_radius = false;
  } else if (topology == "psl4") {
    base = PSL4_EXAMPLE;
    enforce_current_radius = false;
  } else if (topology.size() == N / 2 &&
             topology.find_first_not_of("CS") == std::string::npos) {
    for (int j = 0; j < N / 2; ++j) {
      base[j] = 1;
      base[N - 1 - j] = topology[j] == 'C' ? 1 : -1;
    }
    enforce_current_radius = false;
  } else if (topology != "current") {
    std::cerr << "topology must be current, old, or psl4\n";
    return 2;
  }
  std::vector<int> cosine_pairs, sine_pairs;
  for (int j = 0; j < N / 2; ++j) {
    if (base[j] == base[N - 1 - j]) cosine_pairs.push_back(j);
    else sine_pairs.push_back(j);
  }
  std::cout << "topology=" << topology << " grid=" << grid
            << " cosine_pairs=" << cosine_pairs.size()
            << " sine_pairs=" << sine_pairs.size() << std::endl;
  auto t0 = std::chrono::steady_clock::now();
  uint64_t cos_better = 0, sin_better = 0;
  float cos_inc = 0, sin_inc = 0;
  auto cos = enumerate_component(cosine_pairs, false, grid, keep_cos,
                                 incumbent_mask_for(cosine_pairs, false, base),
                                 cos_better, cos_inc);
  auto sin = enumerate_component(sine_pairs, true, grid, keep_sin,
                                 incumbent_mask_for(sine_pairs, true, base),
                                 sin_better, sin_inc);
  double sec = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
  std::cout << std::setprecision(9)
            << "cos_inc_max=" << cos_inc << " cos_strict_better=" << cos_better
            << " cos_keep_cutoff=" << cos.back().component_max << '\n'
            << "sin_inc_max=" << sin_inc << " sin_strict_better=" << sin_better
            << " sin_keep_cutoff=" << sin.back().component_max << '\n'
            << "component_elapsed_seconds=" << sec << std::endl;

  const uint32_t inc_cos = incumbent_mask_for(cosine_pairs, false, base);
  const uint32_t inc_sin = incumbent_mask_for(sine_pairs, true, base);
  auto cos_basis = make_basis(cosine_pairs, false, grid);
  auto sin_basis = make_basis(sine_pairs, true, grid);
  std::vector<Combined> combined(cos.size());
  std::atomic<size_t> next{0};
  int threads = std::max(1u, std::thread::hardware_concurrency());
  std::vector<std::thread> workers;
  for (int t = 0; t < threads; ++t) {
    workers.emplace_back([&]() {
      for (;;) {
        size_t i = next.fetch_add(1);
        if (i >= cos.size()) return;
        combined[i] = optimize_sine_for_cos(
            cos[i].mask, cos_basis, sin_basis, cosine_pairs.size(),
            sine_pairs.size(), grid, inc_cos, inc_sin,
            enforce_current_radius ? 4 : 0);
        if (!enforce_current_radius && !std::isfinite(combined[i].max2)) {
          std::abort();
        }
      }
    });
  }
  for (auto& w : workers) w.join();
  std::sort(combined.begin(), combined.end(),
            [](auto& a, auto& b) { return a.max2 < b.max2; });
  double combo_sec = std::chrono::duration<double>(
      std::chrono::steady_clock::now() - t0).count();
  std::cout << "combination_threads=" << threads
            << " combination_elapsed_seconds=" << combo_sec << '\n';
  int report_requested = argc > 5 ? std::atoi(argv[5]) : 20;
  int report = std::min<int>(report_requested, combined.size());
  for (int i = 0; i < report; ++i) {
    double fine = fine_score(combined[i], cosine_pairs, sine_pairs, 65536);
    auto coeff = coefficients(combined[i], cosine_pairs, sine_pairs);
    std::cout << "rank=" << i + 1 << " coarse="
              << std::sqrt(combined[i].max2) / std::sqrt(71.0)
              << " fine65536=" << fine
              << " pair_distance=" << combined[i].pair_distance
              << " cos_mask=" << combined[i].cos_mask
              << " sin_mask=" << combined[i].sin_mask << " coefficients=[";
    for (int j = 0; j < N; ++j) {
      if (j) std::cout << ',';
      std::cout << int(coeff[j]);
    }
    std::cout << "]\n";
  }
  return 0;
}

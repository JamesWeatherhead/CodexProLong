// Exhaustive 4-state block-substitution/crossover families for length 70.
// Each family has ten independent length-7 blocks, hence 4^10 = 1,048,576
// globally changed constructions.  Uniform-grid screening is followed by a
// 65,536-point replay of retained candidates.  Incumbent-orbit distance < 7
// is excluded because that neighborhood has already been exhaustively closed.

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <limits>
#include <mutex>
#include <queue>
#include <string>
#include <thread>
#include <vector>

namespace {
constexpr int N = 70;
constexpr int BLOCK = 7;
constexpr int NB = N / BLOCK;
constexpr double PI = 3.141592653589793238462643383279502884;
using Coeffs = std::array<int8_t, N>;
constexpr Coeffs CURRENT = {
    -1, 1,-1, 1,-1, 1,-1, 1,-1, 1, 1, 1, 1, 1, 1,-1,-1,-1,
    -1,-1,-1,-1,-1, 1, 1,-1,-1, 1, 1,-1,-1, 1,-1, 1, 1,-1,
     1, 1,-1,-1, 1, 1, 1, 1, 1, 1,-1,-1, 1, 1, 1, 1, 1,-1,
    -1, 1, 1, 1,-1,-1, 1,-1, 1, 1,-1, 1,-1, 1, 1,-1};
constexpr Coeffs OLD = {
    -1,-1, 1,-1,-1, 1,-1,-1, 1,-1,-1, 1,-1,-1, 1,-1,-1, 1,
     1, 1,-1, 1, 1, 1, 1, 1,-1,-1, 1, 1, 1,-1, 1, 1,-1, 1,
    -1, 1,-1,-1, 1,-1, 1, 1, 1, 1,-1, 1, 1, 1,-1,-1,-1, 1,
    -1, 1,-1, 1,-1,-1,-1, 1, 1, 1, 1, 1, 1,-1,-1,-1};
constexpr Coeffs PSL4 = {
    -1,-1,-1,-1,-1, 1, 1, 1,-1,-1,-1,-1, 1,-1, 1, 1, 1, 1,
     1, 1, 1, 1, 1, 1,-1, 1,-1, 1,-1,-1, 1,-1, 1,-1, 1, 1,
     1, 1,-1,-1, 1, 1,-1,-1, 1, 1,-1,-1, 1, 1,-1, 1,-1, 1,
    -1, 1, 1,-1,-1, 1,-1, 1, 1,-1,-1, 1,-1, 1, 1,-1};

struct Family {
  std::string name;
  std::array<std::array<std::array<int8_t, BLOCK>, 4>, NB> option{};
};
struct Candidate {
  float coarse2;
  uint32_t code;
  int orbit_distance;
};
struct WorseFirst {
  bool operator()(const Candidate& a, const Candidate& b) const {
    return a.coarse2 < b.coarse2;
  }
};

int legendre(int a, int p) {
  a %= p;
  if (a < 0) a += p;
  if (!a) return 1;
  int64_t base = a, exponent = (p - 1) / 2, result = 1;
  while (exponent) {
    if (exponent & 1) result = result * base % p;
    base = base * base % p;
    exponent >>= 1;
  }
  return result == 1 ? 1 : -1;
}

Coeffs rudin_shapiro_window() {
  std::vector<int> p{1}, q{1};
  for (int level = 0; level < 7; ++level) {
    std::vector<int> np = p, nq = p;
    np.insert(np.end(), q.begin(), q.end());
    for (int x : q) nq.push_back(-x);
    p.swap(np);
    q.swap(nq);
  }
  Coeffs out{};
  // The best direct RS seed in the retained scan was q[42:112].
  for (int j = 0; j < N; ++j) out[j] = static_cast<int8_t>(q[42 + j]);
  return out;
}

Coeffs fekete_window() {
  Coeffs out{};
  // Best direct shifted Fekete seed from the current exhaustive family scan.
  for (int j = 0; j < N; ++j) out[j] = legendre(j + 43, 101);
  return out;
}

Family transforms(const std::string& name, const Coeffs& source) {
  Family f;
  f.name = name;
  for (int b = 0; b < NB; ++b) {
    for (int q = 0; q < BLOCK; ++q) {
      int8_t x = source[b * BLOCK + q];
      int8_t r = source[b * BLOCK + (BLOCK - 1 - q)];
      f.option[b][0][q] = x;
      f.option[b][1][q] = -x;
      f.option[b][2][q] = r;
      f.option[b][3][q] = -r;
    }
  }
  return f;
}

Family crossover(const std::string& name, const Coeffs& a, const Coeffs& b) {
  Family f;
  f.name = name;
  for (int block = 0; block < NB; ++block) {
    for (int q = 0; q < BLOCK; ++q) {
      int j = block * BLOCK + q;
      f.option[block][0][q] = a[j];
      f.option[block][1][q] = -a[j];
      f.option[block][2][q] = b[j];
      f.option[block][3][q] = -b[j];
    }
  }
  return f;
}

Family four_sources(const std::string& name, const Coeffs& a, const Coeffs& b,
                    const Coeffs& c, const Coeffs& d) {
  Family f;
  f.name = name;
  const Coeffs* sources[4] = {&a, &b, &c, &d};
  for (int block = 0; block < NB; ++block)
    for (int option = 0; option < 4; ++option)
      for (int q = 0; q < BLOCK; ++q) {
        int j = block * BLOCK + q;
        f.option[block][option][q] = (*sources[option])[j];
      }
  return f;
}

std::vector<Coeffs> current_orbit() {
  std::vector<Coeffs> out;
  for (int rev = 0; rev < 2; ++rev)
    for (int sign : {-1, 1})
      for (int alt = 0; alt < 2; ++alt) {
        Coeffs z{};
        for (int j = 0; j < N; ++j) {
          int src = rev ? N - 1 - j : j;
          z[j] = sign * ((alt && (j & 1)) ? -1 : 1) * CURRENT[src];
        }
        out.push_back(z);
      }
  return out;
}

Coeffs decode(const Family& f, uint32_t code) {
  Coeffs out{};
  for (int b = 0; b < NB; ++b) {
    int option = (code >> (2 * b)) & 3;
    for (int q = 0; q < BLOCK; ++q)
      out[b * BLOCK + q] = f.option[b][option][q];
  }
  return out;
}

int orbit_distance(const Coeffs& a, const std::vector<Coeffs>& orbit) {
  int best = N;
  for (const auto& z : orbit) {
    int d = 0;
    for (int j = 0; j < N; ++j) d += a[j] != z[j];
    best = std::min(best, d);
  }
  return best;
}

struct SearchContext {
  const Family& family;
  int grid;
  int keep;
  const std::vector<float>& re;
  const std::vector<float>& im;
  const std::vector<Coeffs>& orbit;
  std::atomic<int> prefix{0};
  std::mutex merge_mu;
  std::vector<Candidate> merged;
};

void recurse(SearchContext& ctx, int block, uint32_t code,
             std::vector<float>& curve_re, std::vector<float>& curve_im,
             std::priority_queue<Candidate, std::vector<Candidate>, WorseFirst>& heap) {
  if (block == NB) {
    float max2 = 0.0f;
    for (int k = 0; k < ctx.grid; ++k)
      max2 = std::max(max2, curve_re[k] * curve_re[k] + curve_im[k] * curve_im[k]);
    if (static_cast<int>(heap.size()) >= ctx.keep && max2 >= heap.top().coarse2) return;
    Coeffs c = decode(ctx.family, code);
    int distance = orbit_distance(c, ctx.orbit);
    if (distance < 7) return;
    Candidate row{max2, code, distance};
    if (static_cast<int>(heap.size()) < ctx.keep) heap.push(row);
    else { heap.pop(); heap.push(row); }
    return;
  }
  for (int option = 0; option < 4; ++option) {
    size_t base = (static_cast<size_t>(block) * 4 + option) * ctx.grid;
    for (int k = 0; k < ctx.grid; ++k) {
      curve_re[k] += ctx.re[base + k];
      curve_im[k] += ctx.im[base + k];
    }
    recurse(ctx, block + 1, code | (uint32_t(option) << (2 * block)),
            curve_re, curve_im, heap);
    for (int k = 0; k < ctx.grid; ++k) {
      curve_re[k] -= ctx.re[base + k];
      curve_im[k] -= ctx.im[base + k];
    }
  }
}

double dense_score(const Coeffs& c, int grid) {
  double best2 = 0.0;
  for (int k = 0; k < grid; ++k) {
    double theta = 2.0 * PI * k / grid;
    double zr = std::cos(theta), zi = std::sin(theta);
    double pr = c[0], pi = 0.0;
    for (int j = 1; j < N; ++j) {
      double nr = pr * zr - pi * zi + c[j];
      pi = pr * zi + pi * zr;
      pr = nr;
    }
    best2 = std::max(best2, pr * pr + pi * pi);
  }
  return std::sqrt(best2) / std::sqrt(71.0);
}

std::vector<Candidate> search(const Family& family, int grid, int threads,
                              int keep) {
  std::vector<float> re(static_cast<size_t>(NB) * 4 * grid);
  std::vector<float> im(re.size());
  for (int b = 0; b < NB; ++b)
    for (int option = 0; option < 4; ++option)
      for (int k = 0; k < grid; ++k) {
        double theta = 2.0 * PI * k / grid;
        double rr = 0.0, ii = 0.0;
        for (int q = 0; q < BLOCK; ++q) {
          int j = b * BLOCK + q;
          double angle = (N - 1 - j) * theta;
          rr += family.option[b][option][q] * std::cos(angle);
          ii += family.option[b][option][q] * std::sin(angle);
        }
        size_t at = (static_cast<size_t>(b) * 4 + option) * grid + k;
        re[at] = rr;
        im[at] = ii;
      }
  const auto orbit = current_orbit();
  SearchContext ctx{family, grid, keep, re, im, orbit};
  std::vector<std::thread> workers;
  for (int t = 0; t < threads; ++t) {
    workers.emplace_back([&]() {
      std::priority_queue<Candidate, std::vector<Candidate>, WorseFirst> heap;
      std::vector<float> cr(grid), ci(grid);
      for (;;) {
        int prefix = ctx.prefix.fetch_add(1);
        if (prefix >= 16) break;
        int o0 = prefix & 3, o1 = prefix >> 2;
        size_t b0 = static_cast<size_t>(o0) * grid;
        size_t b1 = (4 + o1) * static_cast<size_t>(grid);
        for (int k = 0; k < grid; ++k) {
          cr[k] = re[b0 + k] + re[b1 + k];
          ci[k] = im[b0 + k] + im[b1 + k];
        }
        uint32_t code = uint32_t(o0) | (uint32_t(o1) << 2);
        recurse(ctx, 2, code, cr, ci, heap);
      }
      std::lock_guard<std::mutex> lock(ctx.merge_mu);
      while (!heap.empty()) { ctx.merged.push_back(heap.top()); heap.pop(); }
    });
  }
  for (auto& w : workers) w.join();
  std::sort(ctx.merged.begin(), ctx.merged.end(),
            [](auto& a, auto& b) { return a.coarse2 < b.coarse2; });
  if (static_cast<int>(ctx.merged.size()) > keep) ctx.merged.resize(keep);
  return ctx.merged;
}
}  // namespace

int main(int argc, char** argv) {
  int grid = argc > 1 ? std::atoi(argv[1]) : 512;
  int threads = argc > 2 ? std::atoi(argv[2]) : std::max(1u, std::thread::hardware_concurrency());
  int keep = argc > 3 ? std::atoi(argv[3]) : 500;
  Coeffs rs = rudin_shapiro_window(), fk = fekete_window();
  std::vector<Family> families;
  families.push_back(transforms("current-reverse-sign", CURRENT));
  families.push_back(crossover("current-old-sign", CURRENT, OLD));
  families.push_back(crossover("current-psl4-sign", CURRENT, PSL4));
  families.push_back(crossover("current-rs-sign", CURRENT, rs));
  families.push_back(transforms("rs-reverse-sign", rs));
  families.push_back(transforms("fekete-reverse-sign", fk));
  families.push_back(four_sources("current-old-psl4-fekete", CURRENT, OLD, PSL4, fk));
  families.push_back(four_sources("current-old-psl4-rs", CURRENT, OLD, PSL4, rs));
  for (const auto& family : families) {
    auto t0 = std::chrono::steady_clock::now();
    auto rows = search(family, grid, threads, keep);
    for (auto& row : rows) {
      Coeffs c = decode(family, row.code);
      // Overwrite coarse key with the materially denser replay for ordering.
      double fine = dense_score(c, 65536);
      row.coarse2 = fine * fine;
    }
    std::sort(rows.begin(), rows.end(),
              [](auto& a, auto& b) { return a.coarse2 < b.coarse2; });
    double sec = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    std::cout << std::setprecision(10) << "family=" << family.name
              << " candidates=1048576 grid=" << grid << " fine_kept=" << rows.size()
              << " seconds=" << sec << '\n';
    for (int rank = 0; rank < std::min<int>(3, rows.size()); ++rank) {
      Coeffs c = decode(family, rows[rank].code);
      std::cout << "rank=" << rank + 1 << " fine65536=" << std::sqrt(rows[rank].coarse2)
                << " orbit_distance=" << rows[rank].orbit_distance
                << " code=" << rows[rank].code << " coefficients=[";
      for (int j = 0; j < N; ++j) { if (j) std::cout << ','; std::cout << int(c[j]); }
      std::cout << "]\n";
    }
  }
  return 0;
}

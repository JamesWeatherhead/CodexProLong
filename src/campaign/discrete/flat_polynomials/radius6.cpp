#include <algorithm>
#include <array>
#include <cmath>
#include <complex>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <limits>
#include <set>
#include <sstream>
#include <string>
#include <vector>

namespace {

constexpr int kLength = 70;
constexpr int kUniqueGrid = 999999;
constexpr int kCoarseGrid = 512;
constexpr long double kPi = 3.141592653589793238462643383279502884L;

struct Point {
  long double base_re;
  long double base_im;
  std::array<long double, kLength> delta_re;
  std::array<long double, kLength> delta_im;
  long double base_norm2;
};

std::array<int, kLength> parse_sequence(const std::string& text) {
  std::array<int, kLength> result{};
  std::stringstream stream(text);
  std::string token;
  int index = 0;
  while (std::getline(stream, token, ',')) {
    if (index >= kLength) {
      throw std::runtime_error("too many coefficients");
    }
    const int value = std::stoi(token);
    if (value != -1 && value != 1) {
      throw std::runtime_error("coefficient is not +/-1");
    }
    result[index++] = value;
  }
  if (index != kLength) {
    throw std::runtime_error("expected 70 coefficients");
  }
  return result;
}

Point make_point(int grid_index, const std::array<int, kLength>& coefficients) {
  Point point{};
  const long double theta =
      2.0L * kPi * static_cast<long double>(grid_index) /
      static_cast<long double>(kUniqueGrid);
  for (int coefficient_index = 0; coefficient_index < kLength;
       ++coefficient_index) {
    const int exponent = kLength - 1 - coefficient_index;
    const long double angle = theta * static_cast<long double>(exponent);
    const long double real = std::cos(angle);
    const long double imag = std::sin(angle);
    point.base_re += coefficients[coefficient_index] * real;
    point.base_im += coefficients[coefficient_index] * imag;
    point.delta_re[coefficient_index] =
        -2.0L * coefficients[coefficient_index] * real;
    point.delta_im[coefficient_index] =
        -2.0L * coefficients[coefficient_index] * imag;
  }
  point.base_norm2 = point.base_re * point.base_re + point.base_im * point.base_im;
  return point;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc != 6) {
    std::cerr << "usage: radius6 SEQUENCE FIRST_BEGIN FIRST_END GATE PEAK\n";
    return 2;
  }
  try {
    const auto coefficients = parse_sequence(argv[1]);
    const int first_begin = std::stoi(argv[2]);
    const int first_end = std::stoi(argv[3]);
    const long double gate = std::stold(argv[4]);
    const int peak = std::stoi(argv[5]);
    if (first_begin < 0 || first_end < first_begin || first_end > 65) {
      throw std::runtime_error("invalid first-index range");
    }
    if (peak < 0 || peak >= kUniqueGrid || gate <= 0.0L) {
      throw std::runtime_error("invalid peak or gate");
    }

    std::set<int> literal_indices;
    for (int index = 0; index < kCoarseGrid; ++index) {
      literal_indices.insert(static_cast<int>(std::floor(
          static_cast<long double>(index) * (kUniqueGrid - 1) /
          static_cast<long double>(kCoarseGrid))));
    }
    for (const int center : {peak, (kUniqueGrid - peak) % kUniqueGrid}) {
      for (int delta = -6000; delta <= 6000; delta += 50) {
        int index = (center + delta) % kUniqueGrid;
        if (index < 0) index += kUniqueGrid;
        literal_indices.insert(index);
      }
    }

    std::vector<Point> points;
    points.reserve(literal_indices.size());
    for (const int index : literal_indices) {
      points.push_back(make_point(index, coefficients));
    }
    std::sort(points.begin(), points.end(), [](const Point& left, const Point& right) {
      return left.base_norm2 > right.base_norm2;
    });

    // The positive margin makes the pruning conservative relative to the
    // verifier's complex128 arithmetic: borderline masks become survivors.
    const long double raw_gate = gate * std::sqrt(71.0L) + 1.0e-10L;
    const long double threshold2 = raw_gate * raw_gate;
    unsigned long long processed = 0;
    unsigned long long survivors = 0;
    long double minimum_certificate = std::numeric_limits<long double>::infinity();
    std::array<int, 6> minimum_mask{};

    std::cout << std::setprecision(18);
    for (int a = first_begin; a < first_end; ++a) {
      for (int b = a + 1; b <= 65; ++b) {
        for (int c = b + 1; c <= 66; ++c) {
          for (int d = c + 1; d <= 67; ++d) {
            for (int e = d + 1; e <= 68; ++e) {
              for (int f = e + 1; f <= 69; ++f) {
                ++processed;
                bool rejected = false;
                long double certificate2 = 0.0L;
                for (const Point& point : points) {
                  const long double real = point.base_re + point.delta_re[a] +
                                           point.delta_re[b] + point.delta_re[c] +
                                           point.delta_re[d] + point.delta_re[e] +
                                           point.delta_re[f];
                  const long double imag = point.base_im + point.delta_im[a] +
                                           point.delta_im[b] + point.delta_im[c] +
                                           point.delta_im[d] + point.delta_im[e] +
                                           point.delta_im[f];
                  const long double norm2 = real * real + imag * imag;
                  if (norm2 >= threshold2) {
                    rejected = true;
                    certificate2 = norm2;
                    break;
                  }
                }
                if (rejected) {
                  const long double certificate =
                      std::sqrt(certificate2 / 71.0L);
                  if (certificate < minimum_certificate) {
                    minimum_certificate = certificate;
                    minimum_mask = {a, b, c, d, e, f};
                  }
                  continue;
                }

                ++survivors;
                long double maximum2 = 0.0L;
                for (const Point& point : points) {
                  const long double real = point.base_re + point.delta_re[a] +
                                           point.delta_re[b] + point.delta_re[c] +
                                           point.delta_re[d] + point.delta_re[e] +
                                           point.delta_re[f];
                  const long double imag = point.base_im + point.delta_im[a] +
                                           point.delta_im[b] + point.delta_im[c] +
                                           point.delta_im[d] + point.delta_im[e] +
                                           point.delta_im[f];
                  maximum2 = std::max(maximum2, real * real + imag * imag);
                }
                std::cout << "SURVIVOR " << a << ' ' << b << ' ' << c << ' '
                          << d << ' ' << e << ' ' << f << ' '
                          << std::sqrt(maximum2 / 71.0L) << '\n';
              }
            }
          }
        }
      }
    }

    std::cout << "PROCESSED " << processed << '\n';
    std::cout << "SURVIVORS " << survivors << '\n';
    std::cout << "GRID_POINTS " << points.size() << '\n';
    if (std::isfinite(minimum_certificate)) {
      std::cout << "MIN_CERTIFICATE " << minimum_certificate;
      for (const int index : minimum_mask) std::cout << ' ' << index;
      std::cout << '\n';
    }
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 2;
  }
  return 0;
}

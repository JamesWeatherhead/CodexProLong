#include <array>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

constexpr int kSize = 70;
constexpr int kBound = 4;

struct Result {
  uint64_t nodes = 0;
  uint64_t leaves = 0;
  uint64_t solutions = 0;
};

int NewlyFixedCorrelation(const std::array<int8_t, kSize>& values, int depth) {
  const int lag = kSize - depth;
  int correlation = 0;
  for (int index = 0; index < depth; ++index) {
    correlation += values[index] * values[index + lag];
  }
  return correlation;
}

bool CompleteValid(const std::array<int8_t, kSize>& values) {
  for (int lag = 1; lag < kSize; ++lag) {
    int correlation = 0;
    for (int index = 0; index + lag < kSize; ++index) {
      correlation += values[index] * values[index + lag];
    }
    if (correlation < -kBound || correlation > kBound) {
      return false;
    }
  }
  return true;
}

void Search(std::array<int8_t, kSize>& values, int depth, Result& result) {
  ++result.nodes;
  if (depth == kSize / 2) {
    ++result.leaves;
    result.solutions += CompleteValid(values);
    return;
  }
  const int right = kSize - 1 - depth;
  for (int left_value : {-1, 1}) {
    for (int right_value : {-1, 1}) {
      values[depth] = static_cast<int8_t>(left_value);
      values[right] = static_cast<int8_t>(right_value);
      const int correlation = NewlyFixedCorrelation(values, depth + 1);
      if (correlation >= -kBound && correlation <= kBound) {
        Search(values, depth + 1, result);
      }
    }
  }
}

Result SolveCube(const std::string& cube) {
  if (cube.size() != kSize) {
    throw std::runtime_error("cube length is not 70");
  }
  std::array<int8_t, kSize> values{};
  int left_depth = 0;
  while (left_depth < kSize / 2 && cube[left_depth] != '?') {
    const int right = kSize - 1 - left_depth;
    if (cube[right] == '?') {
      throw std::runtime_error("cube is not outside-in balanced");
    }
    values[left_depth] = cube[left_depth] == '1' ? 1 : -1;
    values[right] = cube[right] == '1' ? 1 : -1;
    ++left_depth;
  }
  for (int index = left_depth; index < kSize - left_depth; ++index) {
    if (cube[index] != '?') {
      throw std::runtime_error("cube middle is not free");
    }
  }
  Result result;
  Search(values, left_depth, result);
  return result;
}

}  // namespace

int main() {
  try {
    std::vector<std::string> cubes;
    std::string cube;
    while (std::cin >> cube) {
      cubes.push_back(cube);
    }
    const auto started = std::chrono::steady_clock::now();
    uint64_t nodes = 0;
    uint64_t leaves = 0;
    uint64_t sat_cubes = 0;
    for (size_t index = 0; index < cubes.size(); ++index) {
      const Result result = SolveCube(cubes[index]);
      nodes += result.nodes;
      leaves += result.leaves;
      sat_cubes += result.solutions > 0;
      std::cout << "CUBE " << index << ' ' << result.nodes << ' '
                << result.leaves << ' ' << result.solutions << '\n';
    }
    const double seconds = std::chrono::duration<double>(
                               std::chrono::steady_clock::now() - started)
                               .count();
    std::cout << "DONE cubes=" << cubes.size() << " nodes=" << nodes
              << " leaves=" << leaves << " sat_cubes=" << sat_cubes
              << " seconds=" << seconds << '\n';
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    return 2;
  }
}

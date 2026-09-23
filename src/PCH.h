#pragma once

// The offline tests build Rules and Catalog without the game: no CommonLibF4, only the standard
// library and nlohmann/json. Everything that needs RE:: lives outside those two files.
#ifndef SH_OFFLINE_TESTS
#	include "RE/Fallout.h"
#	include "F4SE/F4SE.h"

#	include <spdlog/sinks/basic_file_sink.h>

#	define DLLEXPORT __declspec(dllexport)

namespace logger = F4SE::log;
#endif

#include <nlohmann/json.hpp>

#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <charconv>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <deque>
#include <filesystem>
#include <format>
#include <fstream>
#include <functional>
#include <limits>
#include <map>
#include <mutex>
#include <optional>
#include <random>
#include <ranges>
#include <set>
#include <shared_mutex>
#include <span>
#include <thread>
#include <stdexcept>
#include <string>
#include <string_view>
#include <type_traits>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

using namespace std::literals;

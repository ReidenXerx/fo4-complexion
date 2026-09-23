cmake_minimum_required(VERSION 3.21)

# The version lives in VERSION (one line, x.y.z) so the generator, the plugin and the release
# archive can never disagree about it.
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/VERSION" SILHOUETTE_VERSION)
string(STRIP "${SILHOUETTE_VERSION}" SILHOUETTE_VERSION)

# Static libraries, shared CRT: an F4SE plugin is one DLL, with no spdlog.dll or fmt.dll beside it.
set(VCPKG_TARGET_TRIPLET "x64-windows-static-md" CACHE STRING "")

project(
	Silhouette
	VERSION ${SILHOUETTE_VERSION}
	LANGUAGES CXX
)

set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>DLL" CACHE STRING "")

# Fallout 4 OG 1.10.163 only (S-18): every RelocationID resolves to the one runtime we test against,
# and the plugin refuses any other at query time.
set(ENABLE_FALLOUT_F4 ON  CACHE BOOL "" FORCE)
set(ENABLE_FALLOUT_NG OFF CACHE BOOL "" FORCE)
set(ENABLE_FALLOUT_VR OFF CACHE BOOL "" FORCE)
set(BUILD_TESTS       OFF CACHE BOOL "" FORCE)

add_subdirectory("extern/CommonLibF4/CommonLibF4" "CommonLibF4")

set(SOURCES
	"src/PCH.h"
	"src/Catalog.h"
	"src/Catalog.cpp"
	"src/CoSave.h"
	"src/CoSave.cpp"
	"src/Director.h"
	"src/Director.cpp"
	"src/EventSources.h"
	"src/EventSources.cpp"
	"src/Game.h"
	"src/Game.cpp"
	"src/Papyrus.h"
	"src/Papyrus.cpp"
	"src/Plan.h"
	"src/Plan.cpp"
	"src/Registry.h"
	"src/Registry.cpp"
	"src/Rules.h"
	"src/Rules.cpp"
	"src/Sinks.h"
	"src/Sinks.cpp"
	"src/main.cpp"
)

add_library("${PROJECT_NAME}" SHARED ${SOURCES})

target_compile_features("${PROJECT_NAME}" PRIVATE cxx_std_23)

target_compile_definitions(
	"${PROJECT_NAME}"
	PRIVATE
		"SH_PROJECT_NAME=\"${PROJECT_NAME}\""
		"SH_VERSION_MAJOR=${PROJECT_VERSION_MAJOR}"
		"SH_VERSION_MINOR=${PROJECT_VERSION_MINOR}"
		"SH_VERSION_PATCH=${PROJECT_VERSION_PATCH}"
		"SH_VERSION_STRING=\"${PROJECT_VERSION}\""
)

target_include_directories("${PROJECT_NAME}" PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src")

target_link_libraries("${PROJECT_NAME}" PRIVATE CommonLibF4::CommonLibF4)

target_precompile_headers("${PROJECT_NAME}" PRIVATE "src/PCH.h")

if(MSVC)
	target_compile_options("${PROJECT_NAME}" PRIVATE "/permissive-" "/Zc:preprocessor" "/utf-8" "/W4" "/wd4201")
endif()

# Everything with no game in it -- the catalog, the rules, the plans, the co-save bytes and the whole
# director -- is tested without one.
add_executable(
	SilhouetteTests
	"tests/main.cpp"
	"src/Catalog.cpp"
	"src/Director.cpp"
	"src/Plan.cpp"
	"src/Registry.cpp"
	"src/Rules.cpp"
)
target_compile_features(SilhouetteTests PRIVATE cxx_std_23)
target_compile_definitions(SilhouetteTests PRIVATE SH_OFFLINE_TESTS=1)
target_include_directories(SilhouetteTests PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src")
target_precompile_headers(SilhouetteTests PRIVATE "src/PCH.h")
find_package(nlohmann_json CONFIG REQUIRED)
target_link_libraries(SilhouetteTests PRIVATE nlohmann_json::nlohmann_json)
if(MSVC)
	target_compile_options(SilhouetteTests PRIVATE "/permissive-" "/Zc:preprocessor" "/utf-8" "/W4")
endif()

cmake_minimum_required(VERSION 3.21)

# The version lives in VERSION (one line, x.y.z) so the plugin and the release archive can never disagree.
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/VERSION" COMPLEXION_VERSION)
string(STRIP "${COMPLEXION_VERSION}" COMPLEXION_VERSION)

# Static libraries, shared CRT: an F4SE plugin is one DLL, with no spdlog.dll or fmt.dll beside it.
set(VCPKG_TARGET_TRIPLET "x64-windows-static-md" CACHE STRING "")

project(
	Complexion
	VERSION ${COMPLEXION_VERSION}
	LANGUAGES CXX
)

set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>DLL" CACHE STRING "")

# One build for OG 1.10.163, NG 1.10.984 and AE 1.11.x through Runtime Database (CommonLibF4RD), as Silhouette
# (S-75). OFF builds the OG-only plugin on alandtse's CommonLibF4.
option(COMPLEXION_RUNTIME_DATABASE "Build on CommonLibF4RD for OG, NG and AE" ON)
set(BUILD_TESTS OFF CACHE BOOL "" FORCE)
# __FILE__ without this machine's folders: the compiler writes every source's full path into the dll.
if(MSVC)
	file(TO_NATIVE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/" COMPLEXION_TRIM_PREFIX)
	add_compile_options("/d1trimfile:${COMPLEXION_TRIM_PREFIX}")
endif()
if(COMPLEXION_RUNTIME_DATABASE)
	add_subdirectory("extern/CommonLibF4RD/CommonLibF4" "CommonLibF4")
else()
	set(ENABLE_FALLOUT_F4 ON  CACHE BOOL "" FORCE)
	set(ENABLE_FALLOUT_NG OFF CACHE BOOL "" FORCE)
	set(ENABLE_FALLOUT_VR OFF CACHE BOOL "" FORCE)
	add_subdirectory("extern/CommonLibF4/CommonLibF4" "CommonLibF4")
endif()

set(SOURCES
	"src/PCH.h"
	"src/Compat.h"
	"src/Catalog.h"
	"src/Catalog.cpp"
	"src/Compose.h"
	"src/Compose.cpp"
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
	"src/Sinks.h"
	"src/Sinks.cpp"
	"src/main.cpp"
)

add_library("${PROJECT_NAME}" SHARED ${SOURCES})

target_compile_features("${PROJECT_NAME}" PRIVATE cxx_std_23)

target_compile_definitions(
	"${PROJECT_NAME}"
	PRIVATE
		"CX_PROJECT_NAME=\"${PROJECT_NAME}\""
		"CX_VERSION_MAJOR=${PROJECT_VERSION_MAJOR}"
		"CX_VERSION_MINOR=${PROJECT_VERSION_MINOR}"
		"CX_VERSION_PATCH=${PROJECT_VERSION_PATCH}"
		"CX_VERSION_STRING=\"${PROJECT_VERSION}\""
		"$<$<BOOL:${COMPLEXION_RUNTIME_DATABASE}>:CX_RUNTIME_DATABASE=1>"
)

target_include_directories("${PROJECT_NAME}" PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src")

find_package(nlohmann_json CONFIG REQUIRED)
target_link_libraries("${PROJECT_NAME}" PRIVATE CommonLibF4::CommonLibF4 nlohmann_json::nlohmann_json)

target_precompile_headers("${PROJECT_NAME}" PRIVATE "src/PCH.h")

if(MSVC)
	# A PDB for the Release DLL too: a crash log names our functions only with one.
	target_compile_options("${PROJECT_NAME}" PRIVATE "/permissive-" "/Zc:preprocessor" "/utf-8" "/W4" "/wd4201" "$<$<CONFIG:Release>:/Zi>")
	target_link_options("${PROJECT_NAME}" PRIVATE "$<$<CONFIG:Release>:/DEBUG;/OPT:REF;/OPT:ICF;/PDBALTPATH:%_PDB%>")
endif()

# Everything with no game in it -- the composer, the director, the co-save bytes -- is tested without one.
add_executable(
	ComplexionTests
	"tests/main.cpp"
	"src/Compose.cpp"
	"src/Director.cpp"
)
target_compile_features(ComplexionTests PRIVATE cxx_std_23)
target_compile_definitions(ComplexionTests PRIVATE CX_OFFLINE_TESTS=1)
target_include_directories(ComplexionTests PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src")
target_precompile_headers(ComplexionTests PRIVATE "src/PCH.h")
target_link_libraries(ComplexionTests PRIVATE nlohmann_json::nlohmann_json)
if(MSVC)
	target_compile_options(ComplexionTests PRIVATE "/permissive-" "/Zc:preprocessor" "/utf-8" "/W4")
endif()

#include "Camera.h"

#include "Shot.h"

namespace SH::Camera
{
	namespace
	{
		// The free camera state as F4SE and ScreenArcherMenu read it: the base state (0x28 bytes, the size
		// CommonLibF4 asserts on every runtime), then position, pitch and heading.
		struct FreeCamera
		{
			std::byte base[0x28];
			float     x;
			float     y;
			float     z;
			float     pitch;
			float     yaw;
		};
		static_assert(offsetof(FreeCamera, x) == 0x28 && offsetof(FreeCamera, yaw) == 0x38);

		constexpr float kSameSpot = 64.0F;  // how far the free camera may read from the camera and still be it

		// "tfc" is not carried out when it is typed: the camera changes state a frame or more later (measured
		// in game, 2026-09-30 -- a check right after it found no free camera, which came on anyway and outlived
		// the window). So the window says what it WANTS, and every step moves the camera one toggle towards
		// it, answering kWait until the camera is there.
		bool       g_want = false;     // the window wants the free camera on, at g_view
		bool       g_ours = false;     // Silhouette asked for the free camera: it is Silhouette's to switch off
		bool       g_pending = false;  // a toggle was asked for and the camera has not changed since
		bool       g_wasFree = false;  // the state the pending toggle is to change
		std::chrono::steady_clock::time_point g_asked;  // when it was asked for
		constexpr auto kGiveUp = std::chrono::seconds(3);  // a toggle not carried out by then never will be
		Shot::View g_view;

		RE::PlayerCamera* Camera()
		{
			return RE::PlayerCamera::GetSingleton();
		}

		bool InFree(RE::PlayerCamera* a_camera)
		{
			return a_camera->currentState && a_camera->currentState == a_camera->cameraStates[RE::CameraState::kFree];
		}

		void Toggle(bool a_free)
		{
			g_pending = true;
			g_wasFree = a_free;
			g_asked = std::chrono::steady_clock::now();
			RE::Console::ExecuteCommand("tfc");
		}

		// The free camera is on and the window wants it at g_view: its fields are read against the camera's own
		// position first -- with the free camera on, the camera is wherever it is -- and a layout that differs
		// leaves it alone.
		std::string Place(RE::PlayerCamera* a_camera)
		{
			auto* free = reinterpret_cast<FreeCamera*>(a_camera->currentState.get());
			RE::NiPoint3 at;
			a_camera->GetCameraPosition(at, true);
			const float dx = free->x - at.x;
			const float dy = free->y - at.y;
			const float dz = free->z - at.z;
			if (dx * dx + dy * dy + dz * dz > kSameSpot * kSameSpot) {
				g_want = false;  // the next step puts the player's camera back
				return std::format("the free camera reads ({:.0f}, {:.0f}, {:.0f}) where the camera is ({:.0f}, {:.0f}, {:.0f}): "
								   "its layout differs on this game, so the window does not move it",
					free->x, free->y, free->z, at.x, at.y, at.z);
			}
			free->x = g_view.x;
			free->y = g_view.y;
			free->z = g_view.z;
			free->pitch = g_view.pitch;
			free->yaw = g_view.yaw;
			return {};
		}
	}

	std::string Frame(float a_x, float a_y, float a_z, float a_angleDegrees, float a_height)
	{
		g_want = true;
		g_view = Shot::Aim(a_x, a_y, a_z, a_angleDegrees, a_height);
		return Step();
	}

	std::string Restore()
	{
		g_want = false;
		return Step();
	}

	std::string Step()
	{
		auto* camera = Camera();
		if (!camera) {
			g_want = g_ours = g_pending = false;
			return "there is no player camera";
		}
		const bool free = InFree(camera);
		if (g_pending) {
			if (free == g_wasFree) {
				if (std::chrono::steady_clock::now() - g_asked < kGiveUp) {
					return std::string{ kWait };  // the toggle asked for is not carried out yet
				}
				g_pending = false;
				g_want = false;
				return std::format("the free camera did not {} within {} s", free ? "go off" : "come on", kGiveUp.count());
			}
			g_pending = false;
		}
		if (g_want) {
			if (!free) {
				g_ours = true;
				Toggle(false);
				return std::string{ kWait };
			}
			return Place(camera);
		}
		// Back: only a free camera Silhouette switched on goes off; one the player had on stays.
		if (free && g_ours) {
			Toggle(true);
			return std::string{ kWait };
		}
		g_ours = false;
		return {};
	}
}

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

		bool g_ours = false;  // Frame switched the free camera on: Restore switches it off

		RE::PlayerCamera* Camera()
		{
			return RE::PlayerCamera::GetSingleton();
		}

		bool InFree(RE::PlayerCamera* a_camera)
		{
			return a_camera->currentState && a_camera->currentState == a_camera->cameraStates[RE::CameraState::kFree];
		}

		void Toggle()
		{
			RE::Console::ExecuteCommand("tfc");
		}
	}

	std::string Frame(float a_x, float a_y, float a_z, float a_angleDegrees, float a_height)
	{
		auto* camera = Camera();
		if (!camera) {
			return "there is no player camera";
		}
		const bool was = InFree(camera);
		if (!was) {
			Toggle();
			if (!InFree(camera)) {
				return "the free camera did not come on";
			}
			g_ours = true;
		}
		auto* free = reinterpret_cast<FreeCamera*>(camera->currentState.get());
		RE::NiPoint3 at;
		camera->GetCameraPosition(at, true);
		const float dx = free->x - at.x;
		const float dy = free->y - at.y;
		const float dz = free->z - at.z;
		// With the free camera on, the camera is wherever the free camera is: fields that read somewhere else
		// are not its position.
		if (dx * dx + dy * dy + dz * dz > kSameSpot * kSameSpot) {
			const auto why = std::format("the free camera reads ({:.0f}, {:.0f}, {:.0f}) where the camera is ({:.0f}, {:.0f}, {:.0f}): "
										 "its layout differs on this game, so the window does not move it",
				free->x, free->y, free->z, at.x, at.y, at.z);
			Restore();
			return why;
		}
		const auto view = Shot::Aim(a_x, a_y, a_z, a_angleDegrees, a_height);
		free->x = view.x;
		free->y = view.y;
		free->z = view.z;
		free->pitch = view.pitch;
		free->yaw = view.yaw;
		return {};
	}

	void Restore()
	{
		if (!g_ours) {
			return;
		}
		g_ours = false;
		if (auto* camera = Camera(); camera && InFree(camera)) {
			Toggle();
		}
	}
}

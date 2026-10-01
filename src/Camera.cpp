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
		constexpr float kTurn = 6.2832F;    // a full turn: a heading or pitch beyond two of them is not one

		// "tfc" is not carried out when it is typed: the camera changes state a frame or more later (measured
		// in game, 2026-09-30 -- a check right after it found no free camera, which came on anyway and outlived
		// the window). So the window says what it WANTS, and every step moves the camera one toggle towards
		// it, answering kWait until the camera is there.
		bool       g_want = false;     // the window wants the free camera on, at g_view
		bool       g_ours = false;     // Silhouette asked for the free camera: it is Silhouette's to switch off
		bool       g_foreign = false;  // the free camera was on before the window asked: the player's (or
		                               // ScreenArcherMenu's) -- left where it is and left on
		bool       g_placed = false;   // g_view was written into the free camera
		bool       g_muted = false;    // the free camera's own input was switched off (Mute)
		bool       g_pending = false;  // a toggle was asked for and the camera has not changed since
		bool       g_wasFree = false;  // the state the pending toggle is to change
		std::chrono::steady_clock::time_point g_asked;     // when it was asked for
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

		// The free camera listens to the mouse itself -- left button up, right button down -- and took the clicks
		// meant for the window (the owner's test, 2026-10-01). Its own input switch, BSInputEventUser's
		// inputEventHandlingEnabled (every camera state is one, the same on every runtime), is turned off while
		// Silhouette holds the camera, and back on before it lets go. A value that is not a bool is not touched.
		void Mute(RE::TESCameraState* a_state, bool a_mute)
		{
			if (!a_state) {
				return;
			}
			const auto raw = *reinterpret_cast<const std::uint8_t*>(&a_state->inputEventHandlingEnabled);
			if (raw > 1) {
				return;
			}
			a_state->inputEventHandlingEnabled = !a_mute;
			g_muted = a_mute;
		}

		void Unmute(RE::PlayerCamera* a_camera)
		{
			if (g_muted && a_camera) {
				Mute(a_camera->cameraStates[RE::CameraState::kFree].get(), false);
			}
			g_muted = false;
		}

		bool Near(float a_x, float a_y, float a_z, float b_x, float b_y, float b_z)
		{
			const float dx = a_x - b_x;
			const float dy = a_y - b_y;
			const float dz = a_z - b_z;
			return dx * dx + dy * dy + dz * dz <= kSameSpot * kSameSpot;
		}

		// The free camera is on and the window wants it at g_view. Its fields are read first: the position
		// against the camera's own -- with the free camera on, the camera is wherever it is, or where Silhouette
		// last put it, the root following a frame later -- and the angles against what an angle can be. A
		// layout that differs leaves it alone, and the player's camera comes back.
		std::string Place(RE::PlayerCamera* a_camera)
		{
			auto* free = reinterpret_cast<FreeCamera*>(a_camera->currentState.get());
			RE::NiPoint3 at;
			a_camera->GetCameraPosition(at, true);
			const bool here = Near(free->x, free->y, free->z, at.x, at.y, at.z) ||
			                  (g_placed && Near(free->x, free->y, free->z, g_view.x, g_view.y, g_view.z));
			const bool angles = std::isfinite(free->pitch) && std::isfinite(free->yaw) && std::abs(free->pitch) <= 2.0F * kTurn &&
			                    std::abs(free->yaw) <= 2.0F * kTurn;
			if (!here || !angles) {
				const auto why = std::format("the free camera reads ({:.0f}, {:.0f}, {:.0f}; pitch {:.2f}, heading {:.2f}) where the camera is "
											 "({:.0f}, {:.0f}, {:.0f}): its layout differs on this game, so the window does not move it",
					free->x, free->y, free->z, free->pitch, free->yaw, at.x, at.y, at.z);
				g_want = false;
				if (g_ours) {
					Toggle(true);  // back at once: the window works on without it
				}
				return why;
			}
			free->x = g_view.x;
			free->y = g_view.y;
			free->z = g_view.z;
			free->pitch = g_view.pitch;
			free->yaw = g_view.yaw;
			g_placed = true;
			Mute(a_camera->currentState.get(), true);
			return {};
		}
	}

	std::string Frame(float a_x, float a_y, float a_z, float a_angleDegrees, float a_height)
	{
		if (!g_want && !g_ours && !g_pending) {
			// A free camera already on is not Silhouette's: the player's, or another mod's (ScreenArcherMenu,
			// photo mode). It is neither moved nor switched off.
			auto* camera = Camera();
			g_foreign = camera && InFree(camera);
			g_placed = false;
		}
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
			Reset();
			return "there is no player camera";
		}
		const bool free = InFree(camera);
		if (g_pending) {
			if (free == g_wasFree) {
				if (std::chrono::steady_clock::now() - g_asked < kGiveUp) {
					return std::string{ kWait };  // the toggle asked for is not carried out yet
				}
				// Given up. A switch-on that comes later is still Silhouette's to switch off (g_ours stays); a
				// switch-off that never came is not asked for again -- a second "tfc" landing after a slow first
				// one would put the free camera back on.
				g_pending = false;
				g_want = false;
				if (g_wasFree) {
					g_ours = false;
				}
				return std::format("the free camera did not {} within {} s", g_wasFree ? "go off" : "come on", kGiveUp.count());
			}
			g_pending = false;
		}
		if (g_want) {
			if (g_foreign) {
				return {};  // the player's free camera: the window works without moving it
			}
			if (!free) {
				g_ours = true;
				g_placed = false;
				Toggle(false);
				return std::string{ kWait };
			}
			return Place(camera);
		}
		g_foreign = false;
		Unmute(camera);  // before anything else: a free camera left mute would never answer the player again
		// Back: only a free camera Silhouette switched on goes off; one the player had on stays.
		if (free && g_ours) {
			Toggle(true);
			return std::string{ kWait };
		}
		g_ours = false;
		g_placed = false;
		return {};
	}

	void Reset()
	{
		Unmute(Camera());
		g_want = g_ours = g_foreign = g_placed = g_pending = g_wasFree = false;
	}
}

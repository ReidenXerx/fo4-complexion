#include "Shot.h"

#include <algorithm>
#include <cmath>
#include <numbers>

namespace CX::Shot
{
	namespace
	{
		constexpr float kHuman = 128.0F;     // a grown human, in game units, when the height reads nothing
		constexpr float kDistance = 1.55F;   // camera distance, in heights: the whole body with the window open
		constexpr float kLevel = 0.52F;      // camera height, in heights: level with the middle of the body
		constexpr float kLeft = 0.33F;       // the look point moves right by this share of the distance, so
		                                     // they stand left of centre, clear of the window
		constexpr float kNeck = 0.887F;      // the body mesh's height (feet to the neck seam) in actor heights
		                                     // (113.5 of a 128-unit human)
	}

	View Aim(float a_x, float a_y, float a_z, float a_angleDegrees, float a_height)
	{
		const float height = a_height > 1.0F ? a_height : kHuman;
		const float distance = std::max(170.0F, height * kDistance);
		const float angle = a_angleDegrees * std::numbers::pi_v<float> / 180.0F;
		// Where they face (heading: 0 is +y, clockwise), and the camera out along it.
		const float fx = std::sin(angle);
		const float fy = std::cos(angle);
		View v;
		v.x = a_x + fx * distance;
		v.y = a_y + fy * distance;
		v.z = a_z + height * kLevel;
		// Looking back at them: heading angle + pi. Its right-hand side is (cos h, -sin h) for heading h, which
		// for angle + pi is (-cos angle, sin angle).
		const float lookX = a_x - std::cos(angle) * distance * kLeft;
		const float lookY = a_y + std::sin(angle) * distance * kLeft;
		float yaw = std::atan2(lookX - v.x, lookY - v.y);
		if (yaw < 0.0F) {
			yaw += 2.0F * std::numbers::pi_v<float>;
		}
		v.yaw = yaw;
		v.pitch = 0.0F;
		return v;
	}

	View Focus(float a_x, float a_y, float a_z, float a_angleDegrees, float a_height, const Spot& a_spot)
	{
		const float height = a_height > 1.0F ? a_height : kHuman;
		const float scale = height * kNeck;  // body heights -> game units
		const float angle = a_angleDegrees * std::numbers::pi_v<float> / 180.0F;
		// Their forward (heading 0 is +y, clockwise) and their right.
		const float fx = std::sin(angle), fy = std::cos(angle);
		const float rx = std::cos(angle), ry = -std::sin(angle);
		float lx = a_spot.x, ly = a_spot.y, h = a_spot.h;
		float nx = a_spot.nx, ny = a_spot.ny;
		if (a_spot.arm) {
			// The mesh holds the arms out and down at about 45 degrees (measured on thumbs.py's spots: the shoulder
			// near h 0.93, x 0.12; the wrist near h 0.75, x 0.29); the idle pose hangs them at the side. As far
			// from the shoulder down the hanging arm, seen from the arm's side and a little in front.
			const float side = a_spot.x >= 0.0F ? 1.0F : -1.0F;
			const float out = std::max(std::abs(a_spot.x) - 0.12F, 0.0F);
			const float down = std::max(0.93F - a_spot.h, 0.0F);
			h = std::clamp(0.93F - std::sqrt(out * out + down * down), 0.45F, 0.93F);
			lx = side * 0.17F;
			ly = 0.0F;
			nx = side;
			ny = 0.6F;
		}
		const float tx = a_x + (rx * lx + fx * ly) * scale;
		const float ty = a_y + (ry * lx + fy * ly) * scale;
		const float tz = a_z + std::clamp(h, 0.05F, 1.0F) * scale;
		// The normal out of the skin, level (the camera stays level with the spot).
		float wx = rx * nx + fx * ny;
		float wy = ry * nx + fy * ny;
		const float len = std::sqrt(wx * wx + wy * wy);
		if (len < 0.2F) {
			wx = fx;  // a mark facing up or down: from the front
			wy = fy;
		} else {
			wx /= len;
			wy /= len;
		}
		const float distance = std::clamp(a_spot.spread * scale * 3.0F + 35.0F, 45.0F, a_spot.arm ? 120.0F : 105.0F);
		View v;
		v.x = tx + wx * distance;
		v.y = ty + wy * distance;
		v.z = std::max(tz, a_z + 25.0F);  // a mark on the feet: not from the floor
		// Looking back along the normal; the look point moves to the camera's right, so the spot stands left of
		// centre. Looking along (dx, dy), the right-hand side is (dy, -dx).
		const float dx = -wx, dy = -wy;
		const float lookX = tx + dy * distance * kLeft;
		const float lookY = ty - dx * distance * kLeft;
		float yaw = std::atan2(lookX - v.x, lookY - v.y);
		if (yaw < 0.0F) {
			yaw += 2.0F * std::numbers::pi_v<float>;
		}
		v.yaw = yaw;
		v.pitch = 0.0F;
		return v;
	}
}

#include "Shot.h"

#include <algorithm>
#include <cmath>
#include <numbers>

namespace SH::Shot
{
	namespace
	{
		constexpr float kHuman = 128.0F;     // a grown human, in game units, when the height reads nothing
		constexpr float kDistance = 1.55F;   // camera distance, in heights: the whole body with the window open
		constexpr float kLevel = 0.52F;      // camera height, in heights: level with the middle of the body
		constexpr float kLeft = 0.33F;       // the look point moves right by this share of the distance, so
		                                     // they stand left of centre, clear of the window
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
}

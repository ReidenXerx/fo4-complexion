#pragma once

// C-19: where the overlay window puts the camera -- pure arithmetic (Camera.cpp moves the game's free camera
// there). Ported from Silhouette's picker window (S-79).

namespace CX::Shot
{
	// A camera: position, and heading and pitch in radians. Heading as the game's actors have it: 0 looks
	// along +y, and it grows clockwise seen from above (towards +x).
	struct View
	{
		float x{ 0.0F };
		float y{ 0.0F };
		float z{ 0.0F };
		float yaw{ 0.0F };
		float pitch{ 0.0F };
	};

	// In front of someone standing at a_x, a_y, a_z (their feet) and facing a_angleDegrees, a_height tall: far
	// enough for the whole body, level with its middle, looking back at them -- and turned so they stand in
	// the left part of the screen, clear of the window on the right.
	[[nodiscard]] View Aim(float a_x, float a_y, float a_z, float a_angleDegrees, float a_height);
}

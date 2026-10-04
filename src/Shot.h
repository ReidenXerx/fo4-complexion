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

	// Where a mark sits on a body, in the body's own frame (tools/paint/thumbs.py): h 0 the feet .. 1 the neck seam,
	// x the character's right and y forward, both in body heights; its outward normal; how far it spreads (body
	// heights); whether it is on an arm.
	struct Spot
	{
		float h{ 0.5F };
		float x{ 0.0F };
		float y{ 0.0F };
		float nx{ 0.0F };
		float ny{ 1.0F };
		float nz{ 0.0F };
		float spread{ 0.05F };
		bool  arm{ false };
	};

	// Close to a spot on someone standing at a_x, a_y, a_z facing a_angleDegrees, a_height tall: out along the
	// spot's normal, near enough to see the mark, the spot left of centre (clear of the window). Arms are framed
	// loosely: the game's idle pose holds them down, where the mesh holds them out.
	[[nodiscard]] View Focus(float a_x, float a_y, float a_z, float a_angleDegrees, float a_height, const Spot& a_spot);
}

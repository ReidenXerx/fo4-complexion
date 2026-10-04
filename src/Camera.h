#pragma once

// C-19: the overlay window's camera, ported from Silhouette's picker window (S-79). Main thread only (the
// natives that call these are bound as such).

#include "Shot.h"

namespace CX::Camera
{
	// What Frame, Restore and Step answer while the camera is still on its way: the game carries out "tfc"
	// a frame or more after it is typed, so the caller waits a moment and asks Step again.
	inline constexpr std::string_view kWait = "wait";

	// The game's free camera ("tfc", switched on unless it already is) in front of someone at a_x, a_y, a_z
	// facing a_angleDegrees, a_height tall (Shot::Aim). "" when it is there, kWait while it comes on, otherwise
	// why not -- and then the player's camera comes back. The free camera's fields are the ones
	// ScreenArcherMenu writes (F4SE's layout); they are read against the camera's own position before anything
	// is written, and a layout that differs leaves the camera alone -- never half on.
	[[nodiscard]] std::string Frame(float a_x, float a_y, float a_z, float a_angleDegrees, float a_height);

	// The same, to a view already worked out (Shot::Focus: close to a mark).
	[[nodiscard]] std::string FrameView(const Shot::View& a_view);

	// Back to the camera the player had: the free camera goes off if Complexion switched it on. "" when it is
	// back, kWait while it goes.
	[[nodiscard]] std::string Restore();

	// One more step towards what was last asked (Frame or Restore), with the same answers.
	[[nodiscard]] std::string Step();

	// A load or a new game: the camera the window knew is gone, and nothing asked for before it is waited on.
	void Reset();
}

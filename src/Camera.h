#pragma once

// S-79: the picker window's camera. Main thread only (the natives that call these are bound as such).

namespace SH::Camera
{
	// The game's free camera ("tfc", switched on unless it already is) in front of someone at a_x, a_y, a_z
	// facing a_angleDegrees, a_height tall (Shot::Aim). "" when it is there; otherwise why not, and the camera
	// is left as it was. The free camera's fields are the ones ScreenArcherMenu writes (F4SE's layout); they are
	// read against the camera's own position before anything is written, and a layout that differs leaves the
	// camera alone -- never half on (S-75's rule).
	[[nodiscard]] std::string Frame(float a_x, float a_y, float a_z, float a_angleDegrees, float a_height);

	// Back to the camera the player had: the free camera goes off if Frame switched it on.
	void Restore();
}

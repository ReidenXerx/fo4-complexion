#pragma once

// The three things Silhouette listens to: an actor's 3D loading (they appeared), an equip (they
// dressed or undressed), and the crosshair (the NPC picker's target). The sinks only queue: every
// read happens in the pump, on the main thread.

namespace SH::Sinks
{
	// Attaches whatever is not attached yet. Idempotent: kGameDataReady finds the TES sources, the
	// crosshair's global source exists only once the HUD does, so every load tries again.
	void Attach();

	// "loaded: yes, equip: yes, crosshair: no" -- for the log and the MCM.
	[[nodiscard]] std::string Status();
}

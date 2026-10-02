#pragma once

// What Complexion listens to: an actor's 3D loading (they appeared). The sink only queues: every read happens in
// the pump, on the main thread.

namespace CX::Sinks
{
	// Attaches what is not attached yet. Idempotent: every load and every poll tries again.
	void Attach();

	// "loaded: yes" -- for the log and the MCM.
	[[nodiscard]] std::string Status();
}

#pragma once

#include "Director.h"

// Everything that touches the game: loading the catalog, reading actors into plain facts, and the
// pump that turns what the event sinks saw into Director calls. Reads happen on the main thread
// only -- in the pump, which the bridge calls as a native that is NOT callable from tasklets, and in
// the other natives marked the same way.

namespace SH::Game
{
	[[nodiscard]] Director& TheDirector();

	// kGameDataReady: the catalog, every manifest, and the forms the catalog names.
	void Load();

	// From the event sinks, on whatever thread the game sends them: queued, nothing read yet.
	void NoteLoaded(std::uint32_t a_ref);
	void NoteEquip(std::uint32_t a_ref, std::uint32_t a_item, bool a_equipped);
	void NoteCrosshair(std::uint32_t a_ref);

	// Main thread: everything queued since the last pump.
	void Pump();

	// Main thread. The NPC under the crosshair (0 for none, the player, or anyone Silhouette leaves
	// alone). a_recentSeconds > 0 also accepts the last NPC aimed at within that many seconds: a menu
	// opening takes the crosshair off them.
	[[nodiscard]] std::uint32_t CrosshairActor(float a_recentSeconds);

	// Main thread: an actor Silhouette may shape, by form id.
	[[nodiscard]] RE::Actor* ActorFor(std::uint32_t a_ref);
	[[nodiscard]] bool       IsFemale(RE::Actor* a_actor);
	[[nodiscard]] std::uint32_t BaseOf(RE::Actor* a_actor);
	[[nodiscard]] std::string   NameOf(RE::Actor* a_actor);

	// The director's log lines, into ours.
	void FlushLog();

	// A load is starting: what was queued belongs to the save being left.
	void ForgetInbox();
}

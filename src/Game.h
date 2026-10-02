#pragma once

#include "Director.h"

// Everything that touches the game: loading what LooksMenu loads and Complexion's data, reading actors into
// Facts, and the pump that turns what the event sinks saw into Director calls. Reads happen on the main thread
// only: in the pump, which the bridge calls as a native NOT callable from tasklets.
//
// Members only, never a virtual call on a game class: Runtime Database finds functions on OG, NG and AE, but
// not every class's virtual table is mapped the same (Silhouette S-75). Death, childhood and AAF scenes are
// asked in Papyrus by the bridge, when it carries an order out.

namespace CX::Game
{
	[[nodiscard]] Director& TheDirector();

	// kGameDataReady: profiles.json, tags.json (+ tags\*.json), every overlays.json LooksMenu reads, and the
	// factions the profile groups name.
	void Load();

	// A line for the player's screen, once a launch ("" after that and when there is nothing to say): Random
	// Overlay Framework is loaded, or Complexion's data is missing.
	[[nodiscard]] std::string TakeWarning();

	// From the event sink, on whatever thread the game sends it: queued, nothing read yet.
	void NoteLoaded(std::uint32_t a_ref);

	// Main thread: everything queued since the last pump.
	void Pump();

	// Main thread: an actor by form id, or null.
	[[nodiscard]] RE::Actor*  ActorFor(std::uint32_t a_ref);
	[[nodiscard]] std::string NameOf(RE::Actor* a_actor);
	// Main thread: what the game shows of them now, told to the director (as their 3D loading would).
	void See(RE::Actor* a_actor);

	void FlushLog();
	void ForgetInbox();
	void NoteAsked();
	void NoteGameLoaded();
	void ArmSweep();
}

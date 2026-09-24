#pragma once

// Where Fallout 4 1.10.163 keeps the event sources Silhouette listens to.
//
// CommonLibF4's getters are not all right for this runtime. TESEquipEvent::GetEventSource() CALLS
// REL::ID(485633) -- which the same library's TESInitScriptEventSource::GetSingleton() treats as the
// init-script source OBJECT -- so calling it executes data (F4MCP's log: "equip - the header's source
// getter faulted on this runtime"). So sources are found the way F4MCP finds them, and it is ported
// from there (fo4-mcp src/Matrix.cpp, the owner's own project): anchored on TESDeathEvent's source,
// whose getter is right here, the holder's members are walked 0x60 apart and named by the RTTI of
// the sinks registered on them -- the VM's own handler listens to every TES event, so every member
// has at least that one. Global sources (the crosshair) are found in BSTGlobalEvent's registry.

namespace SH::Events
{
	// The crosshair: the view caster's pick, a BSTValueEvent<ViewCasterUpdateData> -- a BSTOptional of the
	// data, with its flag after it. Layout from the CommonLibF4 fork Papyrus Common Library builds on
	// (LucaDotGit/CommonLibF4, ViewCasterUpdateData.hpp), whose GetCurrentCrosshairRef reads activatePickRef.
	//
	// Not PickRefStateChangedEvent, which Silhouette read until 2026-09-24 as F4MCP did: that one is a
	// BSTValueEvent<bool>, two bytes -- the HUD's "update the activate prompt" flag -- and the "ref at +08"
	// was the sender's stack. It held a door or a trapdoor often enough to pass for the crosshair, and hardly
	// ever an NPC, so the Pick hotkey never found anyone.
	struct ViewCasterUpdateEvent
	{
		std::uint32_t activatePickRef;     // 00  ObjectRefHandle: what the player would activate (talk to)
		std::uint32_t magnetismRef;        // 04
		std::uint32_t telekinesisPickRef;  // 08
		std::uint32_t dialoguePickRef;     // 0C  ObjectRefHandle
		void*         avObject;            // 10  the 3D the ray hit
		void*         shapeCastAVObject;   // 18
		std::uint32_t collisionGroup;      // 20
		std::uint32_t pad24;               // 24  ViewCasterData ends at 28
		bool          playerActivateable;  // 28
		std::uint32_t actorLifeState;      // 2C  BSTOptional<ACTOR_LIFE_STATE>: the value,
		bool          actorLifeStateSet;   // 30  and whether there is one
		std::uint8_t  pad31[7];            // 31
		bool          active;              // 38  the event's own optional: false, no pick data at all
	};
	static_assert(offsetof(ViewCasterUpdateEvent, dialoguePickRef) == 0x0C);
	static_assert(offsetof(ViewCasterUpdateEvent, avObject) == 0x10);
	static_assert(offsetof(ViewCasterUpdateEvent, playerActivateable) == 0x28);
	static_assert(offsetof(ViewCasterUpdateEvent, actorLifeState) == 0x2C);
	static_assert(offsetof(ViewCasterUpdateEvent, actorLifeStateSet) == 0x30);
	static_assert(offsetof(ViewCasterUpdateEvent, active) == 0x38);
	static_assert(sizeof(ViewCasterUpdateEvent) == 0x40);

	// The address of the holder member whose sinks listen to a_type, or 0.
	[[nodiscard]] std::uintptr_t FindHolderSource(std::string_view a_type);

	// The address of the global event source for a_type, or 0.
	[[nodiscard]] std::uintptr_t FindGlobalSource(std::string_view a_type);

	// Calls a plain function under a structured-exception guard; false if it faulted.
	bool Guarded(void (*a_fn)(void*), void* a_context);

	// A sink's event can hold a pointer to something being torn down, and naming such a pointer inside
	// a sink crashed F4MCP twice. These read the form id (TESForm +0x14) and form type (+0x1A) of the
	// object a pointer claims to be only after its vtable's RTTI checks out, calling nothing -- 0 when
	// it does not (ported from fo4-mcp src/Matrix.cpp).
	[[nodiscard]] std::uint32_t SafeFormID(const void* a_object);
	[[nodiscard]] std::uint8_t  SafeFormType(const void* a_object);
}

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
	struct PickRefStateChangedEvent
	{
		std::uint64_t                    unk00;  // 00
		RE::NiPointer<RE::TESObjectREFR> ref;    // 08  what the crosshair is on (F4MCP, measured)
	};

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

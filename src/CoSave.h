#pragma once

// The plugin's co-save: the director's records, under F4SE's serialization. Registered before
// the messaging listener, because a load can happen at once and the revert has to be in place first.

namespace CX::CoSave
{
	bool Register(const F4SE::SerializationInterface* a_intfc);

	// Nothing of the save being left may reach the next one: the director's records. F4SE's revert, and a new game.
	void Revert();
}

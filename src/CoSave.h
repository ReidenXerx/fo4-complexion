#pragma once

// The plugin's co-save (S-25): the director's records, under F4SE's serialization. Registered before
// the messaging listener, because a load can happen at once and the revert has to be in place first.

namespace SH::CoSave
{
	bool Register(const F4SE::SerializationInterface* a_intfc);

	// Nothing of the save being left may reach the next one: the director's records, and the records a
	// newer Silhouette wrote that this one keeps to write back. F4SE's revert, and a new game.
	void Revert();
}

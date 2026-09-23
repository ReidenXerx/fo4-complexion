#pragma once

// The plugin's co-save (S-25): the director's records, under F4SE's serialization. Registered before
// the messaging listener, because a load can happen at once and the revert has to be in place first.

namespace SH::CoSave
{
	bool Register(const F4SE::SerializationInterface* a_intfc);
}

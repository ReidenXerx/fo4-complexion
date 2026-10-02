#pragma once

// The natives of Complexion:DLL (papyrus/Complexion/DLL.psc): the bridge asks for orders and reports back. The
// plugin never calls into the Papyrus VM itself.

namespace CX::Papyrus
{
	bool Register(RE::BSScript::IVirtualMachine* a_vm);
}

#pragma once

// Silhouette:Plugin -- the functions the bridge and Silhouette:API call. The plugin never calls into
// the VM (S-18); everything goes this way round.

namespace SH::Papyrus
{
	bool Register(RE::BSScript::IVirtualMachine* a_vm);
}

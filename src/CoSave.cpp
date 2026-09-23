#include "CoSave.h"

#include "Game.h"

namespace SH::CoSave
{
	namespace
	{
		constexpr std::uint32_t kPluginID = 'SLHT';
		constexpr std::uint32_t kRecords = 'REC1';

		void OnSave(const F4SE::SerializationInterface* a_intfc)
		{
			// A reference that no longer exists (a created one the game deleted) is not written.
			const auto bytes = Game::TheDirector().SaveRecords([](std::uint32_t a_ref) { return RE::TESForm::GetFormByID(a_ref) != nullptr; });
			if (!a_intfc->OpenRecord(kRecords, Registry::kVersion) ||
				!a_intfc->WriteRecordData(bytes.data(), static_cast<std::uint32_t>(bytes.size()))) {
				logger::error("co-save: could not write the records - this save will not remember who Silhouette shaped");
				return;
			}
			logger::info("co-save: {} record(s) written", Game::TheDirector().RecordCount());
		}

		void OnLoad(const F4SE::SerializationInterface* a_intfc)
		{
			std::uint32_t type = 0;
			std::uint32_t version = 0;
			std::uint32_t length = 0;
			while (a_intfc->GetNextRecordInfo(type, version, length)) {
				if (type != kRecords) {
					logger::warn("co-save: unknown record {:08X} skipped", type);
					continue;
				}
				std::vector<std::byte> bytes(length);
				if (length && a_intfc->ReadRecordData(bytes.data(), length) != length) {
					logger::error("co-save: the records are cut short - none loaded");
					continue;
				}
				std::string error;
				const auto  resolve = [&](std::uint32_t a_saved) { return a_intfc->ResolveFormID(a_saved).value_or(0); };
				if (!Game::TheDirector().LoadRecords(bytes, version, resolve, error)) {
					logger::error("co-save: records not loaded ({})", error);
				}
			}
			logger::info("co-save: {} record(s) after loading", Game::TheDirector().RecordCount());
		}

		void OnRevert(const F4SE::SerializationInterface*)
		{
			Game::TheDirector().RevertRecords();
		}
	}

	bool Register(const F4SE::SerializationInterface* a_intfc)
	{
		if (!a_intfc) {
			return false;
		}
		a_intfc->SetUniqueID(kPluginID);
		a_intfc->SetRevertCallback(OnRevert);
		a_intfc->SetSaveCallback(OnSave);
		a_intfc->SetLoadCallback(OnLoad);
		return true;
	}
}

#include "CoSave.h"

#include "Compat.h"
#include "Game.h"

namespace CX::CoSave
{
	namespace
	{
		constexpr std::uint32_t kPluginID = 'CMPX';
		constexpr std::uint32_t kRecords = 'REC1';

		void OnSave(const F4SE::SerializationInterface* a_intfc)
		{
			const auto bytes = Game::TheDirector().Save();
			if (!a_intfc->OpenRecord(kRecords, 1) || !a_intfc->WriteRecordData(bytes.data(), static_cast<std::uint32_t>(bytes.size()))) {
				logger::error("co-save: could not write the records - this save will not remember who Complexion decided about");
				return;
			}
			logger::info("co-save: {} record(s) written", Game::TheDirector().RecordCount());
		}

		void OnLoad(const F4SE::SerializationInterface* a_intfc)
		{
			std::uint32_t type = 0;
			std::uint32_t version = 0;
			std::uint32_t length = 0;
			while (Compat::NextRecordInfo(a_intfc, type, version, length)) {
				if (type != kRecords) {
					logger::warn("co-save: unknown record {:08X} skipped", type);
					continue;
				}
				std::vector<std::uint8_t> bytes(length);
				if (length && a_intfc->ReadRecordData(bytes.data(), length) != length) {
					logger::error("co-save: the records are cut short - none loaded");
					continue;
				}
				const auto resolve = [&](std::uint32_t a_saved) { return a_intfc->ResolveFormID(a_saved).value_or(0); };
				if (!Game::TheDirector().Load(bytes, resolve)) {
					logger::error("co-save: records not loaded (version {} or damaged) - everyone is decided anew as they are seen", version);
				}
			}
			logger::info("co-save: {} record(s) after loading", Game::TheDirector().RecordCount());
		}

		void OnRevert(const F4SE::SerializationInterface*)
		{
			Revert();
		}
	}

	void Revert()
	{
		Game::TheDirector().Revert();
	}

	bool Register(const F4SE::SerializationInterface* a_intfc)
	{
		if (!a_intfc) {
			return false;
		}
		Compat::SetUniqueID(a_intfc, kPluginID);
		a_intfc->SetRevertCallback(OnRevert);
		a_intfc->SetSaveCallback(OnSave);
		a_intfc->SetLoadCallback(OnLoad);
		return true;
	}
}

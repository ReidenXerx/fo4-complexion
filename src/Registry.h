#pragma once

#include "Plan.h"

// What the plugin remembers per reference between saves (S-25, S-43): INTENT -- who chose which body --
// and what it has already done to that body. Never the body itself: that is LooksMenu's, and every
// session reads it back (S-43). No game types: the co-save glue hands these bytes to F4SE, and the
// offline tests read them back.

namespace SH
{
	// Who chose the body the actor should have. Stored as a byte: the values never change meaning.
	enum class Source : std::uint8_t
	{
		kNone = 0,           // BodyGen's roll, or nothing of ours
		kNameRule = 1,       // an npc rule by name (S-23)
		kFactionRule = 2,    // a faction rule (S-23)
		kPicker = 3,         // the player, with the NPC picker (S-22)
		kAPI = 4,            // another mod, through Silhouette:API (S-24)
		kNameBlacklist = 5,  // kept bare by the name blacklist (S-23)
	};

	[[nodiscard]] std::string_view SourceName(Source a_source);

	struct Record
	{
		std::uint32_t base{ 0 };  // the NPC record it was written for: a created reference's id is reused
		Source        source{ Source::kNone };
		std::string   preset;     // the body they should have ("" for BodyGen's own, or bare)
		std::uint32_t stamp{ 0 };  // the build whose values that body has
		std::uint32_t announced{ 0 };  // BodyHash of the body OnActorGenerated was raised for; 0 = none
		std::uint32_t touched{ 0 };    // BodyHash of the body the touch-up (S-29, S-44) finished; 0 = none

		// Nothing worth keeping: the record can go.
		[[nodiscard]] bool Empty() const
		{
			return source == Source::kNone && preset.empty() && announced == 0 && touched == 0;
		}
	};

	// The NPC picker, while someone is being picked (S-47): the body they had and the choice behind it.
	struct PickerSave
	{
		std::uint32_t         ref{ 0 };
		std::uint32_t         base{ 0 };
		bool                  female{ false };
		Morphs                snapshot;  // their whole unkeyed layer at Pick
		std::optional<Record> before;
	};

	class Registry
	{
	public:
		static constexpr std::uint32_t kVersion = 1;

		[[nodiscard]] Record*       Find(std::uint32_t a_ref);
		[[nodiscard]] const Record* Find(std::uint32_t a_ref) const;
		Record&                     Get(std::uint32_t a_ref);
		void                        Erase(std::uint32_t a_ref) { _records.erase(a_ref); }
		void                        Clear()
		{
			_records.clear();
			picker.reset();
		}
		void                      Prune(std::uint32_t a_ref);  // erases it if Empty()
		[[nodiscard]] std::size_t Size() const { return _records.size(); }

		[[nodiscard]] const std::unordered_map<std::uint32_t, Record>& All() const { return _records; }

		std::optional<PickerSave> picker;

		// The bytes for the co-save. a_keep says which references still exist; the rest are not
		// written (a created reference that was deleted, or a record with nothing in it).
		[[nodiscard]] std::vector<std::byte> Serialize(const std::function<bool(std::uint32_t)>& a_keep) const;

		// Replaces everything with what the bytes hold. a_resolve maps a saved form id to this session's
		// (0: that form is gone, and so is its record). False, and nothing replaced, when the bytes are
		// not a record list of this version.
		bool Deserialize(std::span<const std::byte> a_bytes, std::uint32_t a_version,
			const std::function<std::uint32_t(std::uint32_t)>& a_resolve, std::string& a_error);

	private:
		std::unordered_map<std::uint32_t, Record> _records;
	};
}

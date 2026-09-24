#pragma once

#include "Plan.h"

#include <unordered_set>

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
		kReset = 6,          // made bare by Reset: a new body at the next load (S-53)
		kRoll = 7,           // a roll owed: Back to random or the regeneration window asked, not landed yet (S-59)
	};

	[[nodiscard]] std::string_view SourceName(Source a_source);

	struct Record
	{
		std::uint32_t base{ 0 };  // the NPC record it was written for: a created reference's id is reused
		Source        source{ Source::kNone };
		std::string   preset;         // the body they should have ("" for BodyGen's own, or bare)
		std::uint32_t stamp{ 0 };      // the build whose values that body has; a reset's is 0 until it has landed (S-59)
		std::uint32_t announced{ 0 };  // BodyHash of the body OnActorGenerated was raised for; 0 = none
		std::uint32_t touched{ 0 };    // TouchKey the touch-up (S-29, S-44) last finished; 0 = none
		std::uint32_t salt{ 0 };       // Back to random's presses under a rule: each draws from it again (S-60); 0 = by id alone

		// Nothing worth keeping: the record can go.
		[[nodiscard]] bool Empty() const
		{
			return source == Source::kNone && preset.empty() && announced == 0 && touched == 0 && salt == 0;
		}

		// What neither the rules nor LooksMenu can give back if it is lost: a choice, a roll or a reset owed,
		// a rule drawn again. The rest (a rule's draw, what was announced or touched) is worked out anew.
		[[nodiscard]] bool Intent() const
		{
			return source == Source::kPicker || source == Source::kAPI || source == Source::kReset || source == Source::kRoll || salt != 0;
		}
	};

	// A picking in progress, or one whose Cancel has not reached the body yet (S-47): the body they had
	// and the choice behind it. One per actor: picking someone else never loses it.
	struct PickerSave
	{
		std::uint32_t         ref{ 0 };
		std::uint32_t         base{ 0 };
		bool                  female{ false };
		Morphs                snapshot;  // their whole unkeyed layer at Pick
		std::optional<Record> before;
		std::uint32_t         seq{ 0 };  // order of arrival, for the cap
	};

	class Registry
	{
	public:
		// 2: each record and picking carries its own length, so a later version can append fields that
		// this one skips. 1 was never written by a released plugin. Appended since, read when present:
		// a record's salt (S-60); a picking's arrival order, then its record's salt. New fields go on the
		// end of an item, never a new version: a version this plugin does not know is not read at all.
		static constexpr std::uint32_t kVersion = 2;
		static constexpr std::size_t   kMaxPickings = 64;

		[[nodiscard]] Record*       Find(std::uint32_t a_ref);
		[[nodiscard]] const Record* Find(std::uint32_t a_ref) const;
		Record&                     Get(std::uint32_t a_ref);
		void                        Erase(std::uint32_t a_ref) { _records.erase(a_ref); }
		void                        Clear()
		{
			_records.clear();
			pickings.clear();
			resetStamps.clear();
			resetMet.clear();
		}
		void                      Prune(std::uint32_t a_ref);  // erases it if Empty()
		[[nodiscard]] std::size_t Size() const { return _records.size(); }

		[[nodiscard]] const std::unordered_map<std::uint32_t, Record>& All() const { return _records; }

		// Keyed by reference. Adding one past the cap drops the oldest.
		std::map<std::uint32_t, PickerSave> pickings;
		void                                Keep(PickerSave a_save);

		// S-68, MCM's "Reset everyone": the builds whose bodies count as made after the last press -- the one
		// current at the press, and each newer one since. Empty: never pressed.
		std::vector<std::uint32_t> resetStamps;

		// S-70: everyone looked at since the press. A body Silhouette did not make cannot be dated, so it is
		// decided again at the first sighting after the press and only then: sliders set by hand, or another
		// mod's body, put on someone after that are theirs to keep.
		std::unordered_set<std::uint32_t> resetMet;

		// The press, for everyone on record wherever they are: a choice (the picker's, another mod's) or a
		// picking in progress becomes a roll owed (S-59 carries it to their next sighting), and a rule's draw
		// goes back to the draw by id alone. How many records that changed.
		std::size_t ForgetChoices();

		// The bytes for the co-save. a_keep(ref, base, intent) says which records and pickings to write
		// (KeepInCoSave is the plugin's rule); a record with nothing in it never is. a_intent: it holds what
		// cannot be worked out again (Record::Intent; every picking does). It runs under the caller's
		// lock: it must not call back into whoever holds this registry.
		using KeepFn = std::function<bool(std::uint32_t a_ref, std::uint32_t a_base, bool a_intent)>;
		[[nodiscard]] std::vector<std::byte> Serialize(const KeepFn& a_keep) const;

		enum class Loaded
		{
			kOk,
			kRefused,  // not a record list: nothing replaced
			kNewer,    // written by a later version: nothing replaced, and the bytes must be kept as they are
		};

		// Replaces everything with what the bytes hold. a_resolve maps a saved form id to this session's
		// (0: that form is gone, and so is its record).
		Loaded Deserialize(std::span<const std::byte> a_bytes, std::uint32_t a_version,
			const std::function<std::uint32_t(std::uint32_t)>& a_resolve, std::string& a_error);

		// The reset's own co-save record (resetStamps, then resetMet), apart from the records: written only once
		// it has been pressed, so a save that never was is as before, and an older plugin skips it. A later
		// field is appended, never a new version: a plugin refuses a version newer than its own, and skips
		// the bytes after what it knows (the first plugin to write this record knew only the stamps).
		static constexpr std::uint32_t         kResetVersion = 1;
		[[nodiscard]] std::vector<std::byte> SerializeReset() const;
		// a_resolve maps a saved form id to this session's (0: gone); none keeps them as they are.
		Loaded DeserializeReset(std::span<const std::byte> a_bytes, std::uint32_t a_version, std::string& a_error,
			const std::function<std::uint32_t(std::uint32_t)>& a_resolve = {});

	private:
		std::unordered_map<std::uint32_t, Record> _records;
		std::uint32_t                             _seq{ 0 };
	};

	// Whether the co-save keeps a record or picking. A placed reference always: it exists in its plugin
	// even while its cell is out of memory, and a load drops it when the plugin is gone. A created one
	// (0xFF) is handed to whoever is created next once it is deleted, so its bookkeeping is kept only while
	// it is still an actor of the same NPC (a_liveBase: its NPC now, nullopt when it is not in memory) --
	// but intent always: a created NPC whose cell is unloaded is not gone, and an id handed to someone else
	// is caught at the next sighting, where Admit sees the other NPC and forgets it (S-57).
	[[nodiscard]] bool KeepInCoSave(std::uint32_t a_ref, std::uint32_t a_base, bool a_intent, std::optional<std::uint32_t> a_liveBase);
}

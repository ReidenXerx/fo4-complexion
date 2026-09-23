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
		kReset = 6,          // made bare by Reset: a new body at the next load (S-53)
	};

	[[nodiscard]] std::string_view SourceName(Source a_source);

	struct Record
	{
		std::uint32_t base{ 0 };  // the NPC record it was written for: a created reference's id is reused
		Source        source{ Source::kNone };
		std::string   preset;         // the body they should have ("" for BodyGen's own, or bare)
		std::uint32_t stamp{ 0 };      // the build whose values that body has
		std::uint32_t announced{ 0 };  // BodyHash of the body OnActorGenerated was raised for; 0 = none
		std::uint32_t touched{ 0 };    // TouchKey the touch-up (S-29, S-44) last finished; 0 = none

		// Nothing worth keeping: the record can go.
		[[nodiscard]] bool Empty() const
		{
			return source == Source::kNone && preset.empty() && announced == 0 && touched == 0;
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
		// this one skips. 1 was never written by a released plugin.
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
		}
		void                      Prune(std::uint32_t a_ref);  // erases it if Empty()
		[[nodiscard]] std::size_t Size() const { return _records.size(); }

		[[nodiscard]] const std::unordered_map<std::uint32_t, Record>& All() const { return _records; }

		// Keyed by reference. Adding one past the cap drops the oldest.
		std::map<std::uint32_t, PickerSave> pickings;
		void                                Keep(PickerSave a_save);

		// The bytes for the co-save. a_keep(ref, base) says which references are still the NPC the
		// record or picking was about; the rest are not written (a created reference that was deleted or
		// handed to someone new, or a record with nothing in it). It runs under the caller's lock: it
		// must not call back into whoever holds this registry.
		using KeepFn = std::function<bool(std::uint32_t a_ref, std::uint32_t a_base)>;
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

	private:
		std::unordered_map<std::uint32_t, Record> _records;
		std::uint32_t                             _seq{ 0 };
	};
}

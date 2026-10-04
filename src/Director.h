#pragma once

#include "Compose.h"

// Who Complexion has decided about, and the work the Papyrus bridge carries out. No game in here: the game
// side (Game.cpp) reads actors into Facts on the main thread, and the bridge asks for orders through natives.
//
// The rules it holds (docs/complexion-decisions.md):
// - one decision per NPC, made the first time they are seen and kept (C-4); a Reset rolls everyone again;
// - the player, the dead, children and anyone not human are never touched (C-4, Silhouette S-81);
// - an order is a whole look: the bridge adds every entry and calls Update once, then checks with GetAll that
//   each landed (C-6); ours take negative priorities, so the bridge tells ours from every other mod's by the sign.

namespace CX
{
	struct Facts
	{
		std::uint32_t ref{ 0 };
		std::uint32_t base{ 0 };
		bool          female{ false };
		std::string   group;   // the profile group their factions match; "" = the default
		std::string   name;    // for the log
		std::string   skip;    // why they are left alone ("dead", "player", "child", "race ..."), "" = eligible
		std::string   hair;    // their head hair's colour family (profiles.json hair_colours); "" = unknown
	};

	struct Record
	{
		bool              female{ false };
		std::uint32_t     base{ 0 };  // the NPC record, part of the seed
		std::string       group;
		std::string       persona;  // Rapport's, as the bridge read it (C-14); "" = none
		std::vector<Pick> picks;
		bool              applied{ false };  // the bridge confirmed every entry landed
		bool              manual{ false };   // chosen by hand in the overlay window (C-19): kept as it is
		std::string       hair;              // the head hair family it was decided with ("" = unknown)
		bool              hairChecked{ true };  // false for a record from a save before v4: its hair is checked once
	};

	struct Order
	{
		std::uint32_t     id{ 0 };
		std::uint32_t     ref{ 0 };
		bool              female{ false };
		std::vector<Pick> picks;
		bool              window{ false };  // the overlay window's preview: done, it changes no record
	};

	class Director
	{
	public:
		// The composition data, at kGameDataReady and again when settings change.
		void SetData(Profiles a_profiles, std::vector<Template> a_catalog);
		void SetEnabled(bool a_enabled);
		void SetAdult(bool a_adult);

		// Someone's 3D loaded (or a sweep read them): decides about them if nobody has yet, and queues the
		// work when what was decided has not been confirmed on them.
		void Seen(const Facts& a_facts);

		// The bridge's side. NextOrder hands out one order at a time per actor; 0 when there is none.
		[[nodiscard]] std::uint32_t        NextOrder();
		[[nodiscard]] std::optional<Order> GetOrder(std::uint32_t a_id) const;
		// Every entry landed: the record is confirmed. a_landed false: the bridge rebuilt once and it still
		// did not land; the record stays unconfirmed and the next sighting tries again.
		void Done(std::uint32_t a_id, bool a_landed);
		// Not loaded, dead now, or busy in another mod's scene: the work waits for the next sighting.
		void Gone(std::uint32_t a_id);
		// The bridge saw a faction the record does not carry (a raider's captive is put in CaptiveFaction on the
		// reference at run time): the look is composed again for a_group, with the same seed, before it is put on.
		// False when the order or the group is unknown. Only for a look not yet confirmed on them.
		bool Regroup(std::uint32_t a_id, std::string_view a_group);
		[[nodiscard]] std::string GroupOf(std::uint32_t a_id) const;
		// The bridge read their Rapport persona: a look not yet put on them is composed again with it. Returns
		// whether the look changed.
		bool SetPersona(std::uint32_t a_id, std::string_view a_persona);

		// MCM "Roll everyone again": a new salt, every record forgotten; whoever is seen next is decided anew
		// (the bridge replaces our old entries, which it knows by their negative priority).
		void ResetAll();
		// After LooksMenu's ClearAll (the ROF cleanup): every decision kept, none of it on anyone any more.
		void Unapply();

		// A load or a new game: what was queued belongs to the save being left.
		void ForgetQueue();

		[[nodiscard]] std::size_t RecordCount() const;
		[[nodiscard]] std::size_t PendingCount() const;
		[[nodiscard]] std::optional<Record> RecordFor(std::uint32_t a_ref) const;

		// The co-save. Load takes a resolver for form ids from another load order (0 = gone).
		[[nodiscard]] std::vector<std::uint8_t> Save() const;
		bool Load(std::span<const std::uint8_t> a_bytes, const std::function<std::uint32_t(std::uint32_t)>& a_resolve);
		void Revert();

		// Lines for the log, taken by Game::FlushLog on the main thread.
		[[nodiscard]] std::vector<std::string> TakeLog();

		[[nodiscard]] std::uint64_t Salt() const;
		void SetSalt(std::uint64_t a_salt);

		// ---- the overlay window (C-19): one session at a time, on one actor ----
		// Where each of Complexion's own templates has its picture: key -> (atlas, cell), and the build of the atlases.
		void SetThumbs(std::unordered_map<std::string, std::pair<int, int>> a_cells, std::string a_build);
		// Where each of Complexion's own templates sits on the body (thumbs.json "focus"), key -> 8 numbers.
		void SetSpots(std::unordered_map<std::string, std::array<float, 8>> a_spots);
		// Where a template sits, for the window's camera: its measured spot, else a spot for its tagged region
		// (other packs' templates); nullopt for one over the whole body or unknown.
		[[nodiscard]] std::optional<std::array<float, 8>> SpotOf(std::string_view a_key) const;
		[[nodiscard]] std::string ThumbBuild() const;
		// Opens a session on a_ref (an NPC, or the player): what Complexion put on them is the draft. "" or why not.
		[[nodiscard]] std::string WindowBegin(std::uint32_t a_ref, bool a_female, std::string_view a_hair = {});
		void WindowEnd();
		// One page of a category ("on", "all", "skin", "hair", "scars", "tattoos", "rough", "paint", "nails"),
		// searched: "<total>|<entry>|<entry>...", an entry "key\tlabel\tkind\ton\tatlas\tcell" (atlas -1: no picture).
		[[nodiscard]] std::string WindowPage(std::string_view a_category, std::string_view a_search, int a_page, int a_per) const;
		// Puts a template on the draft or takes it off: whether it is on now.
		bool WindowToggle(std::string_view a_key);
		[[nodiscard]] std::size_t WindowCount() const;
		void WindowClear();
		// A new random look, as Complexion would roll one for them, into the draft.
		void WindowRoll();
		// An order carrying the draft (Preview) or what they had before (Restore), for the bridge to put on now.
		[[nodiscard]] std::uint32_t WindowPreview();
		[[nodiscard]] std::uint32_t WindowRestore();
		// Apply: the draft is their look from now on, kept until rolled again.
		void WindowApply();

	private:
		void Log(std::string a_line);
		[[nodiscard]] std::uint64_t SeedFor(std::uint32_t a_ref, std::uint32_t a_base) const;

		mutable std::mutex                                 _lock;
		Profiles                                           _profiles;
		std::vector<Template>                              _catalog;
		bool                                               _enabled{ true };
		bool                                               _adult{ true };
		std::uint64_t                                      _salt{ 0x436F6D706C786E31ull };
		std::unordered_map<std::uint32_t, Record>          _records;
		std::deque<std::uint32_t>                          _queue;     // refs waiting for an order
		std::unordered_map<std::uint32_t, Order>           _inflight;  // order id -> order
		std::uint32_t                                      _nextId{ 1 };
		std::vector<std::string>                           _log;

		struct Window
		{
			bool                  active{ false };
			std::uint32_t         ref{ 0 };
			bool                  female{ false };
			std::optional<Record> before;  // their record when the window opened, if any
			std::vector<Pick>     draft;
			std::string           hair;    // their head hair family: Random matches it
			std::uint32_t         rolls{ 0 };
		};
		Window                                                  _window;
		std::unordered_map<std::string, std::pair<int, int>>    _thumbs;
		std::string                                             _thumbBuild;
		std::unordered_map<std::string, std::array<float, 8>>   _spots;

		[[nodiscard]] const Template* Find(std::string_view a_key) const;
		// A hair overlay among a_picks that their head hair family does not accept (a record decided before 0.1.3).
		[[nodiscard]] bool HairClashes(const std::vector<Pick>& a_picks, std::string_view a_hair) const;
		[[nodiscard]] std::vector<Pick> Repriority(std::vector<Pick> a_picks) const;
		[[nodiscard]] std::uint32_t WindowOrder(std::vector<Pick> a_picks);
	};
}

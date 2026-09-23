#pragma once

#include "Catalog.h"
#include "Plan.h"
#include "Registry.h"
#include "Rules.h"

// The plugin's whole decision-making, with no game in it (S-18): what the game side saw goes in,
// orders for the bridge come out, and what the bridge reports comes back. The game side reads actors
// on the main thread and hands over plain facts; the offline tests do the same by hand, so every
// path below runs in the tests exactly as it runs in the game.
//
// Thread-safe: the natives call in from Papyrus threads and the pump from the main thread, so every
// public member takes the one lock. Nothing here calls out while holding it.

namespace SH
{
	// One change to an actor's body that the plugin has decided on and the bridge has not made yet.
	struct BodyRequest
	{
		enum class What
		{
			kPreset,      // a preset (and its variety), replacing the unkeyed layer
			kBlacklist,   // bare, with the blacklist marker (S-23)
			kRestore,     // the picker's Cancel: exactly the unkeyed layer they had
			kRegenerate,  // BodyGen rolls again, keyed layers kept
			kReset,       // the unkeyed layer removed: bare now; once a save is loaded LooksMenu has
			              // dropped the emptied entries and BodyGen rolls them again
		};

		What                  what{ What::kPreset };
		std::string           preset;
		Source                source{ Source::kNone };
		bool                  preview{ false };  // the picker trying a preset on: not recorded
		Morphs                restore;
		std::optional<Record> restoreRecord;
	};

	// What the game side read about an actor, on the main thread.
	struct Sighting
	{
		std::uint32_t ref{ 0 };
		std::uint32_t base{ 0 };        // the NPC record's runtime form id
		ActorFacts    facts;
		bool          eligible{ true };  // false: the player, the character-creation dummies
		bool          clothed{ false };
		std::string   outfitSet;         // the refit set the worn outfit brings, "" for none
	};

	enum class EventKind : std::int32_t
	{
		kGenerated = 1,        // OnActorGenerated(actor, preset)
		kNaked = 2,            // OnActorNaked(actor)
		kRemovingClothes = 3,  // OnActorRemovingClothes(actor)
		kORefitChanged = 4,    // OnORefitChanged(actor, applied)
	};

	struct Event
	{
		std::uint32_t id{ 0 };
		EventKind     kind{ EventKind::kGenerated };
		std::uint32_t ref{ 0 };
		std::string   preset;
		bool          flag{ false };
	};

	enum class OrderKind : std::int32_t
	{
		kProbe = 1,     // which body do they have
		kBody = 2,      // change it
		kRefit = 3,     // ORefit on or off
		kSnapshot = 4,  // the picker's copy of the whole unkeyed layer
	};

	// One job for the bridge. It does, in this order: regenerate, probe, the reads, Prepare, clear,
	// the writes, update; then reports Done. Every value it writes was decided here.
	struct Order
	{
		std::uint32_t id{ 0 };
		std::uint32_t ref{ 0 };
		bool          female{ false };
		OrderKind     kind{ OrderKind::kProbe };

		bool                     regenerate{ false };
		bool                     probe{ false };
		bool                     readAll{ false };
		std::vector<std::string> reads;

		std::string        marker;  // reported by the probe
		float              markerValue{ 0.0F };
		std::vector<float> readValues;  // parallel to reads; NaN until reported
		Morphs             layer;       // reported by readAll

		bool   readsDecided{ false };
		bool   prepared{ false };
		bool   clear{ false };
		Morphs writes;
		bool   update{ false };

		BodyRequest body;
		bool        refitOn{ false };
		std::string refitSet;
		Morphs      refitSnapshot;
	};

	struct Settings
	{
		bool            orefit{ true };  // MCM, and SetORefit (S-24)
		VarietySwitches variety;
	};

	class Director
	{
	public:
		// --- lifecycle ---
		void SetCatalog(std::shared_ptr<const Catalog> a_catalog);
		void Refuse(std::string a_why);  // no catalog, or one that cannot be trusted: act on nothing
		[[nodiscard]] bool        Ready() const;
		[[nodiscard]] std::string Status() const;
		[[nodiscard]] std::shared_ptr<const Catalog> CatalogPtr() const;

		void Configure(const Settings& a_settings);
		[[nodiscard]] Settings Current() const;

		// A save is being left: everything about the world goes, the records stay (the co-save's).
		void ForgetWorld();
		// The co-save is reverting (new game, or before a load): the records go too.
		void RevertRecords();

		// --- what the game saw ---
		void Seen(const Sighting& a_sighting);
		// An equip event was handled: a_sighting is the actor after it. a_removedClothing: the event
		// took off an item that dresses them (OnActorRemovingClothes).
		void Dressed(const Sighting& a_sighting, bool a_removedClothing);

		// --- requests (API, MCM, picker) ---
		bool RequestPreset(std::uint32_t a_ref, bool a_female, std::uint32_t a_base, std::string_view a_preset, Source a_source, std::string& a_why);
		bool RequestRegenerate(std::uint32_t a_ref, bool a_female, std::uint32_t a_base);
		bool RequestReset(std::uint32_t a_ref, bool a_female, std::uint32_t a_base);
		// The body they have, again, with this build's values: their record's preset, or the one their
		// marker names (a_markerPreset, from a probe) for a body BodyGen gave.
		bool RequestReapply(std::uint32_t a_ref, bool a_female, std::uint32_t a_base, std::string_view a_markerPreset, std::string& a_why);

		// --- the bridge ---
		[[nodiscard]] std::uint32_t NextOrder();
		[[nodiscard]] std::optional<Order> Peek(std::uint32_t a_order) const;
		void NoteMarker(std::uint32_t a_order, std::string_view a_marker, float a_value);
		// How many morphs to read before Prepare. For a refit, decided on this first call, after the
		// probe: which set applies can depend on the preset.
		[[nodiscard]] std::int32_t ReadCount(std::uint32_t a_order);
		[[nodiscard]] std::string  ReadMorph(std::uint32_t a_order, std::int32_t a_index) const;
		void NoteRead(std::uint32_t a_order, std::int32_t a_index, float a_value);
		void NoteLayer(std::uint32_t a_order, std::string_view a_morph, float a_value);
		bool Prepare(std::uint32_t a_order);
		[[nodiscard]] bool         Clears(std::uint32_t a_order) const;
		[[nodiscard]] bool         Updates(std::uint32_t a_order) const;
		[[nodiscard]] std::int32_t WriteCount(std::uint32_t a_order) const;
		[[nodiscard]] std::string  WriteMorph(std::uint32_t a_order, std::int32_t a_index) const;
		[[nodiscard]] float        WriteValue(std::uint32_t a_order, std::int32_t a_index) const;
		void Done(std::uint32_t a_order, bool a_ok);
		[[nodiscard]] std::size_t Pending() const;

		// Events for the bridge to raise, oldest first. 0: none.
		[[nodiscard]] std::uint32_t        NextEvent();
		[[nodiscard]] std::optional<Event> EventAt(std::uint32_t a_event) const;

		// --- the NPC picker (S-22) ---
		std::string PickerStart(std::uint32_t a_ref, bool a_female, std::uint32_t a_base, std::string_view a_name);
		std::string PickerStep(std::int32_t a_step);
		std::string PickerKeep();
		std::string PickerCancel();
		[[nodiscard]] std::uint32_t PickerTarget() const;
		[[nodiscard]] bool          PickerReady() const;  // the snapshot is in: Next can start

		// --- uninstalling ---
		// Everyone the records say carries a refit, loaded or not.
		[[nodiscard]] std::vector<std::uint32_t> RefitRefs() const;
		// Their naked values back, whether or not they were seen this session (ORefit must be off,
		// or anyone seen dressed is refit again).
		void RefitOff(std::uint32_t a_ref, bool a_female, std::uint32_t a_base);

		// --- queries ---
		[[nodiscard]] std::string AssignedPreset(std::uint32_t a_ref) const;
		[[nodiscard]] bool        RefitApplied(std::uint32_t a_ref) const;
		[[nodiscard]] std::string Describe(std::uint32_t a_ref) const;

		// --- the co-save (S-25) ---
		[[nodiscard]] std::vector<std::byte> SaveRecords(const std::function<bool(std::uint32_t)>& a_keep) const;
		bool LoadRecords(std::span<const std::byte> a_bytes, std::uint32_t a_version,
			const std::function<std::uint32_t(std::uint32_t)>& a_resolve, std::string& a_error);
		[[nodiscard]] std::size_t RecordCount() const;
		[[nodiscard]] std::optional<Record> RecordOf(std::uint32_t a_ref) const;

		// Lines for the log, taken by the game side (the director never logs itself: no game here).
		[[nodiscard]] std::vector<std::string> TakeLog();

	private:
		struct Work
		{
			bool                       snapshot{ false };
			std::optional<BodyRequest> body;
			bool                       refit{ false };
			bool                       probe{ false };

			[[nodiscard]] bool Empty() const { return !snapshot && !body && !refit && !probe; }
		};

		struct Session
		{
			bool          known{ false };  // seen this session, with facts
			bool          eligible{ false };
			bool          female{ false };
			std::uint32_t base{ 0 };
			bool          clothed{ false };
			std::string   outfitSet;
			ActorFacts    facts;
			bool          probed{ false };      // asked about once this session
			bool          refitStale{ false };  // dressed in another outfit while a refit was on
		};

		struct Picker
		{
			std::uint32_t            ref{ 0 };
			bool                     female{ false };
			std::uint32_t            base{ 0 };
			std::string              name;
			std::vector<std::string> presets;
			std::int32_t             index{ -1 };  // -1: nothing tried on yet
			bool                     snapped{ false };
			Morphs                   snapshot;  // the naked unkeyed layer at Pick
			std::string              current;   // the preset they had at Pick, "" unknown
			std::optional<Record>    before;
		};

		// all of these expect the lock held
		void               Admit(Session& a_session, const Sighting& a_sighting);
		[[nodiscard]] Order* Find(std::uint32_t a_order);
		std::string        CancelPicking();
		void               Log(std::string a_line);
		void               Push(EventKind a_kind, std::uint32_t a_ref, std::string a_preset = {}, bool a_flag = false);
		Work&              WorkFor(std::uint32_t a_ref, bool a_front = false);
		void               Queue(std::uint32_t a_ref, BodyRequest a_body, bool a_front = false);
		void               DecideBody(std::uint32_t a_ref, Session& a_session);
		[[nodiscard]] bool WantsRefit(const Session& a_session) const;
		void               ReconcileRefit(std::uint32_t a_ref, bool a_front = false);
		[[nodiscard]] bool AnyRefitSet(bool a_female) const;
		[[nodiscard]] bool PresetRefitSets(bool a_female) const;
		void               Announce(const Order& a_order);
		[[nodiscard]] std::string PresetNamedBy(std::string_view a_marker, float a_value) const;
		void               FinishBody(Order& a_order);
		void               FinishRefit(Order& a_order);
		void               ClosePicker();

		mutable std::mutex _lock;

		std::shared_ptr<const Catalog> _catalog;
		std::string                    _status{ "starting" };
		Settings                       _settings;

		Registry                                    _registry;
		std::unordered_map<std::uint32_t, Session>  _sessions;
		std::unordered_map<std::uint32_t, Work>     _work;
		std::deque<std::uint32_t>                   _queue;  // references with work, in turn
		std::unordered_map<std::uint32_t, Order>    _inflight;
		std::unordered_set<std::uint32_t>           _busy;  // references with an order in flight
		std::deque<Event>                           _events;
		std::deque<Event>                           _taken;  // the last few handed out, for their details
		bool                                        _eventsDropped{ false };
		std::uint32_t                               _nextOrder{ 1 };
		std::uint32_t                               _nextEvent{ 1 };
		Picker                                      _picker;
		std::vector<std::string>                    _log;
	};
}

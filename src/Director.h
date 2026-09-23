#pragma once

#include "Catalog.h"
#include "Plan.h"
#include "Registry.h"
#include "Rules.h"

// The plugin's whole decision-making, with no game in it (S-18): what the game side saw goes in, orders
// for the bridge come out, and what the bridge reports comes back. The game side reads actors on the
// main thread and hands over plain facts; the offline tests do the same by hand, so every path below
// runs in the tests exactly as it runs in the game.
//
// Truth first (S-43): the co-save holds INTENT -- who chose which body -- and LooksMenu holds the body.
// Every session begins each actor with a probe of LooksMenu, and orders make the body match the intent.
// Every order is safe to repeat, so a save that lands in the middle of one is repaired by the next probe.
//
// Thread-safe: the natives call in from Papyrus threads and the pump from the main thread, so every
// public member takes the one lock. The co-save callbacks run the registry's bytes under it too.

namespace SH
{
	// One change to an actor's body that the plugin has decided on and the bridge has not made yet.
	struct BodyRequest
	{
		enum class What
		{
			kPreset,      // a preset (and its variety), replacing the unkeyed layer
			kBlacklist,   // bare, with the blacklist marker, no refit (S-23)
			kRestore,     // the picker's Cancel: exactly the unkeyed layer they had
			kRegenerate,  // BodyGen rolls again, keyed layers kept
			kReset,       // the unkeyed layer and the refit removed: bare until BodyGen after a load (S-27)
		};

		What        what{ What::kPreset };
		std::string preset;
		bool        preview{ false };      // the picker trying a preset on: not intent
		bool        keepVariety{ false };  // Refresh / Reapply: keep the variety they already have
		Morphs      restore;
	};

	// What the game side read about an actor, on the main thread.
	struct Sighting
	{
		std::uint32_t ref{ 0 };
		std::uint32_t base{ 0 };        // the NPC record's runtime form id
		ActorFacts    facts;
		bool          eligible{ true };  // false: the player, the character-creation dummies
		bool          clothed{ false };
		bool          heavy{ false };    // S-42
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
		std::uint32_t announce{ 0 };  // kGenerated: the body it announces, recorded when handed out
	};

	enum class OrderKind : std::int32_t
	{
		kProbe = 1,     // what LooksMenu holds for them
		kBody = 2,      // change the body
		kRefit = 3,     // the refit layer on or off (S-40)
		kSnapshot = 4,  // the picker's copy of the whole unkeyed layer
		kTouch = 5,     // heal and top-up (S-29, S-44)
	};

	enum class Layer : std::int32_t
	{
		kUnkeyed = 0,  // the body's own layer (keyword None)
		kRefit = 1,    // Silhouette's refit keyword (Silhouette.esp 0x803)
	};

	struct Write
	{
		std::string morph;
		float       value{ 0.0F };
		Layer       layer{ Layer::kUnkeyed };
	};

	// One job for the bridge. It does, in this order: regenerate, probe (names, markers), readAll, the
	// reads, Prepare, the clears, the writes, update; then reports Done. Every value it writes was
	// decided here.
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

		std::string              marker;  // reported by the probe: the body marker
		float                    markerValue{ 0.0F };
		float                    refitValue{ 0.0F };  // the refit marker's value, 0 for none
		std::vector<std::string> names;
		std::vector<float>       readValues;  // parallel to reads; NaN until reported
		Morphs                   layer;       // reported by readAll

		bool               readsDecided{ false };
		bool               prepared{ false };
		bool               clearUnkeyed{ false };
		bool               clearRefit{ false };
		std::vector<Write> writes;
		bool               update{ false };

		BodyRequest   body;
		bool          refitOn{ false };
		bool          heavy{ false };
		std::string   refitSet;
		std::uint32_t touchHash{ 0 };
	};

	struct Settings
	{
		bool            orefit{ true };  // MCM, and SetORefit (S-24)
		VarietySwitches variety;
	};

	class Director
	{
	public:
		Director();

		// --- lifecycle ---
		void SetCatalog(std::shared_ptr<const Catalog> a_catalog);
		void Refuse(std::string a_why);  // no catalog, or one that cannot be trusted: act on nothing
		[[nodiscard]] bool                           Ready() const;
		[[nodiscard]] std::string                    Status() const;
		[[nodiscard]] std::shared_ptr<const Catalog> CatalogPtr() const;

		void                   Configure(const Settings& a_settings);
		[[nodiscard]] Settings Current() const;

		// A save is being left: everything about the world goes, the records stay (the co-save's).
		void ForgetWorld();
		// The co-save is reverting (new game, or before a load): the records go too.
		void RevertRecords();

		// --- what the game saw ---
		void Seen(const Sighting& a_sighting);
		// An equip event was handled: a_sighting is the actor after it. a_removedClothing: the event took
		// off an item that dresses them (OnActorRemovingClothes).
		void Dressed(const Sighting& a_sighting, bool a_removedClothing);

		// --- requests (API, MCM, picker); each writes the intent at once (S-43) ---
		bool RequestPreset(std::uint32_t a_ref, bool a_female, std::uint32_t a_base, std::string_view a_preset, Source a_source, std::string& a_why);
		bool RequestRegenerate(std::uint32_t a_ref, bool a_female, std::uint32_t a_base, std::string& a_why);
		bool RequestReset(std::uint32_t a_ref, bool a_female, std::uint32_t a_base, std::string& a_why);
		// The body they have, again, with this build's values and their own variety: their record's
		// preset, or the one their marker names (a_markerPreset, from a probe) for a body BodyGen gave.
		bool RequestReapply(std::uint32_t a_ref, bool a_female, std::uint32_t a_base, std::string_view a_markerPreset, std::string& a_why);

		// --- the bridge ---
		[[nodiscard]] std::uint32_t        NextOrder();
		[[nodiscard]] std::optional<Order> Peek(std::uint32_t a_order) const;
		[[nodiscard]] std::uint32_t        OrderActor(std::uint32_t a_order) const;
		void                               NoteName(std::uint32_t a_order, std::string_view a_morph);
		void                               NoteMarker(std::uint32_t a_order, std::string_view a_marker, float a_value);
		// How many morphs to read before Prepare -- decided on this first call, after the probe: a body
		// without a Silhouette marker is recognised by a few of its own values.
		[[nodiscard]] std::int32_t ReadCount(std::uint32_t a_order);
		[[nodiscard]] std::string  ReadMorph(std::uint32_t a_order, std::int32_t a_index) const;
		void                       NoteRead(std::uint32_t a_order, std::int32_t a_index, float a_value);
		void                       NoteLayer(std::uint32_t a_order, std::string_view a_morph, float a_value);
		bool                       Prepare(std::uint32_t a_order);
		[[nodiscard]] bool         ClearsUnkeyed(std::uint32_t a_order) const;
		[[nodiscard]] bool         ClearsRefit(std::uint32_t a_order) const;
		[[nodiscard]] bool         Updates(std::uint32_t a_order) const;
		[[nodiscard]] std::int32_t WriteCount(std::uint32_t a_order) const;
		[[nodiscard]] std::string  WriteMorph(std::uint32_t a_order, std::int32_t a_index) const;
		[[nodiscard]] float        WriteValue(std::uint32_t a_order, std::int32_t a_index) const;
		[[nodiscard]] Layer        WriteLayer(std::uint32_t a_order, std::int32_t a_index) const;
		void                       Done(std::uint32_t a_order, bool a_ok);
		[[nodiscard]] std::size_t  Pending() const;

		// Events for the bridge to raise, oldest first. 0: none.
		[[nodiscard]] std::uint32_t        NextEvent();
		[[nodiscard]] std::optional<Event> EventAt(std::uint32_t a_event) const;

		// --- the NPC picker (S-22, S-47) ---
		std::string                 PickerStart(std::uint32_t a_ref, bool a_female, std::uint32_t a_base, std::string_view a_name);
		std::string                 PickerStep(std::int32_t a_step);
		std::string                 PickerKeep();
		std::string                 PickerCancel();
		[[nodiscard]] std::uint32_t PickerTarget() const;
		[[nodiscard]] bool          PickerReady() const;  // the snapshot is in: Next can start

		// --- queries ---
		[[nodiscard]] std::string AssignedPreset(std::uint32_t a_ref) const;  // the intent
		[[nodiscard]] bool        RefitApplied(std::uint32_t a_ref) const;
		[[nodiscard]] std::string Describe(std::uint32_t a_ref) const;

		// --- the co-save (S-25, S-47) ---
		[[nodiscard]] std::vector<std::byte> SaveRecords(const std::function<bool(std::uint32_t)>& a_keep) const;
		bool                                 LoadRecords(std::span<const std::byte> a_bytes, std::uint32_t a_version,
											 const std::function<std::uint32_t(std::uint32_t)>& a_resolve, std::string& a_error);
		[[nodiscard]] std::size_t            RecordCount() const;
		[[nodiscard]] std::optional<Record>  RecordOf(std::uint32_t a_ref) const;

		// Lines for the log, taken by the game side (the director never logs itself: no game here).
		[[nodiscard]] std::vector<std::string> TakeLog();

	private:
		enum Lane : int
		{
			kUrgent = 0,      // the player's own actions, and a refit coming off
			kNormal = 1,      // decisions: rules, refits, touch-ups
			kBackground = 2,  // probes
		};

		struct Work
		{
			int                        lane{ kBackground };
			bool                       snapshot{ false };
			std::optional<BodyRequest> body;
			bool                       touch{ false };
			bool                       refit{ false };
			bool                       probe{ false };

			[[nodiscard]] bool Empty() const { return !snapshot && !body && !touch && !refit && !probe; }
		};

		struct Session
		{
			bool          known{ false };  // seen this session, with facts
			bool          eligible{ false };
			bool          blacklisted{ false };
			bool          female{ false };
			std::uint32_t base{ 0 };
			bool          clothed{ false };
			bool          heavy{ false };
			std::string   outfitSet;
			ActorFacts    facts;

			// What this session knows of LooksMenu's layers (S-43).
			bool                     probed{ false };
			std::string              marker;  // the body marker, "" for none
			std::uint32_t            stamp{ 0 };
			bool                     hasBody{ false };
			int                      refit{ -1 };  // -1 unknown, 0 none, else the refit marker's value
			std::vector<std::string> names;
			bool                     reset{ false };      // reset this session: bare, never refit (S-41)
			bool                     regiven{ false };    // intent was restored once this session
			bool                     restoring{ false };  // a picker restore after a load is queued
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
			std::string              current;  // the preset they had at Pick, "" unknown
		};

		struct Want
		{
			const RefitSet* set{ nullptr };
			bool            heavy{ false };
		};

		// all of these expect the lock held
		Verdict                   Admit(Session& a_session, const Sighting& a_sighting);
		void                      LeaveAlone(std::uint32_t a_ref, const Session& a_session);
		[[nodiscard]] Order*      Find(std::uint32_t a_order);
		void                      Log(std::string a_line);
		void                      Push(EventKind a_kind, std::uint32_t a_ref, std::string a_preset = {}, bool a_flag = false, std::uint32_t a_announce = 0);
		Work&                     WorkFor(std::uint32_t a_ref, int a_lane);
		void                      QueueBody(std::uint32_t a_ref, BodyRequest a_body, int a_lane);
		[[nodiscard]] bool        BodyPending(std::uint32_t a_ref) const;
		void                      Intend(std::uint32_t a_ref, const Session& a_session, Source a_source, std::string a_preset);
		void                      DecideBody(std::uint32_t a_ref, Session& a_session, const Verdict& a_verdict);
		void                      OnProbed(std::uint32_t a_ref, const Order& a_order);
		void                      Reconcile(std::uint32_t a_ref, Session& a_session);
		void                      AnnounceBody(std::uint32_t a_ref, const Session& a_session);
		void                      CheckTouch(std::uint32_t a_ref, const Session& a_session);
		[[nodiscard]] Want        WantRefit(const Session& a_session) const;
		[[nodiscard]] float       RefitMarkerValue(const RefitSet& a_set, bool a_heavy) const;
		void                      ReconcileRefit(std::uint32_t a_ref);
		[[nodiscard]] std::string PresetNamedBy(std::string_view a_marker, std::uint32_t a_stamp) const;
		void                      FinishBody(Order& a_order);
		void                      FinishRefit(Order& a_order);
		void                      ClosePicker();
		std::string               CancelPicking();

		mutable std::mutex _lock;

		std::shared_ptr<const Catalog> _catalog;
		std::string                    _status{ "starting" };
		Settings                       _settings;

		Registry                                   _registry;
		std::unordered_map<std::uint32_t, Session> _sessions;
		std::unordered_map<std::uint32_t, Work>    _work;
		std::deque<std::uint32_t>                  _queue;  // references with work, in turn within a lane
		std::unordered_map<std::uint32_t, Order>   _inflight;
		std::unordered_set<std::uint32_t>          _busy;  // references with an order in flight
		std::deque<Event>                          _events;
		std::deque<Event>                          _taken;  // the last few handed out, for their details
		bool                                       _eventsDropped{ false };
		std::uint32_t                              _nextOrder{ 1 };
		std::uint32_t                              _nextEvent{ 1 };
		Picker                                     _picker;
		std::vector<std::string>                   _log;
	};
}

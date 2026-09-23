#include "Papyrus.h"

#include "Game.h"
#include "Sinks.h"

namespace SH::Papyrus
{
	namespace
	{
		// "Native" is a reserved word in Papyrus, so the script cannot be called that (S-46).
		constexpr auto kScript = "Silhouette:DLL"sv;

		// What an order asks of the bridge, and in which order. The bridge checks this at every load and
		// refuses to run orders it would carry out differently: a DLL and scripts of different builds.
		constexpr std::int32_t kProtocol = 2;

		using Str = RE::BSFixedString;

		std::mutex  g_errorLock;
		std::string g_lastError;

		void SetError(std::string a_why)
		{
			std::scoped_lock l{ g_errorLock };
			g_lastError = std::move(a_why);
		}

		Director& D() { return Game::TheDirector(); }

		std::uint32_t Ref(std::int32_t a_id) { return static_cast<std::uint32_t>(a_id); }
		std::uint32_t Id(std::int32_t a_order) { return static_cast<std::uint32_t>(a_order); }

		// ---- lifecycle (data only) ----

		bool IsReady(std::monostate) { return D().Ready(); }

		Str Status(std::monostate)
		{
			return Str{ std::format("{} | events: {} | {} order(s) waiting, {} record(s)", D().Status(), Sinks::Status(), D().Pending(), D().RecordCount()) };
		}

		Str Version(std::monostate) { return Str{ SH_VERSION_STRING }; }

		std::int32_t ProtocolVersion(std::monostate) { return kProtocol; }

		std::int32_t Stamp(std::monostate)
		{
			const auto c = D().CatalogPtr();
			return c ? static_cast<std::int32_t>(c->stamp) : 0;
		}

		Str Build(std::monostate)
		{
			const auto c = D().CatalogPtr();
			return Str{ c ? c->build : std::string{} };
		}

		void Configure(std::monostate, bool a_orefit, bool a_nipples, bool a_genitals)
		{
			D().Configure(Settings{ .orefit = a_orefit, .variety = { .nipples = a_nipples, .genitals = a_genitals } });
		}

		std::int32_t Pending(std::monostate) { return static_cast<std::int32_t>(D().Pending()); }

		void Log(std::monostate, Str a_line) { logger::info("bridge: {}", a_line.c_str()); }

		// ---- orders (data only) ----

		std::int32_t NextOrder(std::monostate) { return static_cast<std::int32_t>(D().NextOrder()); }

		std::int32_t OrderActor(std::monostate, std::int32_t a_order) { return static_cast<std::int32_t>(D().OrderActor(Id(a_order))); }

		std::int32_t OrderKind(std::monostate, std::int32_t a_order)
		{
			const auto o = D().Peek(Id(a_order));
			return o ? static_cast<std::int32_t>(o->kind) : 0;
		}

		bool OrderFemale(std::monostate, std::int32_t a_order)
		{
			const auto o = D().Peek(Id(a_order));
			return o && o->female;
		}

		bool OrderRegenerates(std::monostate, std::int32_t a_order)
		{
			const auto o = D().Peek(Id(a_order));
			return o && o->regenerate;
		}

		bool OrderProbes(std::monostate, std::int32_t a_order)
		{
			const auto o = D().Peek(Id(a_order));
			return o && o->probe;
		}

		bool OrderReadsAll(std::monostate, std::int32_t a_order)
		{
			const auto o = D().Peek(Id(a_order));
			return o && o->readAll;
		}

		void NoteName(std::monostate, std::int32_t a_order, Str a_morph) { D().NoteName(Id(a_order), a_morph.c_str()); }

		// 0 an ordinary morph, 1 a body marker (read unkeyed), 2 the refit marker (read under the keyword).
		std::int32_t MarkerKind(std::monostate, Str a_morph) { return static_cast<std::int32_t>(KindOf(a_morph.c_str())); }

		void NoteMarker(std::monostate, std::int32_t a_order, Str a_marker, float a_value)
		{
			D().NoteMarker(Id(a_order), a_marker.c_str(), a_value);
		}

		std::int32_t OrderReadCount(std::monostate, std::int32_t a_order) { return D().ReadCount(Id(a_order)); }

		Str OrderReadMorph(std::monostate, std::int32_t a_order, std::int32_t a_index) { return Str{ D().ReadMorph(Id(a_order), a_index) }; }

		void NoteRead(std::monostate, std::int32_t a_order, std::int32_t a_index, float a_value) { D().NoteRead(Id(a_order), a_index, a_value); }

		void NoteLayer(std::monostate, std::int32_t a_order, Str a_morph, float a_value) { D().NoteLayer(Id(a_order), a_morph.c_str(), a_value); }

		bool Prepare(std::monostate, std::int32_t a_order) { return D().Prepare(Id(a_order)); }

		bool OrderClearsUnkeyed(std::monostate, std::int32_t a_order) { return D().ClearsUnkeyed(Id(a_order)); }

		bool OrderClearsRefit(std::monostate, std::int32_t a_order) { return D().ClearsRefit(Id(a_order)); }

		std::int32_t OrderWriteCount(std::monostate, std::int32_t a_order) { return D().WriteCount(Id(a_order)); }

		Str OrderWriteMorph(std::monostate, std::int32_t a_order, std::int32_t a_index) { return Str{ D().WriteMorph(Id(a_order), a_index) }; }

		float OrderWriteValue(std::monostate, std::int32_t a_order, std::int32_t a_index) { return D().WriteValue(Id(a_order), a_index); }

		// 0 the unkeyed layer (keyword None), 1 Silhouette's refit keyword.
		std::int32_t OrderWriteLayer(std::monostate, std::int32_t a_order, std::int32_t a_index)
		{
			return static_cast<std::int32_t>(D().WriteLayer(Id(a_order), a_index));
		}

		bool OrderUpdates(std::monostate, std::int32_t a_order) { return D().Updates(Id(a_order)); }

		void OrderDone(std::monostate, std::int32_t a_order, bool a_ok) { D().Done(Id(a_order), a_ok); }

		// ---- events (data only) ----

		std::int32_t NextEvent(std::monostate) { return static_cast<std::int32_t>(D().NextEvent()); }

		std::int32_t EventKind(std::monostate, std::int32_t a_event)
		{
			const auto e = D().EventAt(Id(a_event));
			return e ? static_cast<std::int32_t>(e->kind) : 0;
		}

		std::int32_t EventActor(std::monostate, std::int32_t a_event)
		{
			const auto e = D().EventAt(Id(a_event));
			return e ? static_cast<std::int32_t>(e->ref) : 0;
		}

		Str EventPreset(std::monostate, std::int32_t a_event)
		{
			const auto e = D().EventAt(Id(a_event));
			return Str{ e ? e->preset : std::string{} };
		}

		bool EventFlag(std::monostate, std::int32_t a_event)
		{
			const auto e = D().EventAt(Id(a_event));
			return e && e->flag;
		}

		// ---- the picker ----

		Str          PickerStep(std::monostate, std::int32_t a_step) { return Str{ D().PickerStep(a_step) }; }
		Str          PickerKeep(std::monostate) { return Str{ D().PickerKeep() }; }
		Str          PickerCancel(std::monostate) { return Str{ D().PickerCancel() }; }
		std::int32_t PickerTarget(std::monostate) { return static_cast<std::int32_t>(D().PickerTarget()); }
		bool         PickerReady(std::monostate) { return D().PickerReady(); }

		// ---- queries (data only) ----

		Str AssignedPreset(std::monostate, std::int32_t a_actor) { return Str{ D().AssignedPreset(Ref(a_actor)) }; }

		Str PresetForMarker(std::monostate, Str a_marker, float a_value)
		{
			const auto c = D().CatalogPtr();
			if (!c || !(a_value > 0.0F) || a_value >= 16777216.0F) {
				return Str{};
			}
			return Str{ c->PresetForMarker(a_marker.c_str(), static_cast<std::uint32_t>(std::lround(a_value))).value_or(std::string{}) };
		}

		std::int32_t PresetCount(std::monostate, bool a_female)
		{
			const auto c = D().CatalogPtr();
			return c ? static_cast<std::int32_t>(c->MenuPresets(a_female).size()) : 0;
		}

		Str PresetName(std::monostate, bool a_female, std::int32_t a_index)
		{
			const auto c = D().CatalogPtr();
			if (!c) {
				return Str{};
			}
			const auto list = c->MenuPresets(a_female);
			return a_index >= 0 && static_cast<std::size_t>(a_index) < list.size() ? Str{ list[static_cast<std::size_t>(a_index)]->name } : Str{};
		}

		bool IsORefitEnabled(std::monostate)
		{
			const auto c = D().CatalogPtr();
			return c && !c->refitSets.empty() && D().Current().orefit;
		}

		bool IsORefitApplied(std::monostate, std::int32_t a_actor) { return D().RefitApplied(Ref(a_actor)); }

		void SetORefit(std::monostate, bool a_on)
		{
			auto s = D().Current();
			s.orefit = a_on;
			D().Configure(s);
		}

		void SetNippleRand(std::monostate, bool a_on)
		{
			auto s = D().Current();
			s.variety.nipples = a_on;
			D().Configure(s);
		}

		void SetGenitalRand(std::monostate, bool a_on)
		{
			auto s = D().Current();
			s.variety.genitals = a_on;
			D().Configure(s);
		}

		Str Describe(std::monostate, std::int32_t a_actor) { return Str{ D().Describe(Ref(a_actor)) }; }

		Str LastError(std::monostate)
		{
			std::scoped_lock l{ g_errorLock };
			return Str{ g_lastError };
		}

		// ---- main thread: these read the game ----

		void Pump(std::monostate)
		{
			Sinks::Attach();  // the crosshair's source appears with the HUD; cheap once attached
			Game::Pump();
		}

		std::int32_t CrosshairActor(std::monostate, float a_recentSeconds) { return static_cast<std::int32_t>(Game::CrosshairActor(a_recentSeconds)); }

		// An NPC Silhouette shapes: not the player, not a character-creation dummy (S-13), a distributed race.
		RE::Actor* Shapeable(std::int32_t a_actor, std::string& a_why)
		{
			auto* actor = Game::ActorFor(Ref(a_actor));
			if (!actor || Game::NeverShaped(actor) || !actor->GetNPC()) {
				a_why = "that is not an NPC Silhouette can shape";
				return nullptr;
			}
			const auto c = D().CatalogPtr();
			if (!c) {
				a_why = D().Status();
				return nullptr;
			}
			const char* race = actor->race ? actor->race->GetFormEditorID() : nullptr;
			if (!race || std::ranges::none_of(c->races, [&](const std::string& r) { return IEquals(r, race); })) {
				a_why = std::format("{} is of a race Silhouette does not shape ({})", Game::NameOf(actor), race ? race : "?");
				return nullptr;
			}
			return actor;
		}

		bool CanShape(std::monostate, std::int32_t a_actor)
		{
			std::string why;
			return Shapeable(a_actor, why) != nullptr;
		}

		Str PickerStart(std::monostate, std::int32_t a_actor)
		{
			std::string why;
			auto*       actor = Shapeable(a_actor, why);
			if (!actor) {
				return Str{ why };
			}
			return Str{ D().PickerStart(Ref(a_actor), Game::IsFemale(actor), Game::BaseOf(actor), Game::NameOf(actor)) };
		}

		// Each request clears LastError on entry and sets it on every way it can say no.
		template <class F>
		bool Request(std::int32_t a_actor, F&& a_do)
		{
			SetError({});
			std::string why;
			auto*       actor = Shapeable(a_actor, why);
			if (!actor || !a_do(actor, why)) {
				SetError(why.empty() ? std::string{ "refused" } : why);
				return false;
			}
			return true;
		}

		bool RequestPreset(std::monostate, std::int32_t a_actor, Str a_preset, std::int32_t a_source)
		{
			const auto source = a_source == static_cast<std::int32_t>(Source::kPicker) ? Source::kPicker : Source::kAPI;
			return Request(a_actor, [&](RE::Actor* a, std::string& why) {
				return D().RequestPreset(Ref(a_actor), Game::IsFemale(a), Game::BaseOf(a), a_preset.c_str(), source, why);
			});
		}

		bool RequestRegenerate(std::monostate, std::int32_t a_actor)
		{
			return Request(a_actor, [&](RE::Actor* a, std::string& why) {
				return D().RequestRegenerate(Ref(a_actor), Game::IsFemale(a), Game::BaseOf(a), why);
			});
		}

		bool RequestReset(std::monostate, std::int32_t a_actor)
		{
			return Request(a_actor, [&](RE::Actor* a, std::string& why) {
				return D().RequestReset(Ref(a_actor), Game::IsFemale(a), Game::BaseOf(a), why);
			});
		}

		bool RequestReapply(std::monostate, std::int32_t a_actor, Str a_markerPreset)
		{
			return Request(a_actor, [&](RE::Actor* a, std::string& why) {
				return D().RequestReapply(Ref(a_actor), Game::IsFemale(a), Game::BaseOf(a), a_markerPreset.c_str(), why);
			});
		}

		Str NameOf(std::monostate, std::int32_t a_actor) { return Str{ Game::NameOf(Game::ActorFor(Ref(a_actor))) }; }

		// Binds a_fn. a_fast: callable from tasklets, so a call costs no frame -- set on our own
		// function object before binding rather than through the VM's SetCallableFromTasklets, a
		// virtual this plugin has never been seen to call on this runtime. Only functions that touch
		// nothing but the director's state (its own lock) may be fast; anything that reads the game
		// stays on the main thread.
		template <class F>
		void Bind(RE::BSScript::IVirtualMachine* a_vm, std::string_view a_name, F a_fn, bool a_fast)
		{
			auto* fn = new RE::BSScript::NativeFunction(kScript, a_name, a_fn, false);
			fn->isCallableFromTasklet = a_fast;
			if (!a_vm->BindNativeMethod(fn)) {
				logger::error("papyrus: could not bind {}.{}", kScript, a_name);
			}
		}
	}

	bool Register(RE::BSScript::IVirtualMachine* a_vm)
	{
		if (!a_vm) {
			return false;
		}
		constexpr bool fast = true;
		constexpr bool main = false;

		Bind(a_vm, "IsReady"sv, IsReady, fast);
		Bind(a_vm, "Status"sv, Status, fast);
		Bind(a_vm, "Version"sv, Version, fast);
		Bind(a_vm, "ProtocolVersion"sv, ProtocolVersion, fast);
		Bind(a_vm, "Stamp"sv, Stamp, fast);
		Bind(a_vm, "Build"sv, Build, fast);
		Bind(a_vm, "Configure"sv, Configure, fast);
		Bind(a_vm, "Pending"sv, Pending, fast);
		Bind(a_vm, "Log"sv, Log, fast);

		Bind(a_vm, "NextOrder"sv, NextOrder, fast);
		Bind(a_vm, "OrderActor"sv, OrderActor, fast);
		Bind(a_vm, "OrderKind"sv, OrderKind, fast);
		Bind(a_vm, "OrderFemale"sv, OrderFemale, fast);
		Bind(a_vm, "OrderRegenerates"sv, OrderRegenerates, fast);
		Bind(a_vm, "OrderProbes"sv, OrderProbes, fast);
		Bind(a_vm, "OrderReadsAll"sv, OrderReadsAll, fast);
		Bind(a_vm, "NoteName"sv, NoteName, fast);
		Bind(a_vm, "MarkerKind"sv, MarkerKind, fast);
		Bind(a_vm, "NoteMarker"sv, NoteMarker, fast);
		Bind(a_vm, "OrderReadCount"sv, OrderReadCount, fast);
		Bind(a_vm, "OrderReadMorph"sv, OrderReadMorph, fast);
		Bind(a_vm, "NoteRead"sv, NoteRead, fast);
		Bind(a_vm, "NoteLayer"sv, NoteLayer, fast);
		Bind(a_vm, "Prepare"sv, Prepare, fast);
		Bind(a_vm, "OrderClearsUnkeyed"sv, OrderClearsUnkeyed, fast);
		Bind(a_vm, "OrderClearsRefit"sv, OrderClearsRefit, fast);
		Bind(a_vm, "OrderWriteCount"sv, OrderWriteCount, fast);
		Bind(a_vm, "OrderWriteMorph"sv, OrderWriteMorph, fast);
		Bind(a_vm, "OrderWriteValue"sv, OrderWriteValue, fast);
		Bind(a_vm, "OrderWriteLayer"sv, OrderWriteLayer, fast);
		Bind(a_vm, "OrderUpdates"sv, OrderUpdates, fast);
		Bind(a_vm, "OrderDone"sv, OrderDone, fast);

		Bind(a_vm, "NextEvent"sv, NextEvent, fast);
		Bind(a_vm, "EventKind"sv, EventKind, fast);
		Bind(a_vm, "EventActor"sv, EventActor, fast);
		Bind(a_vm, "EventPreset"sv, EventPreset, fast);
		Bind(a_vm, "EventFlag"sv, EventFlag, fast);

		Bind(a_vm, "PickerStep"sv, PickerStep, fast);
		Bind(a_vm, "PickerKeep"sv, PickerKeep, fast);
		Bind(a_vm, "PickerCancel"sv, PickerCancel, fast);
		Bind(a_vm, "PickerTarget"sv, PickerTarget, fast);
		Bind(a_vm, "PickerReady"sv, PickerReady, fast);

		Bind(a_vm, "AssignedPreset"sv, AssignedPreset, fast);
		Bind(a_vm, "PresetForMarker"sv, PresetForMarker, fast);
		Bind(a_vm, "PresetCount"sv, PresetCount, fast);
		Bind(a_vm, "PresetName"sv, PresetName, fast);
		Bind(a_vm, "IsORefitEnabled"sv, IsORefitEnabled, fast);
		Bind(a_vm, "IsORefitApplied"sv, IsORefitApplied, fast);
		Bind(a_vm, "SetORefit"sv, SetORefit, fast);
		Bind(a_vm, "SetNippleRand"sv, SetNippleRand, fast);
		Bind(a_vm, "SetGenitalRand"sv, SetGenitalRand, fast);
		Bind(a_vm, "Describe"sv, Describe, fast);
		Bind(a_vm, "LastError"sv, LastError, fast);

		Bind(a_vm, "Pump"sv, Pump, main);
		Bind(a_vm, "CrosshairActor"sv, CrosshairActor, main);
		Bind(a_vm, "CanShape"sv, CanShape, main);
		Bind(a_vm, "PickerStart"sv, PickerStart, main);
		Bind(a_vm, "RequestPreset"sv, RequestPreset, main);
		Bind(a_vm, "RequestRegenerate"sv, RequestRegenerate, main);
		Bind(a_vm, "RequestReset"sv, RequestReset, main);
		Bind(a_vm, "RequestReapply"sv, RequestReapply, main);
		Bind(a_vm, "NameOf"sv, NameOf, main);

		logger::info("papyrus: {} bound (protocol {})", kScript, kProtocol);
		return true;
	}
}

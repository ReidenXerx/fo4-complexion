#include "Sinks.h"

#include "EventSources.h"
#include "Game.h"

namespace SH::Sinks
{
	namespace
	{
		template <class E>
		struct Tap : RE::BSTEventSink<E>
		{
			explicit Tap(void (*a_on)(const E&)) :
				on(a_on) {}

			RE::BSEventNotifyControl ProcessEvent(const E& a_event, RE::BSTEventSource<E>*) override
			{
				on(a_event);
				return RE::BSEventNotifyControl::kContinue;
			}

			void (*on)(const E&);
		};

		bool IsActor(const RE::TESForm* a_form)
		{
			return a_form && a_form->Is(RE::ENUM_FORM_ID::kACHR);
		}

		void OnLoaded(const RE::TESObjectLoadedEvent& a_event)
		{
			if (a_event.loaded && IsActor(RE::TESForm::GetFormByID(a_event.formID))) {
				Game::NoteLoaded(a_event.formID);
			}
		}

		void OnEquip(const RE::TESEquipEvent& a_event)
		{
			const auto* ref = a_event.actor.get();
			if (IsActor(ref)) {
				Game::NoteEquip(ref->GetFormID(), a_event.baseObject, a_event.equipped);
			}
		}

		void OnPick(const Events::PickRefStateChangedEvent& a_event)
		{
			const auto* ref = a_event.ref.get();
			Game::NoteCrosshair(ref ? ref->GetFormID() : 0);
		}

		Tap<RE::TESObjectLoadedEvent>         g_loaded{ OnLoaded };
		Tap<RE::TESEquipEvent>                g_equip{ OnEquip };
		Tap<Events::PickRefStateChangedEvent> g_pick{ OnPick };

		std::atomic<bool> g_loadedOn{ false };
		std::atomic<bool> g_equipOn{ false };
		std::atomic<bool> g_pickOn{ false };

		// Both getters fault on 1.10.163 (F4MCP's log on this machine, every launch: "the header's
		// source getter faulted on this runtime"), so the holder is scanned straight away.
		template <class E>
		void AttachHolder(std::string_view a_type, Tap<E>& a_tap, std::atomic<bool>& a_on)
		{
			if (a_on.load()) {
				return;
			}
			const auto found = Events::FindHolderSource(a_type);
			if (!found) {
				logger::warn("events: no source for {} yet", a_type);
				return;
			}
			reinterpret_cast<RE::BSTEventSource<E>*>(found)->RegisterSink(&a_tap);
			a_on.store(true);
			logger::info("events: {} attached (holder scan, {:X})", a_type, found);
		}
	}

	void Attach()
	{
		AttachHolder<RE::TESObjectLoadedEvent>("TESObjectLoadedEvent"sv, g_loaded, g_loadedOn);
		AttachHolder<RE::TESEquipEvent>("TESEquipEvent"sv, g_equip, g_equipOn);
		if (!g_pickOn.load()) {
			if (const auto found = Events::FindGlobalSource("PickRefStateChangedEvent"sv)) {
				RE::BSTEventSource<Events::PickRefStateChangedEvent>* source =
					reinterpret_cast<RE::BSTGlobalEvent::EventSource<Events::PickRefStateChangedEvent>*>(found);
				source->RegisterSink(&g_pick);
				g_pickOn.store(true);
				logger::info("events: crosshair attached (global source, {:X})", found);
			}
		}
	}

	std::string Status()
	{
		const auto yes = [](const std::atomic<bool>& a_on) { return a_on.load() ? "yes"sv : "no"sv; };
		return std::format("loaded: {}, equip: {}, crosshair: {}", yes(g_loadedOn), yes(g_equipOn), yes(g_pickOn));
	}
}

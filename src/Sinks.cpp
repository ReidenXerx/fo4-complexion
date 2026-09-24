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

		// A sink only READS, and only through the guarded reads: plain fields, and ids and types of objects
		// whose RTTI checked out. Forms are looked up and read on the main thread, in the pump.
		bool Is(const void* a_form, RE::ENUM_FORM_ID a_type)
		{
			return Events::SafeFormType(a_form) == static_cast<std::uint8_t>(a_type);
		}

		void OnLoaded(const RE::TESObjectLoadedEvent& a_event)
		{
			if (a_event.loaded && Is(RE::TESForm::GetFormByID(a_event.formID), RE::ENUM_FORM_ID::kACHR)) {
				Game::NoteLoaded(a_event.formID);
			}
		}

		void OnEquip(const RE::TESEquipEvent& a_event)
		{
			// Only clothing changes what someone wears: weapons, ammunition and aid are never queued.
			const auto* ref = a_event.actor.get();
			if (Is(ref, RE::ENUM_FORM_ID::kACHR) && Is(RE::TESForm::GetFormByID(a_event.baseObject), RE::ENUM_FORM_ID::kARMO)) {
				if (const auto id = Events::SafeFormID(ref)) {
					Game::NoteEquip(id, a_event.baseObject, a_event.equipped);
				}
			}
		}

		// Two handles copied, nothing looked up: the main thread does that when someone asks.
		void OnViewCaster(const Events::ViewCasterUpdateEvent& a_event)
		{
			if (a_event.active) {
				Game::NoteCrosshair(a_event.activatePickRef, a_event.dialoguePickRef);
			} else {
				Game::NoteCrosshair(0, 0);
			}
		}

		Tap<RE::TESObjectLoadedEvent>      g_loaded{ OnLoaded };
		Tap<RE::TESEquipEvent>             g_equip{ OnEquip };
		Tap<Events::ViewCasterUpdateEvent> g_pick{ OnViewCaster };

		std::atomic<bool> g_loadedOn{ false };
		std::atomic<bool> g_equipOn{ false };
		std::atomic<bool> g_pickOn{ false };
		std::atomic<bool> g_loadedWarned{ false };
		std::atomic<bool> g_equipWarned{ false };

		// Both getters fault on 1.10.163 (F4MCP's log on this machine, every launch: "the header's
		// source getter faulted on this runtime"), so the holder is scanned straight away. Every poll
		// tries again while a source is missing; the log says so once.
		template <class E>
		void AttachHolder(std::string_view a_type, Tap<E>& a_tap, std::atomic<bool>& a_on, std::atomic<bool>& a_warned, std::string_view a_without)
		{
			if (a_on.load()) {
				return;
			}
			const auto found = Events::FindHolderSource(a_type);
			if (!found) {
				if (!a_warned.exchange(true)) {
					logger::warn("events: no source for {} yet - {} until it is found (tried again every poll)", a_type, a_without);
				}
				return;
			}
			reinterpret_cast<RE::BSTEventSource<E>*>(found)->RegisterSink(&a_tap);
			a_on.store(true);
			logger::info("events: {} attached (holder scan, {:X})", a_type, found);
		}
	}

	void Attach()
	{
		AttachHolder<RE::TESObjectLoadedEvent>("TESObjectLoadedEvent"sv, g_loaded, g_loadedOn, g_loadedWarned,
			"nobody is seen loading, so the rules, the touch-up and ORefit act only on who the picker or the API names"sv);
		AttachHolder<RE::TESEquipEvent>("TESEquipEvent"sv, g_equip, g_equipOn, g_equipWarned,
			"dressing and undressing go unseen, so ORefit follows only what is read when someone loads"sv);
		if (!g_pickOn.load()) {
			if (const auto found = Events::FindGlobalSource("ViewCasterUpdateEvent"sv)) {
				RE::BSTEventSource<Events::ViewCasterUpdateEvent>* source =
					reinterpret_cast<RE::BSTGlobalEvent::EventSource<Events::ViewCasterUpdateEvent>*>(found);
				source->RegisterSink(&g_pick);
				g_pickOn.store(true);
				logger::info("events: crosshair attached (the view caster's global source, {:X})", found);
			}
		}
	}

	std::string Status()
	{
		const auto yes = [](const std::atomic<bool>& a_on) { return a_on.load() ? "yes"sv : "no"sv; };
		return std::format("loaded: {}, equip: {}, crosshair: {}", yes(g_loadedOn), yes(g_equipOn), yes(g_pickOn));
	}
}

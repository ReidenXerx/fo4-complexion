#include "Sinks.h"

#include "EventSources.h"
#include "Game.h"

namespace CX::Sinks
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

		// A sink only READS, and only through the guarded reads; forms are looked up on the main thread, in the pump.
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

		Tap<RE::TESObjectLoadedEvent> g_loaded{ OnLoaded };
		std::atomic<bool>             g_loadedOn{ false };
		std::atomic<bool>             g_loadedWarned{ false };
	}

	void Attach()
	{
		// The header's getter faults on 1.10.163 (Silhouette, from F4MCP's log): the holder is scanned instead.
		if (g_loadedOn.load()) {
			return;
		}
		const auto found = Events::FindHolderSource("TESObjectLoadedEvent"sv);
		if (!found) {
			if (!g_loadedWarned.exchange(true)) {
				logger::warn("events: no source for TESObjectLoadedEvent yet - nobody is seen loading until it is found (tried again every poll)");
			}
			return;
		}
		reinterpret_cast<RE::BSTEventSource<RE::TESObjectLoadedEvent>*>(found)->RegisterSink(&g_loaded);
		g_loadedOn.store(true);
		logger::info("events: TESObjectLoadedEvent attached (holder scan, {:X})", found);
	}

	std::string Status()
	{
		return std::format("loaded: {}", g_loadedOn.load() ? "yes" : "no");
	}
}

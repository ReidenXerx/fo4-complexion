#include "Papyrus.h"

#include "Game.h"
#include "Sinks.h"

namespace CX::Papyrus
{
	namespace
	{
		constexpr auto kScript = "Complexion:DLL"sv;

		// 1: the first bridge (orders of whole looks, Done/Gone, Configure, ResetAll, Unapply, Warning).
		constexpr std::int32_t kProtocol = 1;

		using Str = RE::BSFixedString;

		Director& D() { return Game::TheDirector(); }

		std::uint32_t Id(std::int32_t a_id) { return static_cast<std::uint32_t>(a_id); }

		// ---- lifecycle (data only) ----

		std::int32_t ProtocolVersion(std::monostate)
		{
			Game::NoteAsked();
			return kProtocol;
		}

		Str Version(std::monostate) { return Str{ CX_VERSION_STRING }; }

		Str Status(std::monostate)
		{
			return Str{ std::format("{} record(s), {} waiting | events: {}", D().RecordCount(), D().PendingCount(), Sinks::Status()) };
		}

		std::int32_t Pending(std::monostate) { return static_cast<std::int32_t>(D().PendingCount()); }

		void Configure(std::monostate, bool a_enabled, bool a_adult)
		{
			D().SetEnabled(a_enabled);
			D().SetAdult(a_adult);
		}

		Str Warning(std::monostate) { return Str{ Game::TakeWarning() }; }

		// MCM "Roll everyone again".
		void ResetAll(std::monostate)
		{
			D().ResetAll();
			Game::ArmSweep();  // the people around are read again at the next polls, so they change at once
		}

		// MCM "Clear every overlay": the bridge called LooksMenu's ClearAll; every look is put back as people are seen.
		void Unapply(std::monostate)
		{
			D().Unapply();
			Game::ArmSweep();
		}

		// ---- the pump (main thread: it reads actors) ----

		void Pump(std::monostate) { Game::Pump(); }

		// ---- orders (data only) ----

		std::int32_t NextOrder(std::monostate) { return static_cast<std::int32_t>(D().NextOrder()); }

		std::int32_t OrderActor(std::monostate, std::int32_t a_id)
		{
			const auto o = D().GetOrder(Id(a_id));
			return o ? static_cast<std::int32_t>(o->ref) : 0;
		}

		bool OrderFemale(std::monostate, std::int32_t a_id)
		{
			const auto o = D().GetOrder(Id(a_id));
			return o && o->female;
		}

		std::int32_t OrderCount(std::monostate, std::int32_t a_id)
		{
			const auto o = D().GetOrder(Id(a_id));
			return o ? static_cast<std::int32_t>(o->picks.size()) : 0;
		}

		Str OrderTemplate(std::monostate, std::int32_t a_id, std::int32_t a_index)
		{
			const auto o = D().GetOrder(Id(a_id));
			if (!o || a_index < 0 || static_cast<std::size_t>(a_index) >= o->picks.size()) {
				return Str{};
			}
			return Str{ o->picks[static_cast<std::size_t>(a_index)].id };
		}

		std::int32_t OrderPriority(std::monostate, std::int32_t a_id, std::int32_t a_index)
		{
			const auto o = D().GetOrder(Id(a_id));
			if (!o || a_index < 0 || static_cast<std::size_t>(a_index) >= o->picks.size()) {
				return 0;
			}
			return o->picks[static_cast<std::size_t>(a_index)].priority;
		}

		void OrderDone(std::monostate, std::int32_t a_id, bool a_landed) { D().Done(Id(a_id), a_landed); }

		void OrderGone(std::monostate, std::int32_t a_id) { D().Gone(Id(a_id)); }

		// Only functions that touch nothing but the director's state (its own lock) may be fast; anything that
		// reads the game stays on the main thread. Set on the function object, as Silhouette does.
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

		Bind(a_vm, "ProtocolVersion"sv, ProtocolVersion, fast);
		Bind(a_vm, "Version"sv, Version, fast);
		Bind(a_vm, "Status"sv, Status, fast);
		Bind(a_vm, "Pending"sv, Pending, fast);
		Bind(a_vm, "Configure"sv, Configure, fast);
		Bind(a_vm, "Warning"sv, Warning, fast);
		Bind(a_vm, "ResetAll"sv, ResetAll, main);  // arms the sweep: main-thread state
		Bind(a_vm, "Unapply"sv, Unapply, main);
		Bind(a_vm, "Pump"sv, Pump, main);
		Bind(a_vm, "NextOrder"sv, NextOrder, fast);
		Bind(a_vm, "OrderActor"sv, OrderActor, fast);
		Bind(a_vm, "OrderFemale"sv, OrderFemale, fast);
		Bind(a_vm, "OrderCount"sv, OrderCount, fast);
		Bind(a_vm, "OrderTemplate"sv, OrderTemplate, fast);
		Bind(a_vm, "OrderPriority"sv, OrderPriority, fast);
		Bind(a_vm, "OrderDone"sv, OrderDone, fast);
		Bind(a_vm, "OrderGone"sv, OrderGone, fast);
		logger::info("papyrus: {} natives bound, protocol {}", kScript, kProtocol);
		return true;
	}
}

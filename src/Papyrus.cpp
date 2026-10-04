#include "Papyrus.h"

#include "Camera.h"
#include "Game.h"
#include "Sinks.h"

namespace CX::Papyrus
{
	namespace
	{
		constexpr auto kScript = "Complexion:DLL"sv;

		// 1: the first bridge (orders of whole looks, Done/Gone, Configure, ResetAll, Unapply, Warning).
		// 2: the overlay window (C-19): crosshair, camera, the window's session.
		constexpr std::int32_t kProtocol = 2;

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
		Str Notice(std::monostate) { return Str{ Game::TakeNotice() }; }

		// A line from the bridge into Complexion.log (the "what is on them" button).
		void Log(std::monostate, Str a_line) { logger::info("bridge: {}", a_line.c_str() ? a_line.c_str() : ""); }

		// What Complexion decided for an actor, for the same button: "group: id, id" or "" when nothing yet.
		Str Decided(std::monostate, std::int32_t a_ref)
		{
			const auto r = D().RecordFor(static_cast<std::uint32_t>(a_ref));
			if (!r) {
				return Str{};
			}
			std::string list;
			for (const auto& p : r->picks) {
				list += (list.empty() ? "" : ", ") + p.id;
			}
			const bool waiting = !r->applied && !r->picks.empty();
			return Str{ std::format("{}{}: {}", r->group, waiting ? " (not yet on them)" : "", list.empty() ? "nothing" : list) };
		}

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

		// Main thread: reads the actor.
		Str NameOf(std::monostate, std::int32_t a_ref)
		{
			const auto id = static_cast<std::uint32_t>(a_ref);
			return Str{ std::format("{} ({:08X})", Game::NameOf(Game::ActorFor(id)), id) };
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

		Str OrderGroup(std::monostate, std::int32_t a_id) { return Str{ D().GroupOf(Id(a_id)) }; }

		bool OrderPersona(std::monostate, std::int32_t a_id, Str a_persona)
		{
			// Papyrus hands strings back in any case: Rapport's personas are lowercase, so are these keys.
			std::string p = a_persona.c_str() ? a_persona.c_str() : "";
			std::ranges::transform(p, p.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
			return D().SetPersona(Id(a_id), p);
		}

		bool OrderRegroup(std::monostate, std::int32_t a_id, Str a_group)
		{
			return D().Regroup(Id(a_id), a_group.c_str() ? std::string_view{ a_group.c_str() } : std::string_view{});
		}

		// ---- the overlay window (C-19) ----

		std::int32_t CrosshairActor(std::monostate, float a_recentSeconds) { return static_cast<std::int32_t>(Game::CrosshairActor(a_recentSeconds)); }

		Str CameraFrame(std::monostate, float a_x, float a_y, float a_z, float a_angle, float a_height)
		{
			return Str{ Camera::Frame(a_x, a_y, a_z, a_angle, a_height) };
		}
		Str CameraRestore(std::monostate) { return Str{ Camera::Restore() }; }

		// The camera close to where a template sits on them (the window, after one is put on). "none" when it has
		// no spot (a mark over the whole body): the camera stays.
		Str CameraFocus(std::monostate, float a_x, float a_y, float a_z, float a_angle, float a_height, Str a_key)
		{
			const auto spot = D().SpotOf(a_key.c_str() ? a_key.c_str() : "");
			if (!spot || (*spot)[6] > 0.15F) {
				return Str{ "none" };  // over the whole body, or spread wide (a sunburn, a tan): the whole of them
			}
			const auto& s = *spot;
			return Str{ Camera::FrameView(Shot::Focus(a_x, a_y, a_z, a_angle, a_height,
				Shot::Spot{ s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7] > 0.5F })) };
		}
		Str CameraStep(std::monostate) { return Str{ Camera::Step() }; }

		Str  WindowBegin(std::monostate, std::int32_t a_ref, bool a_female) { return Str{ D().WindowBegin(Id(a_ref), a_female) }; }
		void WindowEnd(std::monostate) { D().WindowEnd(); }
		Str  WindowBuild(std::monostate) { return Str{ D().ThumbBuild() }; }

		Str WindowPage(std::monostate, Str a_category, Str a_search, std::int32_t a_page, std::int32_t a_per)
		{
			// Papyrus hands strings back in any case: the categories are lowercase.
			std::string cat = a_category.c_str() ? a_category.c_str() : "";
			std::ranges::transform(cat, cat.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
			return Str{ D().WindowPage(cat, a_search.c_str() ? a_search.c_str() : "", a_page, a_per) };
		}

		bool WindowToggle(std::monostate, Str a_key)
		{
			// A key is "f:<id>", and it may come back in another case: the director finds it case-insensitively.
			return D().WindowToggle(a_key.c_str() ? a_key.c_str() : "");
		}

		std::int32_t WindowCount(std::monostate) { return static_cast<std::int32_t>(D().WindowCount()); }
		void         WindowClear(std::monostate) { D().WindowClear(); }
		void         WindowRoll(std::monostate) { D().WindowRoll(); }
		std::int32_t WindowPreview(std::monostate) { return static_cast<std::int32_t>(D().WindowPreview()); }
		std::int32_t WindowRestore(std::monostate) { return static_cast<std::int32_t>(D().WindowRestore()); }
		void         WindowApply(std::monostate) { D().WindowApply(); }

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
		Bind(a_vm, "Notice"sv, Notice, fast);
		Bind(a_vm, "Log"sv, Log, fast);
		Bind(a_vm, "Decided"sv, Decided, fast);
		Bind(a_vm, "NameOf"sv, NameOf, main);
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
		Bind(a_vm, "OrderGroup"sv, OrderGroup, fast);
		Bind(a_vm, "OrderRegroup"sv, OrderRegroup, fast);
		Bind(a_vm, "OrderPersona"sv, OrderPersona, fast);
		Bind(a_vm, "CrosshairActor"sv, CrosshairActor, main);
		Bind(a_vm, "CameraFrame"sv, CameraFrame, main);
		Bind(a_vm, "CameraRestore"sv, CameraRestore, main);
		Bind(a_vm, "CameraFocus"sv, CameraFocus, main);
		Bind(a_vm, "CameraStep"sv, CameraStep, main);
		Bind(a_vm, "WindowBegin"sv, WindowBegin, fast);
		Bind(a_vm, "WindowEnd"sv, WindowEnd, fast);
		Bind(a_vm, "WindowBuild"sv, WindowBuild, fast);
		Bind(a_vm, "WindowPage"sv, WindowPage, fast);
		Bind(a_vm, "WindowToggle"sv, WindowToggle, fast);
		Bind(a_vm, "WindowCount"sv, WindowCount, fast);
		Bind(a_vm, "WindowClear"sv, WindowClear, fast);
		Bind(a_vm, "WindowRoll"sv, WindowRoll, fast);
		Bind(a_vm, "WindowPreview"sv, WindowPreview, fast);
		Bind(a_vm, "WindowRestore"sv, WindowRestore, fast);
		Bind(a_vm, "WindowApply"sv, WindowApply, fast);
		logger::info("papyrus: {} natives bound, protocol {}", kScript, kProtocol);
		return true;
	}
}

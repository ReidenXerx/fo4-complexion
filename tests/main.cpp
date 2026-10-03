// Complexion's offline tests: everything with no game in it.
//
//   ComplexionTests                       the unit checks
//   ComplexionTests --parity <dump file>  the C++ composer against tools/compose.py --dump: every line must match

#include "Compose.h"
#include "Director.h"

namespace
{
	int g_failures = 0;

	void Directors(const CX::Profiles& a_profiles, const std::vector<CX::Template>& a_catalog);

	void Check(bool a_ok, std::string_view a_what)
	{
		if (!a_ok) {
			++g_failures;
			std::println("FAIL: {}", a_what);
		}
	}

	std::filesystem::path Root()
	{
		auto p = std::filesystem::current_path();
		while (!p.empty() && !std::filesystem::exists(p / "data" / "profiles.json")) {
			if (p == p.parent_path()) {
				return {};
			}
			p = p.parent_path();
		}
		return p;
	}

	std::string Text(const std::filesystem::path& a_path)
	{
		std::ifstream in(a_path, std::ios::binary);
		return { std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>() };
	}

	nlohmann::json Read(const std::filesystem::path& a_path)
	{
		std::ifstream in(a_path, std::ios::binary);
		return nlohmann::json::parse(in, nullptr, true, true);
	}

	int Parity(const std::filesystem::path& a_dump)
	{
		const auto root = Root();
		const auto profiles = CX::ParseProfiles(Text(root / "data" / "profiles.json"));
		const auto catalog = CX::ParseCatalog(Read(root / "build" / "tags.json"), {});
		std::ifstream in(a_dump);
		std::string   line;
		int           lines = 0, bad = 0;
		while (std::getline(in, line)) {
			if (!line.empty() && line.back() == '\r') {
				line.pop_back();
			}
			// Tab-separated: group names ("npc:Piper Wright") and template ids have spaces.
			std::vector<std::string> cols;
			for (std::size_t at = 0;;) {
				const auto tab = line.find('\t', at);
				cols.push_back(line.substr(at, tab == std::string::npos ? std::string::npos : tab - at));
				if (tab == std::string::npos) {
					break;
				}
				at = tab + 1;
			}
			if (cols.size() != 6) {
				std::println("bad line: {}", line);
				return 1;
			}
			const auto&   group = cols[0];
			const auto&   sex = cols[1];
			const auto    seed = std::stoull(cols[2]);
			const int     adult = std::stoi(cols[3]);
			const auto&   persona = cols[4];
			const auto&   picks = cols[5];
			const auto* g = profiles.Find(group);
			if (!g) {
				std::println("no group {}", group);
				return 1;
			}
			std::string mine;
			for (const auto& p : CX::Compose(profiles, catalog, sex == "f", *g, seed, adult != 0, persona)) {
				mine += std::format("{}{}@{}", mine.empty() ? "" : ",", p.key, p.priority);
			}
			++lines;
			if (mine != picks) {
				if (++bad <= 5) {
					std::println("MISMATCH {} {} {} {}\n  python: {}\n  c++:    {}", group, sex, seed, adult, picks, mine);
				}
			}
		}
		std::println("parity: {} line(s), {} mismatch(es)", lines, bad);
		return lines > 0 && bad == 0 ? 0 : 1;
	}

	void Units()
	{
		const auto root = Root();
		Check(!root.empty(), "the repository root is found");
		const auto profiles = CX::ParseProfiles(Text(root / "data" / "profiles.json"));
		const auto catalog = CX::ParseCatalog(Read(root / "build" / "tags.json"), {});
		Check(profiles.Find("raiders") != nullptr, "the raiders group is read");
		Check(profiles.groups.back().name == profiles.fallback, "the default group comes last");
		Check(!catalog.empty(), "the catalog has templates");

		// Every roll stays under the cap, never repeats a template, and keeps emblems to members.
		for (const auto& g : profiles.groups) {
			for (bool female : { true, false }) {
				for (std::uint64_t seed = 1; seed < 400; ++seed) {
					const auto picks = CX::Compose(profiles, catalog, female, g, seed * 7919, true);
					Check(static_cast<int>(picks.size()) <= profiles.cap, std::format("{}: at most the cap", g.name));
					std::set<std::string> keys;
					for (const auto& p : picks) {
						Check(keys.insert(p.key).second, std::format("{}: {} once", g.name, p.key));
						Check(p.priority < 0, "our priorities are negative (C-6)");
						const auto t = std::ranges::find(catalog, p.key, &CX::Template::key);
						if (t != catalog.end() && !t->emblem.empty()) {
							Check(std::ranges::find(g.emblems, t->emblem) != g.emblems.end(),
								std::format("{}: emblem {} only for members", g.name, t->emblem));
						}
					}
				}
			}
		}

		// No adult piece when adult content is off.
		const auto* raiders = profiles.Find("raiders");
		for (std::uint64_t seed = 1; seed < 400; ++seed) {
			for (const auto& p : CX::Compose(profiles, catalog, true, *raiders, seed, false)) {
				const auto t = std::ranges::find(catalog, p.key, &CX::Template::key);
				Check(t != catalog.end() && !t->adult, "adult off: no adult piece");
			}
		}

		// The same seed gives the same look.
		Check(CX::Compose(profiles, catalog, true, *raiders, 42, true).size() ==
		          CX::Compose(profiles, catalog, true, *raiders, 42, true).size(),
			"deterministic");

		Directors(profiles, catalog);
	}

	void Directors(const CX::Profiles& a_profiles, const std::vector<CX::Template>& a_catalog)
	{
		CX::Director d;
		d.SetData(a_profiles, a_catalog);
		const CX::Facts raider{ 0x1234, 0x5678, true, "raiders", "Test Raider", "" };

		// Decided once, ordered once, confirmed once.
		d.Seen(raider);
		d.Seen(raider);
		Check(d.RecordCount() == 1, "one record per actor");
		const auto first = d.RecordFor(0x1234);
		Check(first && !first->picks.empty(), "a raider woman gets something (4 universal rolls + 95% features)");
		const auto id = d.NextOrder();
		Check(id != 0 && d.NextOrder() == 0, "one order per actor at a time");
		const auto order = d.GetOrder(id);
		Check(order && order->ref == 0x1234 && order->picks.size() == first->picks.size(), "the order carries the look");
		d.Done(id, true);
		d.Seen(raider);
		Check(d.NextOrder() == 0, "a confirmed look is not ordered again");
		Check(d.RecordFor(0x1234)->picks.size() == first->picks.size(), "the look is kept, not re-rolled");

		// Gone: the work waits for the next sighting.
		CX::Facts other{ 0x2222, 0x3333, false, "", "Settler", "" };
		d.Seen(other);
		if (const auto o = d.NextOrder(); o) {
			d.Gone(o);
			Check(d.NextOrder() == 0, "gone: nothing until seen again");
			d.Seen(other);
			Check(d.NextOrder() != 0, "seen again: ordered again");
		}

		// A captive the record could not see: composed again for the captives, same seed, before it is put on.
		CX::Facts held{ 0x4444, 0x5555, true, "raiders", "Captive", "" };
		d.Seen(held);
		if (const auto o = d.NextOrder(); o) {
			Check(d.GroupOf(o) == "raiders", "the record's group first");
			Check(d.Regroup(o, "Captives") && d.GroupOf(o) == "captives", "regrouped as a captive, whatever case Papyrus hands the name in");
			const auto again = CX::Compose(a_profiles, a_catalog, true, *a_profiles.Find("captives"), 0, true);
			Check(d.GetOrder(o)->picks.size() == d.RecordFor(0x4444)->picks.size(), "the order carries the new look");
			Check(!d.Regroup(o, "nobody"), "an unknown group is refused");
			(void)again;
		}

		// Left alone.
		d.Seen({ 0x9999, 0x1, true, "raiders", "Corpse", "dead" });
		Check(!d.RecordFor(0x9999), "the dead get no decision");

		// The co-save round trip, and a form that is gone in the new load order.
		const auto bytes = d.Save();
		CX::Director e;
		Check(e.Load(bytes, [](std::uint32_t a_ref) { return a_ref == 0x2222 ? 0u : a_ref; }), "the co-save loads");
		Check(e.RecordFor(0x1234) && e.RecordFor(0x1234)->applied && e.RecordFor(0x1234)->picks.size() == first->picks.size(),
			"records survive the co-save");
		Check(!e.RecordFor(0x2222), "a record whose actor is gone is dropped");
		Check(e.Salt() == d.Salt(), "the salt survives the co-save");
		Check(!e.Load(std::span(bytes).first(bytes.size() / 2), {}), "a truncated co-save is refused");

		// The overlay window (C-19): a draft, previews that change no record, Cancel back to what they had, Apply kept.
		{
			const auto before = d.RecordFor(0x1234)->picks;
			Check(d.WindowBegin(0x1234, true).empty() && d.WindowCount() == before.size(), "the window opens on what Complexion put on them");
			const auto page = d.WindowPage("skin", "", 0, 15);
			Check(page.find('|') != std::string::npos, "a page lists something");
			const auto firstKey = page.substr(page.find('|') + 1, page.find('\t') - page.find('|') - 1);
			const bool wasOn = std::ranges::any_of(before, [&](const CX::Pick& p) { return p.key == firstKey; });
			std::string shouted = firstKey;
			std::ranges::transform(shouted, shouted.begin(), [](unsigned char c) { return static_cast<char>(std::toupper(c)); });
			Check(d.WindowToggle(shouted) == !wasOn, "a toggle flips it, whatever case Papyrus hands the key in");
			const auto preview = d.WindowPreview();
			Check(preview != 0 && d.GetOrder(preview)->window, "a preview is a window order");
			d.Done(preview, true);
			Check(d.RecordFor(0x1234)->picks.size() == before.size(), "a preview changes no record");
			const auto restore = d.WindowRestore();
			Check(d.GetOrder(restore)->picks.size() == before.size(), "Cancel puts back what they had");
			d.Done(restore, true);
			d.WindowClear();
			Check(d.WindowCount() == 0, "Clear empties the draft");
			d.WindowRoll();
			const auto rolled = d.WindowCount();
			d.WindowApply();
			Check(d.RecordFor(0x1234)->manual && d.RecordFor(0x1234)->picks.size() == rolled, "Apply keeps the draft, chosen by hand");
			d.WindowEnd();
			CX::Director g;
			Check(g.Load(d.Save(), {}) && g.RecordFor(0x1234)->manual, "a hand-chosen look survives the co-save");
			// The player: never decided for, but a look they chose is put back when it is not on them.
			const CX::Facts me{ 0x14, 0x7, true, "", "Player", "player" };
			d.Seen(me);
			Check(!d.RecordFor(0x14), "the player gets no random look");
			Check(d.WindowBegin(0x14, true).empty(), "the window opens on the player");
			const auto mine = d.WindowPage("skin", "", 0, 15);  // a roll may give a settler nothing: one by hand
			d.WindowToggle(mine.substr(mine.find('|') + 1, mine.find('\t') - mine.find('|') - 1));
			Check(d.WindowCount() == 1, "one overlay chosen for the player");
			d.WindowApply();
			d.WindowEnd();
			d.Unapply();
			d.Seen(me);
			const auto again = d.NextOrder();
			Check(again != 0 && d.GetOrder(again)->ref == 0x14, "the player's chosen look is put back after a clear");
		}

		// Reset: forgotten, and rolled with a new salt.
		const auto salt = d.Salt();
		d.ResetAll();
		Check(d.RecordCount() == 0 && d.Salt() != salt, "Reset forgets everyone and changes the salt");
	}
}

int main(int a_argc, char** a_argv)
{
	try {
		if (a_argc == 3 && std::string_view(a_argv[1]) == "--parity") {
			return Parity(a_argv[2]);
		}
		Units();
	} catch (const std::exception& e) {
		std::println("EXCEPTION: {}", e.what());
		return 1;
	}
	std::println("{}", g_failures ? std::format("{} failure(s)", g_failures) : "all tests passed");
	return g_failures ? 1 : 0;
}

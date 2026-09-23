// Offline tests for everything in the plugin with no game in it: the catalog reader, OBody's rule
// priority as the runtime applies it (S-23), the bodies the plugin writes (variety S-17/S-21, never the
// shaft S-29), ORefit's keyword floors (S-40..S-42), the co-save bytes (S-43, S-47), and the whole
// director -- driven through a fake bridge that does to a fake LooksMenu exactly what Silhouette:Bridge
// does to the real one. The fake keeps LooksMenu's three kinds of layer (unkeyed, Silhouette's refit
// keyword, another mod's keyword) and shows the MAXIMUM over them, as LooksMenu does, so each test checks
// what the woman would look like, not just the orders on the way. It can also stop an order half-way,
// the way a save that lands between two bridge calls does.
//
//     build\Release\SilhouetteTests.exe        -> "N passed, 0 failed", exit code 0

#include "PCH.h"

#include "Catalog.h"
#include "Director.h"
#include "Plan.h"
#include "Registry.h"
#include "Rules.h"

#include <iostream>
#include <sstream>

namespace
{
	int g_failed = 0;
	int g_passed = 0;

	void Check(bool a_ok, std::string_view a_what)
	{
		if (a_ok) {
			++g_passed;
		} else {
			++g_failed;
			std::cout << "FAIL: " << a_what << "\n";
		}
	}

	nlohmann::json BaseCatalog()
	{
		return nlohmann::json::parse(R"json({
			"schema": 1, "build": "abc123", "stamp": 1234, "mode": "absolute", "rulesHash": "r0",
			"states": {"female": ["VaginaPenetrate"], "male": ["Erection"]},
			"neverInBody": {"female": ["VaginaPenetrate"], "male": ["Erection", "Penis Width"]},
			"presets": [
				{"name": "Curvy", "sex": "female", "marker": "Silhouette_Curvy", "values": {"Breasts": 0.8, "Butt": 0.5},
				 "random": true, "menu": true, "zeroed": false, "fit": "full", "family": "CBBE"},
				{"name": "Slim", "sex": "female", "marker": "Silhouette_Slim", "values": {"Breasts": 0.2, "NippleSize": 0.9},
				 "random": true, "menu": true, "zeroed": false, "fit": "full", "family": "CBBE"},
				{"name": "Athletic", "sex": "female", "marker": "Silhouette_Athletic", "values": {"Waist": -0.3},
				 "random": true, "menu": true, "zeroed": false, "fit": "full", "family": "CBBE"},
				{"name": "BT - Average", "sex": "male", "marker": "Silhouette_BT_Average", "values": {"BTChest": 0.4},
				 "random": true, "menu": true, "zeroed": false, "fit": "full", "family": "BodyTalk"}
			],
			"player": {"female": "Slim", "male": "BT - Average"},
			"variety": {
				"female": [{"morph": "NippleSize", "low": 0.0, "high": 0.5, "group": "nipples"},
				           {"morph": "VaginaSize", "low": -0.3, "high": 0.3, "group": "genitals"}],
				"male": [{"morph": "BTBallSize", "low": 0.1, "high": 0.4, "group": "genitals"}]
			},
			"rules": {
				"races": ["HumanRace"],
				"npcFormID": {"female": [{"plugin": "Fallout4.esm", "id": 1000}], "male": []},
				"blacklistedNpcsFormID": [{"plugin": "Fallout4.esm", "id": 2000}],
				"blacklistedPlugins": {"female": ["Blocked.esp"], "male": []},
				"blacklistedRaces": {"female": ["GhoulRace"], "male": []},
				"npcName": [{"name": "Piper", "sex": "female", "presets": ["Curvy"]},
				            {"name": "Blocked Name Rule", "sex": "female", "presets": ["Slim"]}],
				"blacklistedNpcNames": ["Mama Murphy"],
				"faction": [{"plugin": "Fallout4.esm", "id": 3000, "editorID": "BoSFaction", "sex": "female", "presets": ["Athletic"]},
				            {"plugin": "Fallout4.esm", "id": 3001, "editorID": "RaiderFaction", "sex": "female", "presets": ["Slim", "Curvy"]}]
			},
			"orefit": {
				"slots": [33, 36, 41],
				"blacklist": [], "blacklistNames": ["Sheer Dress"], "blacklistPlugins": [],
				"force": [], "forceNames": [],
				"outfits": [{"name": "Vault 111 Jumpsuit", "sex": "female", "set": "Jumpsuit-Refit"}],
				"sets": [
					{"name": "builtin:female", "sex": "female", "floors": [
						{"morph": "BreastsTogether", "value": 0.3, "heavyOnly": false},
						{"morph": "PushUp", "value": 0.2, "heavyOnly": false},
						{"morph": "NipBGone", "value": 1.0, "heavyOnly": true}]},
					{"name": "Curvy-Refit", "sex": "female", "floors": [{"morph": "Breasts", "value": 0.95, "heavyOnly": false}]},
					{"name": "Jumpsuit-Refit", "sex": "female", "floors": [{"morph": "BreastsTogether", "value": 0.6, "heavyOnly": false}]}
				],
				"heavy": {"armorRating": 10, "items": [], "names": []},
				"light": {"items": [], "names": []}
			}
		})json");
	}

	SH::ActorFacts Npc()
	{
		SH::ActorFacts a;
		a.female = true;
		a.baseName = "Somebody";
		a.bases = { { "Fallout4.esm", 0x12345 } };
		a.originPlugin = "Fallout4.esm";
		a.race = "HumanRace";
		a.seed = 0xFF000801;
		return a;
	}

	std::shared_ptr<const SH::Catalog> Cat(const nlohmann::json& a_doc)
	{
		std::string error;
		auto        c = SH::ParseCatalog(a_doc, error);
		if (!c) {
			Check(false, std::format("test catalog: {}", error));
			return nullptr;
		}
		// An older build's manifest: Curvy then carried a shaft value... on a woman? No -- a man's body.
		std::unordered_map<std::string, SH::ManifestEntry> old{
			{ "Silhouette_BT_Old", { "BT - Average", false, { "BTChest", "Penis Width", "Erection" } } },
			{ "Silhouette_Curvy", { "Curvy", true, { "Breasts", "Butt" } } },
		};
		c->AddManifest(99, std::move(old));
		return std::make_shared<const SH::Catalog>(std::move(*c));
	}

	// ------------------------------------------------------------------ catalog

	void TestCatalog()
	{
		std::string error;
		auto        c = SH::ParseCatalog(BaseCatalog(), error);
		Check(c.has_value(), std::format("the base catalog parses ({})", error));
		if (!c) {
			return;
		}
		Check(c->presets.size() == 4, "four presets");
		Check(c->Find("Curvy", true) != nullptr && c->Find("Curvy", false) == nullptr, "presets are per sex");
		Check(c->FindByMarker("silhouette_slim") && c->FindByMarker("Silhouette_Slim")->name == "Slim", "marker -> preset, any case");
		Check(c->playerDefault[1] == "Slim" && c->playerDefault[0] == "BT - Average", "player defaults");
		Check(c->NeverInBody(false, "penis width") && !c->NeverInBody(true, "Penis Width"), "never-in-body is per sex");
		Check(SH::KindOf("Silhouette_Refit") == SH::MarkerKind::kRefit && SH::KindOf("Silhouette_Curvy") == SH::MarkerKind::kBody &&
				  SH::KindOf("Breasts") == SH::MarkerKind::kNone,
			"marker kinds");

		struct Broken
		{
			std::function<void(nlohmann::json&)> edit;
			std::string_view                     what;
		};
		const std::vector<Broken> broken{
			{ [](auto& d) { d["rules"]["npcName"][0]["presets"] = { "Nobody" }; }, "a rule naming a preset the catalog lacks" },
			{ [](auto& d) { d["rules"]["faction"][0]["id"] = 0x01003000; }, "a form id with a load-order byte" },
			{ [](auto& d) { d["presets"][0]["sex"] = "Female"; }, "sex that is not exactly female or male" },
			{ [](auto& d) { d["schema"] = 2; }, "another schema" },
			{ [](auto& d) { d["stamp"] = 1 << 24; }, "a stamp a float32 cannot hold exactly" },
			{ [](auto& d) { d["presets"][0]["marker"] = "Curvy"; }, "a marker without the Silhouette_ prefix" },
			{ [](auto& d) { d["presets"][1]["marker"] = "Silhouette_curvy"; }, "two presets sharing a marker" },
			{ [](auto& d) { d["presets"][0]["marker"] = "Silhouette_Blacklisted"; }, "a preset using the reserved blacklist marker" },
			{ [](auto& d) { d["presets"][0]["marker"] = "Silhouette_Refit"; }, "a preset using the reserved refit marker" },
			{ [](auto& d) { d["variety"]["male"][0]["morph"] = "Penis Width"; }, "variety on a morph never part of a body (S-29)" },
			{ [](auto& d) { d["presets"][0]["values"]["Breasts"] = 1e39; }, "a value a float cannot hold" },
			{ [](auto& d) { d["presets"][0]["values"] = nlohmann::json::array({ 0.1, 0.2 }); }, "values given as a list" },
			{ [](auto& d) { d["rules"]["races"] = nullptr; }, "null where a list belongs" },
			{ [](auto& d) { d["orefit"]["sets"][1]["name"] = "BUILTIN:female"; }, "a refit set listed twice" },
			{ [](auto& d) { d["neverInBody"]["female"] = nlohmann::json::array(); }, "a runtime state missing from never-in-body" },
			{ [](auto& d) { d["presets"][3]["values"]["Penis Width"] = 1.0; }, "a preset carrying a shaft value (S-29)" },
			{ [](auto& d) { d["orefit"]["sets"][0]["floors"][0]["morph"] = "Silhouette_Curvy"; }, "a refit floor on a marker" },
			{ [](auto& d) { d["orefit"]["outfits"][0]["set"] = "Nope-Refit"; }, "an outfit naming a set that does not exist" },
			{ [](auto& d) { d.erase("rulesHash"); }, "no rules hash" },
		};
		for (const auto& b : broken) {
			auto doc = BaseCatalog();
			b.edit(doc);
			Check(!SH::ParseCatalog(doc, error), std::format("refused: {}", b.what));
		}

		{
			std::istringstream both("# Silhouette - generated\r\n# 43 female, 8 male templates. Build 3198337fbaec, marker stamp 3250227 (absolute), rules 0a1b2c3d4e5f.\r\n");
			const auto h = SH::ParseFilesHeader(both);
			Check(h && h->build == "3198337fbaec" && h->stamp == 3250227 && h->rules == "0a1b2c3d4e5f", "a header names its build, stamp and rules");
			std::istringstream old("# 43 female, 8 male templates. Build 3198337fbaec, marker stamp 3250227 (absolute).\r\n");
			const auto o = SH::ParseFilesHeader(old);
			Check(o && o->stamp == 3250227 && o->rules.empty(), "an older header states no rules");
			std::istringstream none("# nothing here\n#\n");
			Check(!SH::ParseFilesHeader(none), "a header without a build is not one");
		}

		const auto manifest = nlohmann::json::parse(R"json({"stamp": 99, "templates": {
			"Silhouette_Old": {"preset": "Old Preset (v1)", "gender": "male", "values": {"BTChest": 1.0, "Penis Width": 1.0}}}})json");
		auto m = SH::ParseManifest(manifest, error);
		Check(m.has_value(), "a manifest parses");
		if (m) {
			c->AddManifest(m->first, m->second);
			Check(c->PresetForMarker("Silhouette_Old", 99) == "Old Preset (v1)", "an older build's marker names its preset");
			Check(!c->PresetForMarker("Silhouette_Old", 1234).has_value(), "a marker is read against ITS stamp only");
			Check(c->PresetForMarker("Silhouette_Curvy", 1234) == "Curvy", "the current build's markers fall back to the catalog");
			const auto heal = c->HealFor("Silhouette_Old", 99);
			Check(heal.size() == 1 && heal[0] == "Penis Width", "HealFor names exactly what that template held that no body may hold");
			Check(c->HealFor("Silhouette_Curvy", 1234).empty(), "this build's bodies need no heal");
		}
	}

	// ------------------------------------------------------------------ rules

	void TestRules()
	{
		std::string error;
		const auto  c = SH::ParseCatalog(BaseCatalog(), error);
		if (!c) {
			Check(false, "catalog for the rules");
			return;
		}
		auto a = Npc();
		Check(SH::Decide(*c, a).tier == SH::Tier::kNone && !SH::Decide(*c, a).blacklisted, "a plain NPC keeps BodyGen's roll");
		a.baseName = "piper";
		auto v = SH::Decide(*c, a);
		Check(v.tier == SH::Tier::kName && v.preset == "Curvy", "npc by name, case-insensitive");
		a = Npc();
		a.baseName = "Piper";
		a.female = false;
		Check(SH::Decide(*c, a).tier == SH::Tier::kNone, "a name rule is for its own sex only");
		a = Npc();
		a.baseName = "Mama Murphy";
		v = SH::Decide(*c, a);
		Check(v.tier == SH::Tier::kNameBlacklist && v.blacklisted, "name blacklist");
		a = Npc();
		a.baseName = "Mama Murphy";
		a.bases = { { "Fallout4.esm", 2000 } };
		v = SH::Decide(*c, a);
		Check(v.tier == SH::Tier::kNone && v.blacklisted, "form id blacklist is BodyGen's, outranks everything, and counts as blacklisted");
		a = Npc();
		a.baseName = "Piper";
		a.bases = { { "Fallout4.esm", 0x12345 }, { "fallout4.ESM", 1000 } };
		Check(SH::Decide(*c, a).tier == SH::Tier::kNone, "a per-NPC form id preset on a template outranks a name rule");
		a = Npc();
		a.factions = { { "Fallout4.esm", 3000 } };
		v = SH::Decide(*c, a);
		Check(v.tier == SH::Tier::kFaction && v.preset == "Athletic", "faction rule");
		a.baseName = "Piper";
		Check(SH::Decide(*c, a).preset == "Curvy", "a name rule outranks a faction rule");
		a = Npc();
		a.factions = { { "Fallout4.esm", 3000 } };
		a.originPlugin = "Blocked.esp";
		v = SH::Decide(*c, a);
		Check(v.tier == SH::Tier::kNone && v.blacklisted, "a plugin blacklist outranks a faction rule and counts as blacklisted");
		a.baseName = "Piper";
		v = SH::Decide(*c, a);
		Check(v.tier == SH::Tier::kName && !v.blacklisted, "a name rule outranks a plugin blacklist (OBody's order): not blacklisted");
		a = Npc();
		a.race = "GhoulRace";
		Check(SH::Decide(*c, a).tier == SH::Tier::kNone, "an undistributed race is never ours");
		a = Npc();
		a.factions = { { "Fallout4.esm", 3001 } };
		const auto first = SH::Decide(*c, a).preset;
		bool       same = true;
		for (int i = 0; i < 20; ++i) {
			same &= SH::Decide(*c, a).preset == first;
		}
		Check(same, "a rule with several presets draws the same one for the same person");
		std::set<std::string> drawn;
		for (std::uint32_t id = 0xFF000800; id < 0xFF000840; ++id) {
			a.seed = id;
			drawn.insert(SH::Decide(*c, a).preset);
		}
		Check(drawn.size() == 2, "a rule with several presets spreads them across people");
	}

	// ------------------------------------------------------------------ plans

	std::optional<float> Value(const SH::Morphs& a_m, std::string_view a_k)
	{
		const auto it = std::ranges::find_if(a_m, [&](const auto& p) { return p.first == a_k; });
		return it == a_m.end() ? std::optional<float>{} : std::optional<float>{ it->second };
	}

	void TestPlan()
	{
		const auto c = Cat(BaseCatalog());
		if (!c) {
			return;
		}
		const auto* curvy = c->Find("Curvy", true);
		const auto  a = SH::BodyFor(*c, *curvy, 0xFF000801, {});
		Check(a == SH::BodyFor(*c, *curvy, 0xFF000801, {}), "the same person gets the same body every time");
		Check(Value(a, "Breasts") == 0.8F && Value(a, "Butt") == 0.5F, "the preset's own values");
		Check(a.back().first == "Silhouette_Curvy" && a.back().second == 1234.0F, "the marker, last, holding the stamp");
		const auto nip = Value(a, "NippleSize");
		const auto vag = Value(a, "VaginaSize");
		Check(nip && *nip >= 0.0F && *nip < 0.5F && vag && *vag >= -0.3F && *vag < 0.3F, "every range drawn, inside its range");

		// S-21: a range REPLACES the preset's own value. Slim sets NippleSize 0.9, outside 0..0.5.
		const auto* slim = c->Find("Slim", true);
		const auto  s = SH::BodyFor(*c, *slim, 0xFF000801, {});
		Check(Value(s, "NippleSize") && *Value(s, "NippleSize") < 0.5F &&
				  *Value(s, "NippleSize") == SH::Draw(0xFF000801, "NippleSize", 0.0F, 0.5F),
			"a preset's own value for a ranged morph is replaced by the draw");
		const auto off = SH::BodyFor(*c, *slim, 0xFF000801, { .nipples = false, .genitals = true });
		Check(Value(off, "NippleSize") == 0.9F, "with nipple variety off, the preset's own value stays");

		// never the shaft (S-29), never a state (S-16), whatever the preset says
		auto withNever = *c;
		for (auto& p : withNever.presets) {
			if (p.name == "BT - Average") {
				p.values.emplace_back("Penis Width", 1.0F);
				p.values.emplace_back("Erection", 1.0F);
			}
		}
		const auto m = SH::BodyFor(withNever, *withNever.Find("BT - Average", false), 7, {});
		Check(!Value(m, "Penis Width") && !Value(m, "Erection") && Value(m, "BTBallSize"), "never the shaft, never a state; balls rolled");

		// keep: what they already hold, inside its range, stays; outside or absent, drawn
		std::unordered_map<std::string, float> keep{ { "NippleSize", 0.33F }, { "VaginaSize", 0.9F } };
		const auto k = SH::BodyFor(*c, *curvy, 0xFF000801, {}, &keep);
		Check(Value(k, "NippleSize") == 0.33F, "a rolled value in range is kept");
		Check(Value(k, "VaginaSize") == SH::Draw(0xFF000801, "VaginaSize", -0.3F, 0.3F), "a value out of range is drawn again");

		// top-up: only what is missing
		const auto t = SH::TopUp(*c, true, 5, {}, { "Breasts", "nipplesize" });
		Check(t.size() == 1 && t[0].first == "VaginaSize", "top-up adds exactly the missing ranges (names compared in any case)");
		Check(SH::TopUp(*c, true, 5, { .nipples = true, .genitals = false }, { "Breasts" }).size() == 1, "top-up follows the switches");

		// refit floors: marker first, heavy-only only when heavy
		const auto* builtin = c->FindRefit("builtin:female", true);
		const auto  light = SH::RefitFloors(*builtin, false);
		const auto  heavy = SH::RefitFloors(*builtin, true);
		Check(light.front().first == "Silhouette_Refit" && light.front().second == 1.0F && heavy.front().second == 2.0F, "the refit marker comes first");
		Check(!Value(light, "NipBGone") && Value(heavy, "NipBGone") == 1.0F && Value(light, "BreastsTogether") == 0.3F, "NipBGone under heavy clothes only");

		float lo = 1.0F;
		float hi = -1.0F;
		for (std::uint32_t id = 0xFF000800; id < 0xFF000900; ++id) {
			const auto v = SH::Draw(id, "VaginaSize", -0.3F, 0.3F);
			lo = std::min(lo, v);
			hi = std::max(hi, v);
		}
		Check(lo < -0.25F && hi > 0.25F, "draws spread across the whole range");
		Check(SH::BodyHash("Silhouette_Curvy", 1234) != SH::BodyHash("Silhouette_Curvy", 1235) &&
				  SH::BodyHash("silhouette_curvy", 1234) == SH::BodyHash("Silhouette_Curvy", 1234) && SH::BodyHash("x", 0) != 0,
			"the body hash tells builds apart, ignores case, and is never 0");
	}

	// ------------------------------------------------------------------ the co-save

	void TestRegistry()
	{
		SH::Registry r;
		auto&        a = r.Get(0x0001A4F2);
		a.base = 0x0002F1E5;
		a.source = SH::Source::kPicker;
		a.preset = "Curvy";
		a.stamp = 1234;
		a.announced = 77;
		a.touched = 88;
		r.Get(0xFF000900).announced = 5;
		(void)r.Get(0x00000001);  // empty: never written
		r.picker = SH::PickerSave{ .ref = 0x0001A4F2, .base = 0x0002F1E5, .female = true,
			.snapshot = { { "Breasts", 0.33F }, { "Silhouette_Slim", 1234.0F } }, .before = a };

		const auto   bytes = r.Serialize([](std::uint32_t) { return true; });
		SH::Registry back;
		std::string  error;
		Check(back.Deserialize(bytes, SH::Registry::kVersion, [](std::uint32_t id) { return id; }, error), std::format("records read back ({})", error));
		const auto* b = back.Find(0x0001A4F2);
		Check(b && b->base == 0x0002F1E5 && b->source == SH::Source::kPicker && b->preset == "Curvy" && b->stamp == 1234 &&
				  b->announced == 77 && b->touched == 88,
			"a record survives the co-save exactly");
		Check(back.Size() == 2, "an empty record is not written");
		Check(back.picker && back.picker->snapshot == r.picker->snapshot && back.picker->before && back.picker->before->preset == "Curvy",
			"a picking in progress survives the co-save (S-47)");

		SH::Registry moved;
		Check(moved.Deserialize(bytes, SH::Registry::kVersion,
				  [](std::uint32_t id) -> std::uint32_t { return id == 0xFF000900 ? 0 : (id & 0x00FFFFFF) | 0x05000000; }, error),
			"records read back with a new load order");
		Check(moved.Size() == 1 && moved.Find(0x0501A4F2) && moved.Find(0x0501A4F2)->base == 0x0502F1E5 && moved.picker &&
				  moved.picker->ref == 0x0501A4F2,
			"ids resolved, the gone one dropped");

		SH::Registry cut;
		cut.Get(42).announced = 1;
		std::vector<std::byte> shorter(bytes.begin(), bytes.end() - 3);
		Check(!cut.Deserialize(shorter, SH::Registry::kVersion, nullptr, error) && cut.Find(42), "cut-short bytes are refused, nothing replaced");
		Check(!cut.Deserialize(bytes, 99, nullptr, error), "another version is refused");
		const auto   kept = r.Serialize([](std::uint32_t id) { return id != 0xFF000900; });
		SH::Registry k;
		Check(k.Deserialize(kept, SH::Registry::kVersion, nullptr, error) && k.Size() == 1, "a deleted reference's record is not saved");
	}

	// ------------------------------------------------------------------ the fake game

	using Layer = std::map<std::string, float>;

	struct FakeActor
	{
		Layer                 unkeyed;
		Layer                 refit;  // Silhouette's keyword
		Layer                 other;  // another mod's keyword (AAF, the anatomy arousal layer)
		std::set<std::string> listed;  // names LooksMenu lists until a load, emptied ones too

		[[nodiscard]] float Effective(const std::string& a_morph) const
		{
			std::optional<float> best;
			for (const auto* l : { &unkeyed, &refit, &other }) {
				if (const auto it = l->find(a_morph); it != l->end()) {
					best = best ? std::max(*best, it->second) : it->second;
				}
			}
			return best.value_or(0.0F);
		}
	};

	struct FakeGame
	{
		std::unordered_map<std::uint32_t, FakeActor> actors;
		std::string                                  rollsTo = "Silhouette_Slim";  // what BodyGen's regenerate gives
		float                                        stamp = 1234.0F;

		// A body as BodyGen writes it: a template's values, its ranges drawn, the marker.
		void Roll(std::uint32_t a_ref, const SH::Catalog& a_c, std::string_view a_marker, float a_stamp)
		{
			auto&       a = actors[a_ref];
			const auto* p = a_c.FindByMarker(a_marker);
			a.unkeyed.clear();
			if (p) {
				for (const auto& [m, v] : SH::BodyFor(a_c, *p, a_ref * 7 + 3, {})) {
					a.unkeyed[m] = v;
				}
			}
			a.unkeyed[std::string{ a_marker }] = a_stamp;
			for (const auto& [m, v] : a.unkeyed) {
				a.listed.insert(m);
			}
		}

		// A save loaded: LooksMenu drops what is empty; names listed are what is there.
		void Load()
		{
			for (auto& [ref, a] : actors) {
				a.listed.clear();
				for (const auto* l : { &a.unkeyed, &a.refit, &a.other }) {
					for (const auto& [m, v] : *l) {
						a.listed.insert(m);
					}
				}
			}
		}
	};

	// Exactly what Silhouette:Bridge does with one order. a_stopAfter: the writes that land before a save
	// cuts the order short (-1: all of them, and Done).
	void RunOrder(SH::Director& d, std::uint32_t a_id, FakeGame& g, int a_stopAfter = -1)
	{
		const auto o = d.Peek(a_id);
		if (!o || d.OrderActor(a_id) != o->ref) {
			return;
		}
		auto& a = g.actors[o->ref];
		if (o->regenerate) {
			// RegenerateMorphs clears every key; the bridge put the keyed values back.
			const auto refit = a.refit;
			const auto other = a.other;
			a = {};
			a.refit = refit;
			a.other = other;
			a.unkeyed[g.rollsTo] = g.stamp;
			for (const auto* l : { &a.unkeyed, &a.refit, &a.other }) {
				for (const auto& [m, v] : *l) {
					a.listed.insert(m);
				}
			}
		}
		if (o->probe) {
			for (const auto& name : a.listed) {
				d.NoteName(a_id, name);
				switch (SH::KindOf(name)) {
				case SH::MarkerKind::kBody:
					d.NoteMarker(a_id, name, a.unkeyed.contains(name) ? a.unkeyed.at(name) : 0.0F);
					break;
				case SH::MarkerKind::kRefit:
					d.NoteMarker(a_id, name, a.refit.contains(name) ? a.refit.at(name) : 0.0F);
					break;
				case SH::MarkerKind::kNone:
					break;
				}
			}
		}
		if (o->readAll) {
			for (const auto& name : a.listed) {
				const auto it = a.unkeyed.find(name);
				if (it != a.unkeyed.end() && it->second != 0.0F) {
					d.NoteLayer(a_id, name, it->second);
				}
			}
		}
		const auto n = d.ReadCount(a_id);
		for (std::int32_t i = 0; i < n; ++i) {
			const auto m = d.ReadMorph(a_id, i);
			const auto it = a.unkeyed.find(m);
			d.NoteRead(a_id, i, it == a.unkeyed.end() ? 0.0F : it->second);
		}
		if (!d.Prepare(a_id)) {
			d.Done(a_id, false);
			return;
		}
		if (d.OrderActor(a_id) != o->ref) {
			return;
		}
		if (d.ClearsUnkeyed(a_id)) {
			a.unkeyed.clear();
		}
		if (d.ClearsRefit(a_id)) {
			a.refit.clear();
		}
		const auto w = d.WriteCount(a_id);
		for (std::int32_t i = 0; i < w; ++i) {
			if (a_stopAfter >= 0 && i >= a_stopAfter) {
				return;  // the save landed here: no Done, and the order is forgotten with the session
			}
			const auto m = d.WriteMorph(a_id, i);
			const auto v = d.WriteValue(a_id, i);
			auto&      layer = d.WriteLayer(a_id, i) == SH::Layer::kRefit ? a.refit : a.unkeyed;
			if (v == 0.0F) {
				layer.erase(m);  // LooksMenu: SetMorph(0) erases the entry
			} else {
				layer[m] = v;
			}
			a.listed.insert(m);
		}
		if (a_stopAfter >= 0) {
			return;
		}
		d.Done(a_id, true);
	}

	int Drain(SH::Director& d, FakeGame& g)
	{
		int n = 0;
		while (const auto id = d.NextOrder()) {
			RunOrder(d, id, g);
			if (++n > 1000) {
				Check(false, "the director keeps handing out orders: a loop");
				break;
			}
		}
		return n;
	}

	std::vector<SH::Event> Events(SH::Director& d)
	{
		std::vector<SH::Event> out;
		while (const auto id = d.NextEvent()) {
			out.push_back(*d.EventAt(id));
		}
		return out;
	}

	bool Has(const std::vector<SH::Event>& a_events, SH::EventKind a_kind, std::string_view a_preset = {})
	{
		return std::ranges::any_of(a_events, [&](const SH::Event& e) { return e.kind == a_kind && (a_preset.empty() || e.preset == a_preset); });
	}

	SH::Sighting See(std::uint32_t a_ref, std::string a_name, bool a_clothed = false, bool a_heavy = false, std::string a_outfit = {})
	{
		SH::Sighting s;
		s.ref = a_ref;
		s.base = 0x00012345;
		s.facts = Npc();
		s.facts.baseName = std::move(a_name);
		s.facts.seed = a_ref;
		s.clothed = a_clothed;
		s.heavy = a_heavy;
		s.outfitSet = std::move(a_outfit);
		return s;
	}

	// A new session over the same saved game: the director's records go through the co-save bytes.
	void Reload(SH::Director& d, FakeGame& g, const nlohmann::json& a_doc = BaseCatalog())
	{
		const auto bytes = d.SaveRecords(nullptr);
		d.ForgetWorld();
		d.RevertRecords();
		std::string error;
		Check(d.LoadRecords(bytes, SH::Registry::kVersion, [](std::uint32_t id) { return id; }, error), std::format("reload ({})", error));
		d.SetCatalog(Cat(a_doc));
		g.Load();
	}

	// ------------------------------------------------------------------ the director: bodies

	void TestBodies()
	{
		SH::Director d;
		FakeGame     g;
		const auto   cat = Cat(BaseCatalog());
		d.SetCatalog(cat);

		// A plain NPC: BodyGen gave them Slim. One probe, one OnActorGenerated, nothing else.
		g.Roll(0x100, *cat, "Silhouette_Slim", 1234.0F);
		const auto before = g.actors[0x100].unkeyed;
		d.Seen(See(0x100, "Somebody"));
		Check(Drain(d, g) == 1, "a plain NPC with a whole body costs one probe");
		Check(Has(Events(d), SH::EventKind::kGenerated, "Slim"), "OnActorGenerated names BodyGen's preset");
		Check(g.actors[0x100].unkeyed == before, "a probe changes nothing");
		d.Seen(See(0x100, "Somebody"));
		Check(Drain(d, g) == 0, "seen again this session: nothing to do");
		Reload(d, g);
		d.Seen(See(0x100, "Somebody"));
		(void)Drain(d, g);
		Check(!Has(Events(d), SH::EventKind::kGenerated), "a new session probes again but announces a body only once");

		// An announcement queued but never handed out before a save is made again after the load.
		g.Roll(0x110, *cat, "Silhouette_Athletic", 1234.0F);
		d.Seen(See(0x110, "Somebody"));
		(void)Drain(d, g);
		Reload(d, g);  // the event was never taken
		d.Seen(See(0x110, "Somebody"));
		(void)Drain(d, g);
		Check(Has(Events(d), SH::EventKind::kGenerated, "Athletic"), "an announcement lost to a save is made again");

		// A name rule: the intent is written the moment it is decided, the body follows.
		g.Roll(0x200, *cat, "Silhouette_Slim", 1234.0F);
		d.Seen(See(0x200, "Piper"));
		const auto intent = d.RecordOf(0x200);
		Check(intent && intent->source == SH::Source::kNameRule && intent->preset == "Curvy", "the rule's intent is recorded before the bridge acts (S-43)");
		(void)Drain(d, g);
		Check(g.actors[0x200].unkeyed.contains("Silhouette_Curvy") && !g.actors[0x200].unkeyed.contains("Silhouette_Slim") &&
				  g.actors[0x200].unkeyed.at("Breasts") == 0.8F,
			"the name rule's preset replaced BodyGen's body, marker and all");
		Check(Has(Events(d), SH::EventKind::kGenerated, "Curvy"), "OnActorGenerated for the rule's body");
		d.Seen(See(0x200, "Piper"));
		Check(Drain(d, g) == 0, "a rule already applied is not applied again");

		// LooksMenu forgot her (a non-persistent NPC away from the loaded area) and BodyGen rolled again:
		// the probe sees reality differ from intent and gives the rule's body back.
		Reload(d, g);
		g.Roll(0x200, *cat, "Silhouette_Athletic", 1234.0F);
		d.Seen(See(0x200, "Piper"));
		(void)Drain(d, g);
		Check(g.actors[0x200].unkeyed.contains("Silhouette_Curvy"), "a body that is not the intended one is given again (S-43)");

		// An API request accepted and saved before the bridge ever ran it survives the save.
		std::string why;
		g.Roll(0x300, *cat, "Silhouette_Slim", 1234.0F);
		Check(d.RequestPreset(0x300, true, 0x00012345, "Athletic", SH::Source::kAPI, why), "an API choice is accepted");
		Reload(d, g);
		d.Seen(See(0x300, "Somebody Else"));
		(void)Drain(d, g);
		Check(g.actors[0x300].unkeyed.contains("Silhouette_Athletic"), "a choice queued before a save lands after the load");

		// A save that cuts a body order short leaves half a body without a marker; the load repairs it.
		Check(d.RequestPreset(0x310, true, 0x00012345, "Curvy", SH::Source::kPicker, why), "picked");
		g.Roll(0x310, *cat, "Silhouette_Slim", 1234.0F);
		const auto cut = d.NextOrder();
		RunOrder(d, cut, g, 1);  // the clear and one write, then the save
		Check(!g.actors[0x310].unkeyed.contains("Silhouette_Curvy"), "(set-up) half a body, no marker");
		Reload(d, g);
		d.Seen(See(0x310, "Somebody"));
		(void)Drain(d, g);
		const auto want = SH::BodyFor(*cat, *cat->Find("Curvy", true), 0x310, {});
		Layer      whole(want.begin(), want.end());
		Check(g.actors[0x310].unkeyed == whole, "the next session gives the whole body");

		// A new build re-gives a picked preset with its values; its own build leaves it be.
		auto next = BaseCatalog();
		next["stamp"] = 5678;
		Reload(d, g, next);
		d.Seen(See(0x310, "Somebody"));
		(void)Drain(d, g);
		Check(g.actors[0x310].unkeyed.contains("Silhouette_Curvy") && g.actors[0x310].unkeyed.at("Silhouette_Curvy") == 5678.0F,
			"a new build re-gives the choice, stamped with the new build");
		Reload(d, g);

		// Name blacklist: bare with the marker; kept bare after LooksMenu forgets; lifted, BodyGen rolls.
		g.Roll(0x400, *cat, "Silhouette_Slim", 1234.0F);
		d.Seen(See(0x400, "Mama Murphy"));
		(void)Drain(d, g);
		Check((g.actors[0x400].unkeyed == Layer{ { "Silhouette_Blacklisted", 1234.0F } }), "a name-blacklisted NPC is bare but for the blacklist marker");
		Check(!Has(Events(d), SH::EventKind::kGenerated), "no body, no OnActorGenerated");
		Reload(d, g);
		g.Roll(0x400, *cat, "Silhouette_Slim", 1234.0F);
		d.Seen(See(0x400, "Mama Murphy"));
		(void)Drain(d, g);
		Check((g.actors[0x400].unkeyed == Layer{ { "Silhouette_Blacklisted", 1234.0F } }), "blacklisted again after BodyGen rolled her behind our back");
		auto lifted = BaseCatalog();
		lifted["rules"]["blacklistedNpcNames"] = nlohmann::json::array();
		Reload(d, g, lifted);
		g.rollsTo = "Silhouette_Athletic";
		d.Seen(See(0x400, "Mama Murphy"));
		(void)Drain(d, g);
		Check(g.actors[0x400].unkeyed.contains("Silhouette_Athletic") && !g.actors[0x400].unkeyed.contains("Silhouette_Blacklisted"),
			"a lifted blacklist lets BodyGen roll them");
		Check(Has(Events(d), SH::EventKind::kGenerated, "Athletic"), "and their new body is announced");
		Reload(d, g);

		// Not ours: the player and the dummies, and races Silhouette does not distribute to.
		auto player = See(0x14, "Piper");
		player.eligible = false;
		d.Seen(player);
		auto ghoul = See(0x500, "Piper");
		ghoul.facts.race = "GhoulRace";
		d.Seen(ghoul);
		Check(Drain(d, g) == 0, "the player, the dummies and undistributed races are left alone");

		// A created reference's id reused by someone else: the record is forgotten.
		Check(d.RequestPreset(0xFF000A00, true, 0x00011111, "Curvy", SH::Source::kPicker, why), "picked");
		(void)Drain(d, g);
		auto stranger = See(0xFF000A00, "Somebody");
		stranger.base = 0x00022222;
		d.Seen(stranger);
		(void)Drain(d, g);
		Check(!d.RecordOf(0xFF000A00) || d.RecordOf(0xFF000A00)->source != SH::Source::kPicker, "a record for a reused id is dropped");

		// A placed leveled NPC respawned: a new temporary base, the same person to LooksMenu. The choice stays.
		Check(d.RequestPreset(0x0A00, true, 0xFF00B000, "Curvy", SH::Source::kPicker, why), "picked");
		(void)Drain(d, g);
		auto respawned = See(0x0A00, "Somebody");
		respawned.base = 0xFF00B001;
		d.Seen(respawned);
		(void)Drain(d, g);
		Check(d.RecordOf(0x0A00) && d.RecordOf(0x0A00)->source == SH::Source::kPicker && g.actors[0x0A00].unkeyed.contains("Silhouette_Curvy"),
			"a placed reference keeps its record when its leveled base is replaced");

		Check(!d.RequestPreset(0x600, true, 1, "Nobody", SH::Source::kAPI, why) && why.find("Nobody") != std::string::npos, "an unknown preset is refused with a reason");
		Check(!d.RequestPreset(0x600, false, 1, "Curvy", SH::Source::kAPI, why), "a preset of the other sex is refused");

		// The latest decision wins while an actor waits; one order per actor at a time.
		(void)d.RequestPreset(0x700, true, 1, "Curvy", SH::Source::kAPI, why);
		(void)d.RequestPreset(0x700, true, 1, "Athletic", SH::Source::kAPI, why);
		(void)d.RequestPreset(0x701, true, 1, "Slim", SH::Source::kAPI, why);
		const auto first = d.NextOrder();
		(void)d.RequestPreset(0x700, true, 1, "Slim", SH::Source::kAPI, why);
		const auto second = d.NextOrder();
		Check(d.Peek(first) && d.Peek(first)->ref == 0x700 && d.Peek(first)->body.preset == "Athletic", "two requests before the bridge came: the second wins");
		Check(d.Peek(second) && d.Peek(second)->ref == 0x701, "an actor with an order in flight waits; the next actor goes");
		Check(d.AssignedPreset(0x700) == "Slim", "AssignedPreset answers with the intent");
		RunOrder(d, first, g);
		RunOrder(d, second, g);
		(void)Drain(d, g);
		Check(g.actors[0x700].unkeyed.contains("Silhouette_Slim"), "and the last decision is the one that lands");

		// Reset: bare, and the intent says so at once; Regenerate: BodyGen's roll, keyed layers kept.
		g.actors[0x700].other["Erection"] = 1.0F;
		Check(d.RequestReset(0x700, true, 1, why) && d.AssignedPreset(0x700).empty(), "Reset: the intent is cleared at once");
		(void)Drain(d, g);
		Check(g.actors[0x700].unkeyed.empty() && g.actors[0x700].refit.empty(), "Reset leaves no unkeyed morph and no refit");
		g.rollsTo = "Silhouette_Curvy";
		Check(d.RequestRegenerate(0x700, true, 1, why), "regenerate accepted");
		(void)Drain(d, g);
		Check(g.actors[0x700].unkeyed.contains("Silhouette_Curvy") && g.actors[0x700].other.at("Erection") == 1.0F &&
				  Has(Events(d), SH::EventKind::kGenerated, "Curvy"),
			"Regenerate: BodyGen's roll, another mod's keyed morph kept, announced");

		// A stale order from another launch is nobody's.
		SH::Director other;
		other.SetCatalog(cat);
		Check(other.OrderActor(first) == 0 && other.Peek(first) == std::nullopt, "an order id from another launch names nothing");
		Check(d.NextOrder() == 0, "(idle)");

		// Lanes: a request goes ahead of probes queued earlier.
		for (std::uint32_t r = 0x800; r < 0x805; ++r) {
			g.Roll(r, *cat, "Silhouette_Slim", 1234.0F);
			d.Seen(See(r, "Somebody"));
		}
		(void)d.RequestPreset(0x810, true, 1, "Curvy", SH::Source::kAPI, why);
		const auto lane = d.NextOrder();
		Check(d.Peek(lane) && d.Peek(lane)->ref == 0x810, "the player's request is served before background probes");
		RunOrder(d, lane, g);
		(void)Drain(d, g);
	}

	// ------------------------------------------------------------------ the director: ORefit

	void TestRefit()
	{
		SH::Director d;
		FakeGame     g;
		const auto   cat = Cat(BaseCatalog());
		d.SetCatalog(cat);

		// Dressed with a body: floors under the keyword, her own layer untouched, the clothed shape her
		// body raised to the floors -- in sync by construction (S-40).
		g.Roll(0x100, *cat, "Silhouette_Slim", 1234.0F);
		g.actors[0x100].unkeyed["BreastsTogether"] = 0.1F;
		const auto naked = g.actors[0x100].unkeyed;
		d.Seen(See(0x100, "Somebody", true));
		(void)Drain(d, g);
		auto& a = g.actors[0x100];
		Check(a.unkeyed == naked, "the refit never touches her own layer");
		Check(a.Effective("BreastsTogether") == 0.3F && a.Effective("PushUp") == 0.2F && a.Effective("NipBGone") == 0.0F,
			"dressed lightly: breasts together and pushed up, nipples as they are");
		Check(a.refit.contains("Silhouette_Refit") && d.RefitApplied(0x100), "the refit marker says a refit is on");
		auto ev = Events(d);
		Check(Has(ev, SH::EventKind::kORefitChanged) && std::ranges::find_if(ev, [](auto& e) { return e.kind == SH::EventKind::kORefitChanged; })->flag,
			"OnORefitChanged(applied)");

		// Heavy clothes flatten the nipples; back to light, they come back.
		d.Dressed(See(0x100, "Somebody", true, true), false);
		(void)Drain(d, g);
		Check(a.Effective("NipBGone") == 1.0F, "under heavy clothes, nipples flat (S-42)");
		d.Dressed(See(0x100, "Somebody", true, false), false);
		(void)Drain(d, g);
		Check(a.Effective("NipBGone") == 0.0F && a.Effective("BreastsTogether") == 0.3F, "under light clothes again, nipples back");

		// A body that grows above the floor shows through: dressed and undressed in sync.
		g.actors[0x100].unkeyed["BreastsTogether"] = 0.7F;
		Check(a.Effective("BreastsTogether") == 0.7F, "a body above the floor keeps its own value while dressed");
		g.actors[0x100].unkeyed["BreastsTogether"] = 0.1F;

		// Undressing takes the keyword layer off: exactly her body.
		d.Dressed(See(0x100, "Somebody", false), true);
		ev = Events(d);
		Check(Has(ev, SH::EventKind::kRemovingClothes) && Has(ev, SH::EventKind::kNaked), "OnActorRemovingClothes and OnActorNaked");
		(void)Drain(d, g);
		Check(a.refit.empty() && a.unkeyed == naked && a.Effective("BreastsTogether") == 0.1F, "naked: exactly her body, nothing of the refit left");

		// A preset's own refit, and an outfit's own set outranking both.
		g.Roll(0x200, *cat, "Silhouette_Curvy", 1234.0F);
		d.Seen(See(0x200, "Somebody", true));
		(void)Drain(d, g);
		Check(g.actors[0x200].Effective("Breasts") == 0.95F && !g.actors[0x200].refit.contains("BreastsTogether"), "Curvy-Refit, not the built-in set");
		d.Dressed(See(0x200, "Somebody", true, false, "Jumpsuit-Refit"), false);
		(void)Drain(d, g);
		Check(g.actors[0x200].Effective("BreastsTogether") == 0.6F && !g.actors[0x200].refit.contains("Breasts"), "another outfit's set replaces the refit layer");

		// Who is never refit (S-41).
		const auto refitOf = [&](std::uint32_t ref) { return !g.actors[ref].refit.empty(); };
		g.Roll(0x300, *cat, "Silhouette_Slim", 1234.0F);
		d.Seen(See(0x300, "Mama Murphy", true));
		(void)Drain(d, g);
		Check(!refitOf(0x300), "a name-blacklisted woman stays bare, dressed or not");
		auto formBlack = See(0x301, "Somebody", true);
		formBlack.facts.bases = { { "Fallout4.esm", 2000 } };
		d.Seen(formBlack);
		(void)Drain(d, g);
		Check(!refitOf(0x301), "a woman BodyGen keeps bare by form id is not refit");
		g.actors[0x302].other["VaginaSize"] = 0.4F;  // only another mod's keyed morph
		d.Seen(See(0x302, "Somebody", true));
		(void)Drain(d, g);
		Check(!refitOf(0x302), "a woman with only other mods' morphs has no body: not refit, the regeneration window can still roll her");
		d.Seen(See(0x303, "Somebody", true));
		(void)Drain(d, g);
		Check(!refitOf(0x303) && g.actors[0x303].listed.empty(), "a woman with nothing stored gets nothing stored: BodyGen can still roll her");
		std::string why;
		g.Roll(0x304, *cat, "Silhouette_Slim", 1234.0F);
		d.Seen(See(0x304, "Somebody", true));
		(void)Drain(d, g);
		Check(refitOf(0x304), "(set-up) refit on");
		Check(d.RequestReset(0x304, true, 0x00012345, why), "reset accepted");
		(void)Drain(d, g);
		d.Dressed(See(0x304, "Somebody", true), false);
		(void)Drain(d, g);
		Check(g.actors[0x304].unkeyed.empty() && g.actors[0x304].refit.empty(), "reset while dressed: bare, no refit, nothing to keep BodyGen away");

		// A custom follower: no Silhouette marker, a body of her own. Refit (owner, S-41).
		g.actors[0x305].unkeyed = { { "Breasts", 0.6F }, { "Waist", 0.2F } };
		g.actors[0x305].listed = { "Breasts", "Waist" };
		d.Seen(See(0x305, "Heather", true));
		(void)Drain(d, g);
		Check(refitOf(0x305) && g.actors[0x305].Effective("BreastsTogether") == 0.3F, "a custom follower with her own body is refit");

		// A new body while dressed: the refit stays, and the clothed shape follows the new body.
		g.Roll(0x306, *cat, "Silhouette_Slim", 1234.0F);
		d.Seen(See(0x306, "Somebody", true));
		(void)Drain(d, g);
		Check(d.RequestPreset(0x306, true, 0x00012345, "Curvy", SH::Source::kPicker, why), "picked");
		(void)Drain(d, g);
		Check(g.actors[0x306].unkeyed.contains("Silhouette_Curvy") && g.actors[0x306].Effective("Breasts") == 0.95F,
			"a new body arrives under the refit it should have (Curvy-Refit)");

		// Men: no set, no refit.
		auto man = See(0x500, "Somebody", true);
		man.facts.female = false;
		g.Roll(0x500, *cat, "Silhouette_BT_Average", 1234.0F);
		d.Seen(man);
		(void)Drain(d, g);
		Check(!refitOf(0x500), "no male set: a clothed man is left as he is");

		// Switched off: everyone refit comes off at once; on: refit again.
		d.Configure({ .orefit = false });
		(void)Drain(d, g);
		Check(!refitOf(0x200) && !refitOf(0x305) && !refitOf(0x306), "ORefit off: every refit comes off");
		d.Configure({ .orefit = true });
		(void)Drain(d, g);
		Check(refitOf(0x200) && refitOf(0x305), "ORefit on: refit again");

		// A save that cuts a refit short: the pending marker tells the next session.
		SH::Director e;
		FakeGame     h;
		e.SetCatalog(cat);
		h.Roll(0x100, *cat, "Silhouette_Slim", 1234.0F);
		const auto bare = h.actors[0x100].unkeyed;
		e.Seen(See(0x100, "Somebody", true));
		const auto probe = e.NextOrder();
		RunOrder(e, probe, h);
		const auto refitOrder = e.NextOrder();
		Check(e.Peek(refitOrder) && e.Peek(refitOrder)->kind == SH::OrderKind::kRefit, "(set-up) the refit order");
		RunOrder(e, refitOrder, h, 2);  // the pending marker and one floor, then the save
		Reload(e, h);
		e.Seen(See(0x100, "Somebody", false));  // she undressed in the loaded save
		(void)Drain(e, h);
		Check(h.actors[0x100].refit.empty() && h.actors[0x100].unkeyed == bare, "an unfinished refit found naked after a load comes off entirely");
		e.Seen(See(0x100, "Somebody", true));
		(void)Drain(e, h);
		RunOrder(e, e.NextOrder(), h);
		Reload(e, h);
		h.actors[0x100].refit.erase("PushUp");  // a refit cut short after its last floor... but before the final marker
		h.actors[0x100].refit["Silhouette_Refit"] = 0.25F;
		e.Seen(See(0x100, "Somebody", true));
		(void)Drain(e, h);
		Check(h.actors[0x100].Effective("PushUp") == 0.2F && h.actors[0x100].refit.at("Silhouette_Refit") >= 1.0F,
			"an unfinished refit found dressed is written whole");

		// Silhouette.esp removed: LooksMenu drops the keyword's values at load. Put back when dressed.
		Reload(e, h);
		h.actors[0x100].refit.clear();
		e.Seen(See(0x100, "Somebody", true));
		(void)Drain(e, h);
		Check(h.actors[0x100].Effective("BreastsTogether") == 0.3F, "a refit LooksMenu dropped is put back on the next sighting");
	}

	// ------------------------------------------------------------------ the director: touch-up

	void TestTouchUp()
	{
		SH::Director d;
		FakeGame     g;
		const auto   cat = Cat(BaseCatalog());
		d.SetCatalog(cat);

		// A man an older build shaped: the shaft value goes (S-29), the ball size he lacks comes (S-44).
		auto& m = g.actors[0x100];
		m.unkeyed = { { "BTChest", 0.4F }, { "Penis Width", 1.0F }, { "Silhouette_BT_Old", 99.0F } };
		m.listed = { "BTChest", "Penis Width", "Silhouette_BT_Old" };
		auto man = See(0x100, "Somebody");
		man.facts.female = false;
		d.Seen(man);
		(void)Drain(d, g);
		Check(!m.unkeyed.contains("Penis Width") && m.unkeyed.at("BTChest") == 0.4F && m.unkeyed.contains("BTBallSize") &&
				  m.unkeyed.at("BTBallSize") == SH::Draw(0x100, "BTBallSize", 0.1F, 0.4F),
			"an old body: shaft removed, balls rolled, the rest untouched");
		const auto after = m.unkeyed;
		Reload(d, g);
		d.Seen(man);
		Check(Drain(d, g) == 1 && m.unkeyed == after, "touched once: the next session only probes");

		// A woman from before the variety existed gets it; what she has stays.
		auto& w = g.actors[0x200];
		w.unkeyed = { { "Breasts", 0.8F }, { "Butt", 0.5F }, { "NippleSize", 0.2F }, { "Silhouette_Curvy", 99.0F } };
		w.listed = { "Breasts", "Butt", "NippleSize", "Silhouette_Curvy" };
		d.Seen(See(0x200, "Somebody"));
		(void)Drain(d, g);
		Check(w.unkeyed.at("NippleSize") == 0.2F && w.unkeyed.contains("VaginaSize") && w.unkeyed.at("Breasts") == 0.8F,
			"top-up: the missing genital range drawn, her nipples kept");

		// Touched once per body: a value the player took off afterwards (LooksMenu's own sliders) stays off.
		w.unkeyed.erase("VaginaSize");
		Reload(d, g);
		d.Seen(See(0x200, "Somebody"));
		(void)Drain(d, g);
		Check(!w.unkeyed.contains("VaginaSize"), "a topped-up value the player removed later is not put back");

		// Variety switched off: no top-up of that group.
		auto& x = g.actors[0x300];
		x.unkeyed = { { "Breasts", 0.8F }, { "Silhouette_Curvy", 99.0F } };
		x.listed = { "Breasts", "Silhouette_Curvy" };
		d.Configure({ .orefit = true, .variety = { .nipples = false, .genitals = true } });
		d.Seen(See(0x300, "Somebody"));
		(void)Drain(d, g);
		Check(!x.unkeyed.contains("NippleSize") && x.unkeyed.contains("VaginaSize"), "the variety switches apply to the top-up");
	}

	// ------------------------------------------------------------------ the director: the picker

	void TestPicker()
	{
		SH::Director d;
		FakeGame     g;
		const auto   cat = Cat(BaseCatalog());
		d.SetCatalog(cat);
		g.Roll(0x100, *cat, "Silhouette_Slim", 1234.0F);
		const auto before = g.actors[0x100].unkeyed;
		d.Seen(See(0x100, "Cait"));
		(void)Drain(d, g);
		(void)Events(d);

		auto msg = d.PickerStart(0x100, true, 0x00012345, "Cait");
		Check(msg.find("Cait") != std::string::npos, "Pick names who was picked");
		Check(d.PickerStep(1).find("Still reading") != std::string::npos, "Next waits for the snapshot");
		(void)Drain(d, g);
		Check(d.PickerReady(), "the snapshot is in");
		msg = d.PickerStep(1);
		Check(msg == "Cait: Athletic (3/3)", std::format("Next starts from the preset she has (Slim is 2/3): {}", msg));
		(void)Drain(d, g);
		Check(g.actors[0x100].unkeyed.contains("Silhouette_Athletic"), "the preview is on her");
		Check(!d.RecordOf(0x100) || d.RecordOf(0x100)->source != SH::Source::kPicker, "a preview is not a choice");
		msg = d.PickerCancel();
		(void)Drain(d, g);
		Check(g.actors[0x100].unkeyed == before, std::format("Cancel puts back exactly what she had ({})", msg));
		Check(d.PickerTarget() == 0, "and ends the picking");

		(void)d.PickerStart(0x100, true, 0x00012345, "Cait");
		(void)Drain(d, g);
		(void)d.PickerStep(-1);
		(void)Drain(d, g);
		msg = d.PickerKeep();
		Check(msg == "Cait keeps Curvy.", msg);
		const auto rec = d.RecordOf(0x100);
		Check(rec && rec->source == SH::Source::kPicker && rec->preset == "Curvy", "Keep records a picker choice");
		Check(Has(Events(d), SH::EventKind::kGenerated, "Curvy"), "Keep announces the body");

		// Picking refused while a body is on its way; a request made while picking ends it.
		std::string why;
		g.Roll(0x200, *cat, "Silhouette_Slim", 1234.0F);
		(void)d.RequestPreset(0x200, true, 0x00012345, "Athletic", SH::Source::kAPI, why);
		Check(d.PickerStart(0x200, true, 0x00012345, "Curie").find("still changing") != std::string::npos, "no picking while a body is on its way");
		(void)Drain(d, g);
		(void)d.PickerStart(0x200, true, 0x00012345, "Curie");
		(void)Drain(d, g);
		(void)d.RequestPreset(0x200, true, 0x00012345, "Curvy", SH::Source::kAPI, why);
		Check(d.PickerTarget() == 0, "a decision made elsewhere ends the picking");
		(void)Drain(d, g);
		Check(g.actors[0x200].unkeyed.contains("Silhouette_Curvy"), "and is what she gets");

		// A save in the middle of picking loads as a Cancel (S-47).
		g.Roll(0x300, *cat, "Silhouette_Slim", 1234.0F);
		const auto hers = g.actors[0x300].unkeyed;
		d.Seen(See(0x300, "Cait"));
		(void)Drain(d, g);
		(void)d.PickerStart(0x300, true, 0x00012345, "Cait");
		(void)Drain(d, g);
		(void)d.PickerStep(1);
		(void)Drain(d, g);
		Check(!(g.actors[0x300].unkeyed == hers), "(set-up) a preview on her");
		Reload(d, g);
		d.Seen(See(0x300, "Cait"));
		(void)Drain(d, g);
		Check(g.actors[0x300].unkeyed == hers, "a picking saved mid-preview loads as a Cancel");
		Reload(d, g);
		d.Seen(See(0x300, "Cait"));
		(void)Drain(d, g);
		Check(g.actors[0x300].unkeyed == hers, "and only once");

		// Picking someone else puts the first back; a failed snapshot ends the picking.
		(void)d.PickerStart(0x100, true, 0x00012345, "Cait");
		(void)Drain(d, g);
		(void)d.PickerStep(1);
		(void)Drain(d, g);
		msg = d.PickerStart(0x300, true, 0x00012345, "Curie");
		Check(msg.starts_with("Cait is back to"), msg);
		std::uint32_t snap = 0;
		while (const auto id = d.NextOrder()) {
			if (d.Peek(id)->kind == SH::OrderKind::kSnapshot) {
				snap = id;
				break;
			}
			RunOrder(d, id, g);
		}
		Check(snap != 0, "the new snapshot is asked for");
		d.Done(snap, false);
		(void)Drain(d, g);
		Check(d.PickerTarget() == 0, "a snapshot that failed ends the picking instead of leaving it waiting");
		Check(g.actors[0x100].unkeyed.contains("Silhouette_Curvy"), "Cait is back to her kept body");
	}
}

// The generated files themselves, read by the plugin's own parser: what the game would refuse at load
// is refused here, before anything is deployed (L4F1). a_root is a Data folder or a mod folder.
int CheckData(const std::filesystem::path& a_root)
{
	const auto folder = a_root / "F4SE/Plugins/Silhouette";
	std::string error;
	std::ifstream in(folder / "catalog.json", std::ios::binary);
	if (!in) {
		std::cout << "CHECK FAIL: no " << (folder / "catalog.json").string() << "\n";
		return 1;
	}
	std::optional<SH::Catalog> catalog;
	try {
		catalog = SH::ParseCatalog(nlohmann::json::parse(in), error);
	} catch (const std::exception& e) {
		error = e.what();
	}
	if (!catalog) {
		std::cout << "CHECK FAIL: the plugin would refuse catalog.json: " << error << "\n";
		return 1;
	}
	int failed = 0;
	std::size_t manifests = 0;
	bool own = false;
	std::error_code ec;
	for (const auto& entry : std::filesystem::directory_iterator(folder / "manifests", ec)) {
		if (entry.path().extension() != ".json") {
			continue;
		}
		std::ifstream m(entry.path(), std::ios::binary);
		std::optional<std::pair<std::uint32_t, std::unordered_map<std::string, SH::ManifestEntry>>> parsed;
		try {
			parsed = SH::ParseManifest(nlohmann::json::parse(m), error);
		} catch (const std::exception& e) {
			error = e.what();
		}
		if (!parsed) {
			std::cout << "CHECK FAIL: manifest " << entry.path().filename().string() << ": " << error << "\n";
			++failed;
			continue;
		}
		own = own || parsed->first == catalog->stamp;
		++manifests;
	}
	if (!own) {
		std::cout << "CHECK FAIL: no manifest for this build's stamp " << catalog->stamp << "\n";
		++failed;
	}
	for (const auto* file : { "Silhouette_templates.ini", "Silhouette_morphs.ini" }) {
		std::ifstream h(a_root / "F4SE/Plugins/F4EE/BodyGen/Loose" / file);
		const auto header = h ? SH::ParseFilesHeader(h) : std::nullopt;
		if (!header) {
			std::cout << "CHECK FAIL: " << file << " names no build in its header\n";
			++failed;
		} else if (header->build != catalog->build || header->stamp != catalog->stamp || header->rules != catalog->rulesHash) {
			std::cout << std::format("CHECK FAIL: {} is build {} stamp {} rules {}, the catalog build {} stamp {} rules {}\n", file,
				header->build, header->stamp, header->rules, catalog->build, catalog->stamp, catalog->rulesHash);
			++failed;
		}
	}
	if (failed == 0) {
		std::cout << std::format("CHECK OK: build {}, stamp {}, rules {}: {} presets, {} refit set(s), {} manifest(s), both BodyGen headers agree\n",
			catalog->build, catalog->stamp, catalog->rulesHash, catalog->presets.size(), catalog->refitSets.size(), manifests);
	}
	return failed;
}

int main(int argc, char** argv)
{
	if (argc == 3 && std::string_view{ argv[1] } == "--check") {
		return CheckData(argv[2]);
	}
	TestCatalog();
	TestRules();
	TestPlan();
	TestRegistry();
	TestBodies();
	TestRefit();
	TestTouchUp();
	TestPicker();
	std::cout << g_passed << " passed, " << g_failed << " failed\n";
	return g_failed;
}

// Offline tests for everything in the plugin with no game in it: the catalog reader, OBody's rule
// priority as the runtime applies it (S-23), the ORefit arithmetic (S-20), the bodies the plugin
// writes (variety, S-17/S-21), the co-save bytes (S-25), and the whole director -- driven through a
// fake bridge that does to a fake LooksMenu layer exactly what Silhouette:Bridge does to the real one,
// so each test checks the body an actor ends up with, not just the orders on the way.
//
//     build\Release\SilhouetteTests.exe        -> "N passed, 0 failed", exit code 0
//
// Each check prints what it expected when it fails, and the exit code is the failure count.

#include "PCH.h"

#include "Catalog.h"
#include "Director.h"
#include "Plan.h"
#include "Registry.h"
#include "Rules.h"

#include <iostream>

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
		return nlohmann::json::parse(R"({
			"schema": 1, "build": "abc123", "stamp": 1234, "mode": "absolute",
			"presets": [
				{"name": "Curvy", "sex": "female", "marker": "Silhouette_Curvy", "values": {"Breasts": 0.8, "Butt": 0.5},
				 "random": true, "menu": true, "zeroed": false, "fit": "full", "family": "CBBE"},
				{"name": "Slim", "sex": "female", "marker": "Silhouette_Slim", "values": {"Breasts": 0.2},
				 "random": true, "menu": true, "zeroed": false, "fit": "full", "family": "CBBE"},
				{"name": "Athletic", "sex": "female", "marker": "Silhouette_Athletic", "values": {"Waist": -0.3},
				 "random": true, "menu": true, "zeroed": false, "fit": "full", "family": "CBBE"},
				{"name": "BT - Average", "sex": "male", "marker": "Silhouette_BT_Average", "values": {"BTChest": 0.4},
				 "random": true, "menu": true, "zeroed": false, "fit": "full", "family": "BodyTalk"}
			],
			"player": {"female": "Slim", "male": "BT - Average"},
			"states": {"female": ["VaginaPenetrate"], "male": ["Erection"]},
			"variety": {
				"female": [{"morph": "NippleSize", "low": 0.0, "high": 0.5, "group": "nipples"},
				           {"morph": "VaginaSize", "low": -0.3, "high": 0.3, "group": "genitals"}],
				"male": [{"morph": "BTBallSize", "low": 0.1, "high": 0.4, "group": "genitals"}]
			},
			"blacklistMarker": "Silhouette_Blacklisted",
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
				"enabled": true, "slots": [33, 36, 41],
				"blacklist": [], "blacklistNames": ["Sheer Dress"], "blacklistPlugins": [],
				"force": [], "forceNames": [],
				"outfits": [{"name": "Vault 111 Jumpsuit", "sex": "female", "set": "Jumpsuit-Refit"}],
				"sets": [
					{"name": "builtin:female", "sex": "female", "entries": [
						{"morph": "BreastsTogether", "op": "max", "value": 0.3},
						{"morph": "Breasts", "op": "add", "value": -0.05},
						{"morph": "NipBGone", "op": "set", "value": 1.0},
						{"morph": "BreastGravity2", "op": "min", "value": 0.2}]},
					{"name": "Curvy-Refit", "sex": "female", "entries": [{"morph": "Breasts", "op": "set", "value": 0.6}]},
					{"name": "Jumpsuit-Refit", "sex": "female", "entries": [{"morph": "Breasts", "op": "min", "value": 0.4}]}
				]
			}
		})");
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

	void TestCatalog()
	{
		std::string error;
		auto c = SH::ParseCatalog(BaseCatalog(), error);
		Check(c.has_value(), std::format("the base catalog parses ({})", error));
		if (!c) {
			return;
		}
		Check(c->presets.size() == 4, "four presets");
		Check(c->Find("Curvy", true) != nullptr && c->Find("Curvy", false) == nullptr, "presets are per sex");
		Check(c->FindByMarker("Silhouette_Slim") && c->FindByMarker("Silhouette_Slim")->name == "Slim", "marker -> preset");
		Check(c->playerDefault[1] == "Slim" && c->playerDefault[0] == "BT - Average", "player defaults");

		// what a broken file does: refused whole, with the reason
		auto broken = BaseCatalog();
		broken["rules"]["npcName"][0]["presets"] = { "Nobody" };
		Check(!SH::ParseCatalog(broken, error) && error.find("Nobody") != std::string::npos,
			"a rule naming a preset the catalog lacks refuses the file");

		broken = BaseCatalog();
		broken["rules"]["faction"][0]["id"] = 0x01003000;
		Check(!SH::ParseCatalog(broken, error) && error.find("load-order") != std::string::npos,
			"a form id that carries a load-order byte is refused");

		broken = BaseCatalog();
		broken["presets"][0]["sex"] = "Female";
		Check(!SH::ParseCatalog(broken, error), "sex is exactly \"female\" or \"male\"");

		broken = BaseCatalog();
		broken["schema"] = 2;
		Check(!SH::ParseCatalog(broken, error), "another schema is refused, not guessed at");

		broken = BaseCatalog();
		broken["stamp"] = 1 << 24;
		Check(!SH::ParseCatalog(broken, error), "a stamp that a float32 cannot hold exactly is refused");

		// manifests: a marker of an older build still names its preset
		const auto manifest = nlohmann::json::parse(R"json({"stamp": 99, "templates": {
			"Silhouette_Old": {"preset": "Old Preset (v1)", "gender": "female", "values": {"Breasts": 1.0}}}})json");
		auto m = SH::ParseManifest(manifest, error);
		Check(m.has_value(), "a manifest parses");
		if (m) {
			c->AddManifest(m->first, m->second);
			Check(c->PresetForMarker("Silhouette_Old", 99) == "Old Preset (v1)", "an older build's marker names its preset");
			Check(!c->PresetForMarker("Silhouette_Old", 1234).has_value(), "a marker is read against ITS stamp only");
			Check(c->PresetForMarker("Silhouette_Curvy", 1234) == "Curvy", "the current build's markers fall back to the catalog");
		}
	}

	void TestRules()
	{
		std::string error;
		const auto c = SH::ParseCatalog(BaseCatalog(), error);
		if (!c) {
			Check(false, "catalog for the rules");
			return;
		}

		auto a = Npc();
		Check(SH::Decide(*c, a).tier == SH::Tier::kNone, "a plain NPC keeps BodyGen's roll");

		a = Npc();
		a.baseName = "piper";
		auto v = SH::Decide(*c, a);
		Check(v.tier == SH::Tier::kName && v.preset == "Curvy", "npc by name, case-insensitive");

		a = Npc();
		a.baseName = "Piper";
		a.female = false;
		Check(SH::Decide(*c, a).tier == SH::Tier::kNone, "a name rule is for its own sex only");

		a = Npc();
		a.baseName = "Mama Murphy";
		Check(SH::Decide(*c, a).tier == SH::Tier::kNameBlacklist, "name blacklist");

		a = Npc();
		a.baseName = "Mama Murphy";
		a.bases = { { "Fallout4.esm", 2000 } };
		Check(SH::Decide(*c, a).tier == SH::Tier::kNone, "form id blacklist is BodyGen's and outranks everything");

		a = Npc();
		a.baseName = "Piper";
		a.bases = { { "Fallout4.esm", 0x12345 }, { "fallout4.ESM", 1000 } };
		Check(SH::Decide(*c, a).tier == SH::Tier::kNone, "a per-NPC form id preset (BodyGen's) outranks a name rule; plugin names compare case-insensitively");

		a = Npc();
		a.factions = { { "Fallout4.esm", 3000 } };
		v = SH::Decide(*c, a);
		Check(v.tier == SH::Tier::kFaction && v.preset == "Athletic", "faction rule");

		a = Npc();
		a.factions = { { "Fallout4.esm", 3000 } };
		a.baseName = "Piper";
		Check(SH::Decide(*c, a).preset == "Curvy", "a name rule outranks a faction rule");

		a = Npc();
		a.factions = { { "Fallout4.esm", 3000 } };
		a.originPlugin = "Blocked.esp";
		Check(SH::Decide(*c, a).tier == SH::Tier::kNone, "a plugin blacklist outranks a faction rule (OBody's order)");

		a = Npc();
		a.factions = { { "Fallout4.esm", 3000 } };
		a.race = "GhoulRace";
		Check(SH::Decide(*c, a).tier == SH::Tier::kNone, "an undistributed race is never ours");

		a = Npc();
		a.factions = { { "Fallout4.esm", 3001 } };
		const auto first = SH::Decide(*c, a).preset;
		bool same = true;
		for (int i = 0; i < 20; ++i) {
			same &= SH::Decide(*c, a).preset == first;
		}
		Check(same, "a rule with several presets draws the same one for the same person");

		// and different people are not all drawn the same
		std::set<std::string> drawn;
		for (std::uint32_t id = 0xFF000800; id < 0xFF000840; ++id) {
			a.seed = id;
			drawn.insert(SH::Decide(*c, a).preset);
		}
		Check(drawn.size() == 2, "a rule with several presets spreads them across people");
	}

	void TestRefit()
	{
		std::string error;
		const auto c = SH::ParseCatalog(BaseCatalog(), error);
		if (!c) {
			Check(false, "catalog for refit");
			return;
		}
		const auto* builtin = c->RefitFor("Slim", true, "");
		Check(builtin && builtin->name == "builtin:female", "no preset refit -> the built-in set");
		const auto* own = c->RefitFor("Curvy", true, "");
		Check(own && own->name == "Curvy-Refit", "<Preset>-Refit wins over the built-in set");

		std::unordered_map<std::string, float> now{ { "BreastsTogether", 0.1F }, { "Breasts", 0.8F }, { "BreastGravity2", 0.5F } };
		const auto out = SH::ApplyRefit(*builtin, now);
		auto get = [&](std::string_view m) {
			const auto it = std::ranges::find_if(out, [&](const auto& p) { return p.first == m; });
			return it == out.end() ? -99.0F : it->second;
		};
		Check(std::abs(get("BreastsTogether") - 0.3F) < 1e-6, "max raises a lower value to the floor");
		Check(std::abs(get("Breasts") - 0.75F) < 1e-6, "add works from the naked value");
		Check(std::abs(get("NipBGone") - 1.0F) < 1e-6, "set, and a morph the NPC lacks counts from 0");
		Check(std::abs(get("BreastGravity2") - 0.2F) < 1e-6, "min caps a higher value");
		Check(out.size() == 4, "exactly the set's morphs, nothing else");

		now["BreastsTogether"] = 0.9F;
		Check(std::abs(get("BreastsTogether") - 0.3F) < 1e-6 && std::abs(SH::ApplyRefit(*builtin, now)[0].second - 0.9F) < 1e-6,
			"max leaves a higher value alone");
	}

	// ------------------------------------------------------------------ plans

	void TestPlan()
	{
		std::string error;
		const auto  c = SH::ParseCatalog(BaseCatalog(), error);
		if (!c) {
			Check(false, "catalog for plans");
			return;
		}
		const auto* curvy = c->Find("Curvy", true);
		const auto  a = SH::BodyFor(*c, *curvy, 0xFF000801, {});
		const auto  b = SH::BodyFor(*c, *curvy, 0xFF000801, {});
		Check(a == b, "the same person gets the same body every time");
		auto value = [](const SH::Morphs& m, std::string_view k) {
			const auto it = std::ranges::find_if(m, [&](const auto& p) { return p.first == k; });
			return it == m.end() ? std::optional<float>{} : std::optional<float>{ it->second };
		};
		Check(value(a, "Breasts") == 0.8F && value(a, "Butt") == 0.5F, "the preset's own values");
		Check(a.back().first == "Silhouette_Curvy" && a.back().second == 1234.0F, "the marker, last, holding the stamp");
		const auto nip = value(a, "NippleSize");
		const auto vag = value(a, "VaginaSize");
		Check((!nip || (*nip > 0.0F && *nip < 0.5F)) && (!vag || (*vag >= -0.3F && *vag <= 0.3F)), "variety drawn inside its range");
		Check(!value(a, "BTBallSize"), "a man's range never lands on a woman");

		// spread: over many people the draws cover the range
		float lo = 1.0F;
		float hi = -1.0F;
		for (std::uint32_t id = 0xFF000800; id < 0xFF000900; ++id) {
			const auto v = SH::Draw(id, "VaginaSize", -0.3F, 0.3F);
			lo = std::min(lo, v);
			hi = std::max(hi, v);
		}
		Check(lo < -0.25F && hi > 0.25F, "draws spread across the whole range");

		const auto off = SH::BodyFor(*c, *curvy, 0xFF000801, { .nipples = false, .genitals = true });
		Check(!value(off, "NippleSize"), "SetNippleRand(false): no nipple range, and Curvy names none of its own");

		// runtime states never land in a body, even when a preset carries one
		auto withState = *c;
		for (auto& p : withState.presets) {
			if (p.name == "Curvy") {
				p.values.emplace_back("VaginaPenetrate", 1.0F);
			}
		}
		const auto s = SH::BodyFor(withState, *withState.Find("Curvy", true), 1, {});
		Check(!value(s, "VaginaPenetrate"), "a runtime state (S-16) is never written");

		// Unrefit: the clothed values of the refit morphs go back to their naked values
		const SH::Morphs layer{ { "Breasts", 0.6F }, { "Butt", 0.5F }, { "NipBGone", 1.0F } };
		const SH::Morphs snap{ { "Breasts", 0.8F }, { "NipBGone", 0.0F }, { "BreastsTogether", 0.2F } };
		const auto       naked = SH::Unrefit(layer, snap);
		Check(value(naked, "Breasts") == 0.8F && !value(naked, "NipBGone") && value(naked, "BreastsTogether") == 0.2F && value(naked, "Butt") == 0.5F,
			"Unrefit puts back the naked values, and drops what was 0 naked");

		Check(SH::BodyHash("Silhouette_Curvy", 1234) != SH::BodyHash("Silhouette_Curvy", 1235) && SH::BodyHash("x", 0) != 0,
			"the body hash tells builds apart and is never 0");
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
		a.refitApplied = true;
		a.refitSet = "builtin:female";
		a.snapshot = { { "Breasts", 0.8F }, { "NipBGone", 0.0F } };
		r.Get(0xFF000900).announced = 5;
		(void)r.Get(0x00000001);  // empty: never written

		const auto   bytes = r.Serialize([](std::uint32_t) { return true; });
		SH::Registry back;
		std::string  error;
		Check(back.Deserialize(bytes, SH::Registry::kVersion, [](std::uint32_t id) { return id; }, error), std::format("records read back ({})", error));
		const auto* b = back.Find(0x0001A4F2);
		Check(b && b->base == 0x0002F1E5 && b->source == SH::Source::kPicker && b->preset == "Curvy" && b->stamp == 1234 &&
				  b->announced == 77 && b->refitApplied && b->refitSet == "builtin:female" && b->snapshot == a.snapshot,
			"a record survives the co-save exactly");
		Check(back.Size() == 2, "an empty record is not written");

		// load order changed: ids are resolved; a form whose plugin is gone takes its record with it
		SH::Registry moved;
		Check(moved.Deserialize(bytes, SH::Registry::kVersion,
				  [](std::uint32_t id) -> std::uint32_t { return id == 0xFF000900 ? 0 : (id & 0x00FFFFFF) | 0x05000000; }, error),
			"records read back with a new load order");
		Check(moved.Size() == 1 && moved.Find(0x0501A4F2) && moved.Find(0x0501A4F2)->base == 0x0502F1E5, "ids resolved, the gone one dropped");

		// cut short, or another version: nothing half-loaded
		SH::Registry cut;
		cut.Get(42).announced = 1;
		std::vector<std::byte> shorter(bytes.begin(), bytes.end() - 3);
		Check(!cut.Deserialize(shorter, SH::Registry::kVersion, nullptr, error) && cut.Find(42), "cut-short bytes are refused, nothing replaced");
		Check(!cut.Deserialize(bytes, 99, nullptr, error), "another version is refused");

		// a reference that no longer exists is not written
		const auto   kept = r.Serialize([](std::uint32_t id) { return id != 0xFF000900; });
		SH::Registry k;
		Check(k.Deserialize(kept, SH::Registry::kVersion, nullptr, error) && k.Size() == 1, "a deleted reference's record is not saved");
	}

	// ------------------------------------------------------------------ the director, end to end

	// An actor's unkeyed LooksMenu layer, as the fake bridge sees it.
	using Layer = std::map<std::string, float>;

	struct FakeGame
	{
		std::unordered_map<std::uint32_t, Layer> layers;
		std::string                              rollsTo = "Silhouette_Slim";  // what BodyGen's regenerate gives
		float                                    stamp = 1234.0F;
		int                                      orders = 0;
	};

	// Exactly what Silhouette:Bridge does with one order.
	void RunOrder(SH::Director& d, std::uint32_t a_id, FakeGame& g)
	{
		const auto o = d.Peek(a_id);
		if (!o) {
			return;
		}
		++g.orders;
		auto& layer = g.layers[o->ref];
		if (o->regenerate) {
			layer = { { g.rollsTo, g.stamp } };  // BodyGen rolled; keyed layers are not modelled here
		}
		if (o->probe) {
			for (const auto& [name, v] : layer) {
				if (SH::Catalog::IsMarker(name)) {
					d.NoteMarker(a_id, name, v);
				}
			}
		}
		if (o->readAll) {
			for (const auto& [name, v] : layer) {
				d.NoteLayer(a_id, name, v);
			}
		}
		const auto n = d.ReadCount(a_id);
		for (std::int32_t i = 0; i < n; ++i) {
			const auto m = d.ReadMorph(a_id, i);
			const auto it = layer.find(m);
			d.NoteRead(a_id, i, it == layer.end() ? 0.0F : it->second);
		}
		if (!d.Prepare(a_id)) {
			d.Done(a_id, false);
			return;
		}
		if (d.Clears(a_id)) {
			layer.clear();
		}
		const auto w = d.WriteCount(a_id);
		for (std::int32_t i = 0; i < w; ++i) {
			const auto m = d.WriteMorph(a_id, i);
			const auto v = d.WriteValue(a_id, i);
			if (v == 0.0F) {
				layer.erase(m);  // LooksMenu: SetMorph(0) erases the entry
			} else {
				layer[m] = v;
			}
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

	SH::Sighting See(std::uint32_t a_ref, std::string a_name, bool a_clothed = false, std::string a_outfit = {})
	{
		SH::Sighting s;
		s.ref = a_ref;
		s.base = 0x00012345;
		s.facts = Npc();
		s.facts.baseName = std::move(a_name);
		s.facts.seed = a_ref;
		s.clothed = a_clothed;
		s.outfitSet = std::move(a_outfit);
		return s;
	}

	std::shared_ptr<const SH::Catalog> Cat(const nlohmann::json& a_doc)
	{
		std::string error;
		auto        c = SH::ParseCatalog(a_doc, error);
		if (!c) {
			Check(false, std::format("test catalog: {}", error));
			return nullptr;
		}
		return std::make_shared<const SH::Catalog>(std::move(*c));
	}

	void TestDirectorBodies()
	{
		SH::Director d;
		FakeGame     g;
		d.SetCatalog(Cat(BaseCatalog()));

		// A plain NPC: BodyGen already gave them Slim. One probe, one OnActorGenerated.
		g.layers[0x100] = { { "Breasts", 0.2F }, { "Silhouette_Slim", 1234.0F } };
		d.Seen(See(0x100, "Somebody"));
		Check(Drain(d, g) == 1, "a plain NPC costs one probe");
		auto ev = Events(d);
		Check(Has(ev, SH::EventKind::kGenerated, "Slim"), "OnActorGenerated names BodyGen's preset");
		Check((g.layers[0x100] == Layer{ { "Breasts", 0.2F }, { "Silhouette_Slim", 1234.0F } }), "a probe changes nothing");
		d.Seen(See(0x100, "Somebody"));
		Check(Drain(d, g) == 0, "seen again this session: nothing to do");
		d.ForgetWorld();
		d.Seen(See(0x100, "Somebody"));
		(void)Drain(d, g);
		Check(!Has(Events(d), SH::EventKind::kGenerated), "a new session probes again but announces a body only once");

		// A name rule replaces BodyGen's roll, and is recorded.
		g.layers[0x200] = { { "Breasts", 0.2F }, { "Silhouette_Slim", 1234.0F } };
		d.Seen(See(0x200, "Piper"));
		(void)Drain(d, g);
		const auto& piper = g.layers[0x200];
		Check(piper.contains("Silhouette_Curvy") && !piper.contains("Silhouette_Slim") && piper.at("Breasts") == 0.8F,
			"the name rule's preset replaced BodyGen's body, marker and all");
		ev = Events(d);
		Check(Has(ev, SH::EventKind::kGenerated, "Curvy") && Has(ev, SH::EventKind::kNaked), "OnActorGenerated, and OnActorNaked for a body given naked");
		const auto rec = d.RecordOf(0x200);
		Check(rec && rec->source == SH::Source::kNameRule && rec->preset == "Curvy" && rec->stamp == 1234, "the rule is recorded with its build");
		d.Seen(See(0x200, "Piper"));
		Check(Drain(d, g) == 0, "a rule already applied is not applied again");

		// The rule changes: applied again. The rule goes: the body stays, no longer ours.
		auto doc = BaseCatalog();
		doc["rules"]["npcName"][0]["presets"] = { "Athletic" };
		d.SetCatalog(Cat(doc));
		d.Seen(See(0x200, "Piper"));
		(void)Drain(d, g);
		Check(g.layers[0x200].contains("Silhouette_Athletic"), "a changed rule is applied again");
		doc["rules"]["npcName"] = nlohmann::json::array();
		d.SetCatalog(Cat(doc));
		d.Seen(See(0x200, "Piper"));
		(void)Drain(d, g);
		Check(g.layers[0x200].contains("Silhouette_Athletic") && d.RecordOf(0x200) && d.RecordOf(0x200)->source == SH::Source::kNone,
			"a rule taken away leaves the body, as BodyGen's");

		// A new build re-gives a picked preset with the build's values; the same build leaves it be.
		d.SetCatalog(Cat(BaseCatalog()));
		std::string why;
		Check(d.RequestPreset(0x300, true, 0x00012345, "Slim", SH::Source::kPicker, why), "a picker choice is accepted");
		(void)Drain(d, g);
		Check(g.layers[0x300].contains("Silhouette_Slim"), "the choice is applied");
		d.Seen(See(0x300, "Somebody Else"));
		Check(Drain(d, g) <= 1 && g.layers[0x300].contains("Silhouette_Slim"), "a choice outranks the rules and is not re-given in its own build");
		auto next = BaseCatalog();
		next["stamp"] = 5678;
		d.SetCatalog(Cat(next));
		d.Seen(See(0x300, "Somebody Else"));
		(void)Drain(d, g);
		Check(g.layers[0x300].contains("Silhouette_Slim") && g.layers[0x300].at("Silhouette_Slim") == 5678.0F,
			"a new build re-gives the choice, stamped with the new build");
		d.SetCatalog(Cat(BaseCatalog()));
		(void)Events(d);

		// Name blacklist: bare with the marker; lifted: BodyGen rolls them.
		g.layers[0x400] = { { "Breasts", 0.2F }, { "Silhouette_Slim", 1234.0F } };
		d.Seen(See(0x400, "Mama Murphy"));
		(void)Drain(d, g);
		Check((g.layers[0x400] == Layer{ { "Silhouette_Blacklisted", 1234.0F } }), "a name-blacklisted NPC is bare but for the blacklist marker");
		Check(!Has(Events(d), SH::EventKind::kGenerated), "no body, no OnActorGenerated");
		auto lifted = BaseCatalog();
		lifted["rules"]["blacklistedNpcNames"] = nlohmann::json::array();
		d.SetCatalog(Cat(lifted));
		g.rollsTo = "Silhouette_Athletic";
		d.Seen(See(0x400, "Mama Murphy"));
		(void)Drain(d, g);
		Check(g.layers[0x400].contains("Silhouette_Athletic") && !g.layers[0x400].contains("Silhouette_Blacklisted"), "a lifted blacklist lets BodyGen roll them");
		Check(Has(Events(d), SH::EventKind::kGenerated, "Athletic"), "and their new body is announced");
		d.SetCatalog(Cat(BaseCatalog()));

		// Not ours: the player and the dummies, and races Silhouette does not distribute to.
		auto player = See(0x14, "Piper");
		player.eligible = false;
		d.Seen(player);
		auto ghoul = See(0x500, "Piper");
		ghoul.facts.race = "GhoulRace";
		d.Seen(ghoul);
		Check(Drain(d, g) == 0, "the player, the dummies and undistributed races are left alone");

		// A created reference's id reused by someone else: their record is forgotten.
		Check(d.RequestPreset(0xFF000A00, true, 0x00011111, "Curvy", SH::Source::kPicker, why), "picked");
		(void)Drain(d, g);
		auto stranger = See(0xFF000A00, "Somebody");
		stranger.base = 0x00022222;
		d.Seen(stranger);
		(void)Drain(d, g);
		Check(!d.RecordOf(0xFF000A00) || d.RecordOf(0xFF000A00)->source != SH::Source::kPicker, "a record for a reused id is dropped");

		// Requests that cannot be kept say why.
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
		Check(d.AssignedPreset(0x700) == "Slim", "AssignedPreset answers with what is decided, before the bridge has done it");
		RunOrder(d, first, g);
		RunOrder(d, second, g);
		(void)Drain(d, g);
		Check(g.layers[0x700].contains("Silhouette_Slim"), "and the last decision is the one that lands");

		// Reset: bare; Regenerate: BodyGen's roll.
		(void)d.RequestReset(0x700, true, 1);
		(void)Drain(d, g);
		Check(g.layers[0x700].empty(), "Reset leaves no unkeyed morph at all");
		g.rollsTo = "Silhouette_Curvy";
		(void)d.RequestRegenerate(0x700, true, 1);
		(void)Drain(d, g);
		Check(g.layers[0x700].contains("Silhouette_Curvy") && Has(Events(d), SH::EventKind::kGenerated, "Curvy"), "Regenerate: BodyGen's roll, announced");
	}

	void TestDirectorRefit()
	{
		SH::Director d;
		FakeGame     g;
		d.SetCatalog(Cat(BaseCatalog()));
		const Layer naked{ { "Breasts", 0.8F }, { "Butt", 0.5F }, { "BreastsTogether", 0.1F }, { "Silhouette_Slim", 1234.0F } };

		// Dressed at first sight: the built-in set goes on (Slim has no refit of its own).
		g.layers[0x100] = naked;
		d.Seen(See(0x100, "Somebody", true));
		(void)Drain(d, g);
		const auto& on = g.layers[0x100];
		Check(on.contains("NipBGone") && on.at("BreastsTogether") == 0.3F && std::abs(on.at("Breasts") - 0.75F) < 1e-6F && on.at("NipBGone") == 1.0F && on.at("Butt") == 0.5F,
			"clothed: the built-in refit's values, the rest untouched");
		auto ev = Events(d);
		Check(!ev.empty() && ev.front().kind == SH::EventKind::kORefitChanged && ev.front().flag, "OnORefitChanged(applied)");
		Check(d.RefitApplied(0x100), "the refit is recorded");

		// Undressing puts back exactly the naked layer.
		d.Dressed(See(0x100, "Somebody", false), true);
		ev = Events(d);
		Check(Has(ev, SH::EventKind::kRemovingClothes) && Has(ev, SH::EventKind::kNaked), "OnActorRemovingClothes and OnActorNaked");
		(void)Drain(d, g);
		Check(g.layers[0x100] == naked, "naked again: the body is exactly what it was before the refit");
		Check(!d.RefitApplied(0x100), "the refit is off");

		// A preset with its own refit uses it; an outfit's own set outranks both.
		g.layers[0x200] = { { "Breasts", 0.8F }, { "Silhouette_Curvy", 1234.0F } };
		d.Seen(See(0x200, "Somebody", true));
		(void)Drain(d, g);
		Check(g.layers[0x200].at("Breasts") == 0.6F && !g.layers[0x200].contains("NipBGone"), "Curvy-Refit, not the built-in set");
		d.Dressed(See(0x200, "Somebody", true, "Jumpsuit-Refit"), false);
		(void)Drain(d, g);
		Check(g.layers[0x200].at("Breasts") == 0.4F, "another outfit with its own set: off, then that set on");
		d.Dressed(See(0x200, "Somebody", false), true);
		(void)Drain(d, g);
		Check((g.layers[0x200] == Layer{ { "Breasts", 0.8F }, { "Silhouette_Curvy", 1234.0F } }), "and naked, the original values");

		// A new body while clothed: the body first, then its refit.
		g.layers[0x300] = naked;
		d.Seen(See(0x300, "Piper", true));
		(void)Drain(d, g);
		Check(g.layers[0x300].contains("Silhouette_Curvy") && g.layers[0x300].at("Breasts") == 0.6F, "a rule's body arrives refit when they are dressed");
		d.Dressed(See(0x300, "Piper", false), true);
		(void)Drain(d, g);
		Check(g.layers[0x300].at("Breasts") == 0.8F, "and undressed, the preset's own value");

		// Switched off: everyone refit this session goes back; on: they are refit again.
		g.layers[0x400] = naked;
		d.Seen(See(0x400, "Somebody", true));
		(void)Drain(d, g);
		d.Configure({ .orefit = false });
		(void)Drain(d, g);
		Check(g.layers[0x400] == naked && !d.RefitApplied(0x400), "ORefit off: the naked body back at once");
		d.Configure({ .orefit = true });
		(void)Drain(d, g);
		Check(d.RefitApplied(0x400), "ORefit on: refit again");

		// Men: no set, no refit.
		auto man = See(0x500, "Somebody", true);
		man.facts.female = false;
		g.layers[0x500] = { { "BTChest", 0.4F }, { "Silhouette_BT_Average", 1234.0F } };
		d.Seen(man);
		(void)Drain(d, g);
		Check(!d.RefitApplied(0x500) && g.layers[0x500].at("BTChest") == 0.4F, "no male set: a clothed man is left as he is");

		// The refit survives a save and comes off after the load.
		const auto   bytes = d.SaveRecords(nullptr);
		SH::Director after;
		after.SetCatalog(Cat(BaseCatalog()));
		std::string error;
		Check(after.LoadRecords(bytes, SH::Registry::kVersion, [](std::uint32_t id) { return id; }, error), "records load");
		after.Seen(See(0x400, "Somebody", false));
		(void)Drain(after, g);
		Check(g.layers[0x400] == naked, "after a load, undressed: the snapshot from the save puts the naked body back");
	}

	void TestDirectorPicker()
	{
		SH::Director d;
		FakeGame     g;
		d.SetCatalog(Cat(BaseCatalog()));
		const Layer before{ { "Breasts", 0.33F }, { "Butt", 0.21F }, { "Silhouette_Slim", 1234.0F } };
		g.layers[0x100] = before;
		d.Seen(See(0x100, "Cait"));
		(void)Drain(d, g);
		(void)Events(d);

		auto msg = d.PickerStart(0x100, true, 0x00012345, "Cait");
		Check(msg.find("Cait") != std::string::npos, "Pick names who was picked");
		Check(d.PickerStep(1).find("Still reading") != std::string::npos, "Next waits for the snapshot");
		(void)Drain(d, g);
		Check(d.PickerReady(), "the snapshot is in");
		msg = d.PickerStep(1);
		Check(msg == "Cait: Curvy (1/3)", std::format("Next shows the preset and where it is in the list ({})", msg));
		(void)Drain(d, g);
		Check(g.layers[0x100].contains("Silhouette_Curvy"), "the preview is on her");
		const auto back1 = d.PickerStep(-1);
		const auto back2 = d.PickerStep(-1);
		Check(back1 == "Cait: Athletic (3/3)" && back2 == "Cait: Slim (2/3)", std::format("Previous goes round ({} / {})", back1, back2));
		(void)Drain(d, g);
		Check(!d.RecordOf(0x100) || d.RecordOf(0x100)->source != SH::Source::kPicker, "a preview is not a choice");
		msg = d.PickerCancel();
		(void)Drain(d, g);
		Check(g.layers[0x100] == before, std::format("Cancel puts back exactly what she had ({})", msg));
		Check(d.PickerTarget() == 0, "and ends the picking");

		// Keep records the choice.
		(void)d.PickerStart(0x100, true, 0x00012345, "Cait");
		(void)Drain(d, g);
		(void)d.PickerStep(3);
		(void)Drain(d, g);
		msg = d.PickerKeep();
		Check(msg == "Cait keeps Athletic.", msg);
		const auto rec = d.RecordOf(0x100);
		Check(rec && rec->source == SH::Source::kPicker && rec->preset == "Athletic", "Keep records a picker choice");
		Check(Has(Events(d), SH::EventKind::kGenerated, "Athletic"), "Keep announces the body");

		// Picked while clothed and refit: Cancel gives back the refit body, via the naked one.
		const Layer naked{ { "Breasts", 0.8F }, { "Silhouette_Slim", 1234.0F } };
		g.layers[0x200] = naked;
		d.Seen(See(0x200, "Curie", true));
		(void)Drain(d, g);
		const auto refit = g.layers[0x200];
		(void)d.PickerStart(0x200, true, 0x00012345, "Curie");
		(void)Drain(d, g);
		(void)d.PickerStep(1);
		(void)Drain(d, g);
		Check(g.layers[0x200].at("Breasts") == 0.6F, "a clothed preview wears its preset's refit");
		(void)d.PickerCancel();
		(void)Drain(d, g);
		Check(g.layers[0x200] == refit, "Cancel on a clothed NPC: her own body, refit exactly as before");
		d.Dressed(See(0x200, "Curie", false), true);
		(void)Drain(d, g);
		Check(g.layers[0x200] == naked, "and undressed, exactly her naked body");

		// Picking someone else cancels the first; a failed snapshot ends the picking.
		(void)d.PickerStart(0x100, true, 0x00012345, "Cait");
		(void)Drain(d, g);
		(void)d.PickerStep(1);
		msg = d.PickerStart(0x200, true, 0x00012345, "Curie");
		Check(msg.starts_with("Cait is back to"), msg);
		std::uint32_t snap = 0;
		while (const auto id = d.NextOrder()) {
			if (d.Peek(id)->kind == SH::OrderKind::kSnapshot) {
				snap = id;
				break;
			}
			RunOrder(d, id, g);
		}
		Check(snap != 0, "Curie's snapshot is asked for");
		d.Done(snap, false);
		(void)Drain(d, g);
		Check(d.PickerTarget() == 0, "a snapshot that failed ends the picking instead of leaving it waiting");
		Check(g.layers[0x100].contains("Silhouette_Athletic"), "Cait is back to her kept body");
	}
}

int main()
{
	TestCatalog();
	TestRules();
	TestRefit();
	TestPlan();
	TestRegistry();
	TestDirectorBodies();
	TestDirectorRefit();
	TestDirectorPicker();
	std::cout << g_passed << " passed, " << g_failed << " failed\n";
	return g_failed;
}

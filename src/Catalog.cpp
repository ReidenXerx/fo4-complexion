#include "Catalog.h"

namespace SH
{
	namespace
	{
		using json = nlohmann::json;

		// Every reader throws on a wrong shape; ParseCatalog turns the first throw into the error and
		// refuses the whole document.
		struct Bad : std::runtime_error
		{
			using std::runtime_error::runtime_error;
		};

		const json& At(const json& a_obj, std::string_view a_key, std::string_view a_where)
		{
			if (!a_obj.is_object()) {
				throw Bad(std::format("{}: expected an object", a_where));
			}
			const auto it = a_obj.find(a_key);
			if (it == a_obj.end()) {
				throw Bad(std::format("{}: missing \"{}\"", a_where, a_key));
			}
			return *it;
		}

		const json* Maybe(const json& a_obj, std::string_view a_key)
		{
			if (!a_obj.is_object()) {
				return nullptr;
			}
			const auto it = a_obj.find(a_key);
			return it == a_obj.end() || it->is_null() ? nullptr : &*it;
		}

		std::string Str(const json& a_v, std::string_view a_where)
		{
			if (!a_v.is_string()) {
				throw Bad(std::format("{}: expected a string", a_where));
			}
			return a_v.get<std::string>();
		}

		bool Bool(const json& a_v, std::string_view a_where)
		{
			if (!a_v.is_boolean()) {
				throw Bad(std::format("{}: expected true or false", a_where));
			}
			return a_v.get<bool>();
		}

		float Num(const json& a_v, std::string_view a_where)
		{
			if (!a_v.is_number()) {
				throw Bad(std::format("{}: expected a number", a_where));
			}
			const auto v = a_v.get<double>();
			if (!std::isfinite(v)) {
				throw Bad(std::format("{}: not a finite number", a_where));
			}
			return static_cast<float>(v);
		}

		bool Sex(const json& a_v, std::string_view a_where)
		{
			const auto s = Str(a_v, a_where);
			if (s == "female") {
				return true;
			}
			if (s == "male") {
				return false;
			}
			throw Bad(std::format("{}: sex must be \"female\" or \"male\", not \"{}\"", a_where, s));
		}

		std::vector<std::string> Strings(const json& a_v, std::string_view a_where)
		{
			if (!a_v.is_array()) {
				throw Bad(std::format("{}: expected a list", a_where));
			}
			std::vector<std::string> out;
			for (const auto& e : a_v) {
				out.push_back(Str(e, a_where));
			}
			return out;
		}

		// A non-negative integer, however the JSON holds it: a parser reads 12 as unsigned, a
		// program that builds the document may have written it signed.
		std::uint64_t Unsigned(const json& a_v, std::string_view a_where)
		{
			if (!a_v.is_number_integer() || (!a_v.is_number_unsigned() && a_v.get<std::int64_t>() < 0)) {
				throw Bad(std::format("{} must be a non-negative integer", a_where));
			}
			return a_v.get<std::uint64_t>();
		}

		FormRef Ref(const json& a_v, std::string_view a_where)
		{
			FormRef r;
			r.plugin = Str(At(a_v, "plugin", a_where), a_where);
			const auto value = Unsigned(At(a_v, "id", a_where), std::format("{}: id", a_where));
			// Without the load-order byte: at most 24 bits for a full plugin, 12 for a light one.
			if (value > 0xFFFFFF) {
				throw Bad(std::format("{}: id {:X} carries a load-order byte", a_where, value));
			}
			r.id = static_cast<std::uint32_t>(value);
			if (r.plugin.empty()) {
				throw Bad(std::format("{}: empty plugin name", a_where));
			}
			return r;
		}

		std::vector<FormRef> Refs(const json& a_v, std::string_view a_where)
		{
			if (!a_v.is_array()) {
				throw Bad(std::format("{}: expected a list", a_where));
			}
			std::vector<FormRef> out;
			for (const auto& e : a_v) {
				out.push_back(Ref(e, a_where));
			}
			return out;
		}

		// {"female": [...], "male": [...]} -> [male, female]
		template <class F>
		void PerSex(const json& a_v, std::string_view a_where, F&& a_each)
		{
			if (!a_v.is_object()) {
				throw Bad(std::format("{}: expected {{\"female\": ..., \"male\": ...}}", a_where));
			}
			for (const auto& [key, value] : a_v.items()) {
				if (key == "female") {
					a_each(true, value);
				} else if (key == "male") {
					a_each(false, value);
				} else {
					throw Bad(std::format("{}: unknown key \"{}\"", a_where, key));
				}
			}
		}

		RefitEntry::Op Op(const json& a_v, std::string_view a_where)
		{
			const auto s = Str(a_v, a_where);
			if (s == "set") {
				return RefitEntry::Op::kSet;
			}
			if (s == "add") {
				return RefitEntry::Op::kAdd;
			}
			if (s == "max") {
				return RefitEntry::Op::kMax;
			}
			if (s == "min") {
				return RefitEntry::Op::kMin;
			}
			throw Bad(std::format("{}: op must be set, add, max or min, not \"{}\"", a_where, s));
		}
	}

	bool IEquals(std::string_view a_lhs, std::string_view a_rhs)
	{
		return a_lhs.size() == a_rhs.size() &&
		       std::ranges::equal(a_lhs, a_rhs, [](char a, char b) {
				   return std::tolower(static_cast<unsigned char>(a)) == std::tolower(static_cast<unsigned char>(b));
			   });
	}

	bool FormRef::Is(std::string_view a_plugin, std::uint32_t a_id) const
	{
		return id == a_id && IEquals(plugin, a_plugin);
	}

	const Preset* Catalog::Find(std::string_view a_name, bool a_female) const
	{
		for (const auto& p : presets) {
			if (p.female == a_female && p.name == a_name) {
				return &p;
			}
		}
		return nullptr;
	}

	const Preset* Catalog::FindByMarker(std::string_view a_marker) const
	{
		for (const auto& p : presets) {
			if (p.marker == a_marker) {
				return &p;
			}
		}
		return nullptr;
	}

	std::vector<const Preset*> Catalog::MenuPresets(bool a_female) const
	{
		std::vector<const Preset*> out;
		for (const auto& p : presets) {
			if (p.female == a_female && p.menu) {
				out.push_back(&p);
			}
		}
		return out;
	}

	const RefitSet* Catalog::FindRefit(std::string_view a_name, bool a_female) const
	{
		for (const auto& s : refitSets) {
			if (s.female == a_female && IEquals(s.name, a_name)) {
				return &s;
			}
		}
		return nullptr;
	}

	std::string Catalog::OutfitRefitSet(std::string_view a_outfitName, bool a_female) const
	{
		if (a_outfitName.empty()) {
			return {};
		}
		for (const auto& o : outfitRefits) {
			if (o.female == a_female && IEquals(o.outfit, a_outfitName)) {
				return o.refitSet;
			}
		}
		return {};
	}

	bool Catalog::IsMarker(std::string_view a_morph)
	{
		return a_morph.starts_with("Silhouette_"sv);
	}

	const RefitSet* Catalog::RefitFor(std::string_view a_preset, bool a_female, std::string_view a_outfitSet) const
	{
		if (!a_outfitSet.empty()) {
			if (const auto* s = FindRefit(a_outfitSet, a_female)) {
				return s;
			}
		}
		if (!a_preset.empty()) {
			if (const auto* s = FindRefit(std::format("{}-Refit", a_preset), a_female)) {
				return s;
			}
		}
		if (const auto* s = FindRefit(a_female ? "Female-Refit"sv : "Male-Refit"sv, a_female)) {
			return s;
		}
		return FindRefit(a_female ? "builtin:female"sv : "builtin:male"sv, a_female);
	}

	void Catalog::AddManifest(std::uint32_t a_stamp, std::unordered_map<std::string, std::string> a_markers)
	{
		_manifests[a_stamp] = std::move(a_markers);
	}

	std::optional<std::string> Catalog::PresetForMarker(std::string_view a_marker, std::uint32_t a_stamp) const
	{
		if (const auto it = _manifests.find(a_stamp); it != _manifests.end()) {
			if (const auto m = it->second.find(std::string{ a_marker }); m != it->second.end()) {
				return m->second;
			}
		}
		// A stamp with no manifest (deleted by hand, or a build we never saw): the current build's
		// marker still names a preset of the same name when it exists.
		if (a_stamp == stamp) {
			if (const auto* p = FindByMarker(a_marker)) {
				return p->name;
			}
		}
		return std::nullopt;
	}

	std::optional<Catalog> ParseCatalog(const nlohmann::json& a_doc, std::string& a_error)
	{
		try {
			Catalog c;
			const auto& schema = At(a_doc, "schema", "catalog");
			if (!schema.is_number_integer() || schema.get<int>() != 1) {
				throw Bad("catalog: schema must be 1 (this plugin reads format 1 only)");
			}
			c.schema = 1;
			c.build = Str(At(a_doc, "build", "catalog"), "catalog.build");
			const auto stamp = Unsigned(At(a_doc, "stamp", "catalog"), "catalog.stamp");
			if (stamp == 0 || stamp >= (1ull << 24)) {
				throw Bad("catalog.stamp: must be 1 .. 2^24-1 (a marker holds it as a float32, exactly)");
			}
			c.stamp = static_cast<std::uint32_t>(stamp);
			c.mode = Str(At(a_doc, "mode", "catalog"), "catalog.mode");

			for (const auto& p : At(a_doc, "presets", "catalog")) {
				Preset preset;
				preset.name = Str(At(p, "name", "preset"), "preset.name");
				const auto where = std::format("preset \"{}\"", preset.name);
				preset.female = Sex(At(p, "sex", where), where);
				preset.marker = Str(At(p, "marker", where), where);
				for (const auto& [morph, value] : At(p, "values", where).items()) {
					preset.values.emplace_back(morph, Num(value, where));
				}
				preset.random = Bool(At(p, "random", where), where);
				preset.menu = Bool(At(p, "menu", where), where);
				preset.zeroed = Bool(At(p, "zeroed", where), where);
				preset.fit = Str(At(p, "fit", where), where);
				preset.family = Str(At(p, "family", where), where);
				if (c.Find(preset.name, preset.female)) {
					throw Bad(std::format("{}: listed twice for one sex", where));
				}
				c.presets.push_back(std::move(preset));
			}

			PerSex(At(a_doc, "player", "catalog"), "catalog.player", [&](bool a_female, const json& a_v) {
				c.playerDefault[a_female ? 1 : 0] = Str(a_v, "catalog.player");
			});
			PerSex(At(a_doc, "states", "catalog"), "catalog.states", [&](bool a_female, const json& a_v) {
				c.states[a_female ? 1 : 0] = Strings(a_v, "catalog.states");
			});
			PerSex(At(a_doc, "variety", "catalog"), "catalog.variety", [&](bool a_female, const json& a_v) {
				if (!a_v.is_array()) {
					throw Bad("catalog.variety: expected a list per sex");
				}
				for (const auto& e : a_v) {
					VarietyRange r;
					r.morph = Str(At(e, "morph", "variety"), "variety.morph");
					const auto where = std::format("variety \"{}\"", r.morph);
					r.low = Num(At(e, "low", where), where);
					r.high = Num(At(e, "high", where), where);
					r.group = Str(At(e, "group", where), where);
					if (r.low > r.high) {
						throw Bad(std::format("{}: low {} is above high {}", where, r.low, r.high));
					}
					if (r.group != "nipples" && r.group != "genitals") {
						throw Bad(std::format("{}: group must be \"nipples\" or \"genitals\", not \"{}\"", where, r.group));
					}
					auto& list = c.variety[a_female ? 1 : 0];
					if (std::ranges::any_of(list, [&](const VarietyRange& a_o) { return a_o.morph == r.morph; })) {
						throw Bad(std::format("{}: listed twice for one sex", where));
					}
					list.push_back(std::move(r));
				}
			});
			c.blacklistMarker = Str(At(a_doc, "blacklistMarker", "catalog"), "catalog.blacklistMarker");
			if (!Catalog::IsMarker(c.blacklistMarker)) {
				throw Bad(std::format("catalog.blacklistMarker \"{}\" must start with Silhouette_", c.blacklistMarker));
			}

			const auto& rules = At(a_doc, "rules", "catalog");
			c.races = Strings(At(rules, "races", "rules"), "rules.races");
			PerSex(At(rules, "npcFormID", "rules"), "rules.npcFormID", [&](bool a_female, const json& a_v) {
				c.npcFormIDRules[a_female ? 1 : 0] = Refs(a_v, "rules.npcFormID");
			});
			c.blacklistedNpcsFormID = Refs(At(rules, "blacklistedNpcsFormID", "rules"), "rules.blacklistedNpcsFormID");
			PerSex(At(rules, "blacklistedPlugins", "rules"), "rules.blacklistedPlugins", [&](bool a_female, const json& a_v) {
				c.blacklistedPlugins[a_female ? 1 : 0] = Strings(a_v, "rules.blacklistedPlugins");
			});
			PerSex(At(rules, "blacklistedRaces", "rules"), "rules.blacklistedRaces", [&](bool a_female, const json& a_v) {
				c.blacklistedRaces[a_female ? 1 : 0] = Strings(a_v, "rules.blacklistedRaces");
			});
			for (const auto& r : At(rules, "npcName", "rules")) {
				NameRule rule;
				rule.name = Str(At(r, "name", "rules.npcName"), "rules.npcName");
				rule.female = Sex(At(r, "sex", "rules.npcName"), "rules.npcName");
				rule.presets = Strings(At(r, "presets", "rules.npcName"), "rules.npcName");
				c.nameRules.push_back(std::move(rule));
			}
			c.blacklistedNpcNames = Strings(At(rules, "blacklistedNpcNames", "rules"), "rules.blacklistedNpcNames");
			for (const auto& r : At(rules, "faction", "rules")) {
				FactionRule rule;
				rule.faction = Ref(r, "rules.faction");
				rule.editorID = Str(At(r, "editorID", "rules.faction"), "rules.faction");
				rule.female = Sex(At(r, "sex", "rules.faction"), "rules.faction");
				rule.presets = Strings(At(r, "presets", "rules.faction"), "rules.faction");
				c.factionRules.push_back(std::move(rule));
			}

			const auto& orefit = At(a_doc, "orefit", "catalog");
			c.orefitEnabled = Bool(At(orefit, "enabled", "orefit"), "orefit.enabled");
			for (const auto& s : At(orefit, "slots", "orefit")) {
				if (!s.is_number_integer() || s.get<int>() < 30 || s.get<int>() > 61) {
					throw Bad("orefit.slots: biped slots are 30..61");
				}
				c.clothedSlots.push_back(s.get<int>());
			}
			c.outfitBlacklist = Refs(At(orefit, "blacklist", "orefit"), "orefit.blacklist");
			c.outfitBlacklistNames = Strings(At(orefit, "blacklistNames", "orefit"), "orefit.blacklistNames");
			c.outfitBlacklistPlugins = Strings(At(orefit, "blacklistPlugins", "orefit"), "orefit.blacklistPlugins");
			c.forceRefit = Refs(At(orefit, "force", "orefit"), "orefit.force");
			c.forceRefitNames = Strings(At(orefit, "forceNames", "orefit"), "orefit.forceNames");
			for (const auto& o : At(orefit, "outfits", "orefit")) {
				OutfitRefit refit;
				refit.outfit = Str(At(o, "name", "orefit.outfits"), "orefit.outfits");
				refit.female = Sex(At(o, "sex", "orefit.outfits"), "orefit.outfits");
				refit.refitSet = Str(At(o, "set", "orefit.outfits"), "orefit.outfits");
				c.outfitRefits.push_back(std::move(refit));
			}
			for (const auto& s : At(orefit, "sets", "orefit")) {
				RefitSet set;
				set.name = Str(At(s, "name", "orefit.sets"), "orefit.sets");
				const auto where = std::format("refit set \"{}\"", set.name);
				set.female = Sex(At(s, "sex", where), where);
				for (const auto& e : At(s, "entries", where)) {
					RefitEntry entry;
					entry.morph = Str(At(e, "morph", where), where);
					entry.op = Op(At(e, "op", where), where);
					entry.value = Num(At(e, "value", where), where);
					set.entries.push_back(std::move(entry));
				}
				c.refitSets.push_back(std::move(set));
			}

			// Every preset a rule names must exist for that sex, or the rule is a promise the plugin
			// cannot keep: refuse the file now rather than skipping NPCs later without a word.
			for (const auto& r : c.nameRules) {
				for (const auto& p : r.presets) {
					if (!c.Find(p, r.female)) {
						throw Bad(std::format("rules.npcName \"{}\": preset \"{}\" is not in this catalog", r.name, p));
					}
				}
			}
			for (const auto& r : c.factionRules) {
				for (const auto& p : r.presets) {
					if (!c.Find(p, r.female)) {
						throw Bad(std::format("rules.faction \"{}\": preset \"{}\" is not in this catalog", r.editorID, p));
					}
				}
			}
			for (const bool female : { false, true }) {
				const auto& d = c.playerDefault[female ? 1 : 0];
				if (!d.empty() && !c.Find(d, female)) {
					throw Bad(std::format("player default \"{}\" is not in this catalog", d));
				}
				// A range on a runtime state would roll a permanent erection or an open body (S-16).
				for (const auto& r : c.variety[female ? 1 : 0]) {
					if (std::ranges::any_of(c.states[female ? 1 : 0], [&](const std::string& a_s) { return IEquals(a_s, r.morph); })) {
						throw Bad(std::format("variety \"{}\" is a runtime state (S-16) and is never rolled", r.morph));
					}
				}
			}
			for (const auto& o : c.outfitRefits) {
				if (!c.FindRefit(o.refitSet, o.female)) {
					throw Bad(std::format("orefit.outfits \"{}\": refit set \"{}\" is not in this catalog", o.outfit, o.refitSet));
				}
			}
			return c;
		} catch (const std::exception& e) {
			a_error = e.what();
			return std::nullopt;
		}
	}

	std::optional<std::pair<std::uint32_t, std::unordered_map<std::string, std::string>>>
		ParseManifest(const nlohmann::json& a_doc, std::string& a_error)
	{
		try {
			const auto stamp = Unsigned(At(a_doc, "stamp", "manifest"), "manifest.stamp");
			if (stamp == 0 || stamp >= (1ull << 24)) {
				throw Bad("manifest.stamp: must be 1 .. 2^24-1");
			}
			std::unordered_map<std::string, std::string> markers;
			for (const auto& [marker, entry] : At(a_doc, "templates", "manifest").items()) {
				markers.emplace(marker, Str(At(entry, "preset", marker), marker));
			}
			return std::make_pair(static_cast<std::uint32_t>(stamp), std::move(markers));
		} catch (const std::exception& e) {
			a_error = e.what();
			return std::nullopt;
		}
	}

	std::vector<std::pair<std::string, float>> ApplyRefit(
		const RefitSet& a_set, const std::unordered_map<std::string, float>& a_current)
	{
		std::vector<std::pair<std::string, float>> out;
		for (const auto& e : a_set.entries) {
			const auto it = a_current.find(e.morph);
			const float now = it == a_current.end() ? 0.0F : it->second;
			float v = now;
			switch (e.op) {
			case RefitEntry::Op::kSet:
				v = e.value;
				break;
			case RefitEntry::Op::kAdd:
				v = now + e.value;
				break;
			case RefitEntry::Op::kMax:
				v = std::max(now, e.value);
				break;
			case RefitEntry::Op::kMin:
				v = std::min(now, e.value);
				break;
			}
			// One morph named twice in a set: the later entry works on the earlier result, which is
			// what reading the set top to bottom means.
			const auto prior = std::ranges::find_if(out, [&](const auto& a_p) { return a_p.first == e.morph; });
			if (prior != out.end()) {
				switch (e.op) {
				case RefitEntry::Op::kSet:
					prior->second = e.value;
					break;
				case RefitEntry::Op::kAdd:
					prior->second += e.value;
					break;
				case RefitEntry::Op::kMax:
					prior->second = std::max(prior->second, e.value);
					break;
				case RefitEntry::Op::kMin:
					prior->second = std::min(prior->second, e.value);
					break;
				}
			} else {
				out.emplace_back(e.morph, v);
			}
		}
		return out;
	}
}

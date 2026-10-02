#include "Compose.h"

namespace CX
{
	namespace
	{
		// SplitMix64, as tools/compose.py's Rng.
		class Rng
		{
		public:
			explicit Rng(std::uint64_t a_seed) :
				_s(a_seed) {}

			std::uint64_t Next()
			{
				_s += 0x9E3779B97F4A7C15ull;
				auto z = _s;
				z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
				z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
				return z ^ (z >> 31);
			}
			int           Percent() { return static_cast<int>(Next() % 100); }
			std::size_t   Pick(std::size_t a_n) { return static_cast<std::size_t>(Next() % a_n); }

		private:
			std::uint64_t _s;
		};

		int Layer(std::string_view a_kind)
		{
			static const std::map<std::string, int, std::less<>> layers{
				{ "skin", -100 }, { "mole", -100 }, { "freckles", -100 }, { "acne", -100 }, { "birthmark", -100 }, { "nipple", -100 },
				{ "scar", -90 }, { "wound", -90 }, { "burn", -90 }, { "bruise", -90 }, { "marks", -90 },
				{ "pubic_hair", -80 }, { "body_hair", -80 },
				{ "tattoo", -70 }, { "brand", -65 }, { "dirt", -60 }, { "blood", -55 }, { "nails", -50 }
			};
			const auto it = layers.find(a_kind);
			return it == layers.end() ? -70 : it->second;
		}

		bool Has(const std::vector<std::string>& a_list, std::string_view a_value)
		{
			return std::ranges::find(a_list, a_value) != a_list.end();
		}

		bool Adultish(const Template& a_t)
		{
			return a_t.adult || Has(a_t.style, "degrading") || Has(a_t.style, "sexual");
		}

		std::vector<std::string> Strings(const nlohmann::ordered_json& a_json)
		{
			std::vector<std::string> out;
			if (a_json.is_array()) {
				for (const auto& v : a_json) {
					if (v.is_string()) {
						out.push_back(v.get<std::string>());
					}
				}
			}
			return out;
		}
	}

	const Group* Profiles::Find(std::string_view a_name) const
	{
		for (const auto& g : groups) {
			if (g.name == a_name) {
				return &g;
			}
		}
		return nullptr;
	}

	Profiles ParseProfiles(std::string_view a_text)
	{
		// Kind weights are walked in FILE order: parsed as ordered_json straight from the text. A json (std::map)
		// in between sorts them, and every weighted roll then lands on another kind than tools/compose.py's.
		const auto j = nlohmann::ordered_json::parse(a_text, nullptr, true, true);
		Profiles p;
		p.cap = j.at("cap").get<int>();
		for (const auto& [k, v] : j.at("kinds").items()) {
			p.kinds[k] = Strings(v);
		}
		for (const auto& [k, v] : j.at("hair").items()) {
			p.hair[k] = Strings(v);
		}
		for (const auto& u : j.at("universal").at("female")) {
			p.female.push_back({ u.at("kind").get<std::string>(), u.at("percent").get<int>() });
		}
		for (const auto& u : j.at("universal").at("male")) {
			p.male.push_back({ u.at("kind").get<std::string>(), u.at("percent").get<int>() });
		}
		const auto& r = j.at("rules");
		p.sameKindDecay = r.at("same_kind_decay").get<double>();
		p.styleShare = r.at("style_share").get<double>();
		p.oneLarge = r.at("one_large").get<bool>();
		p.regionsUnique = r.at("regions_unique").get<bool>();
		p.fallback = j.at("default").get<std::string>();

		// The faction groups in their order, then the named characters, then the default.
		std::vector<std::pair<std::string, const nlohmann::ordered_json*>> order;
		for (const auto& name : Strings(j.at("order"))) {
			order.emplace_back(name, &j.at("groups").at(name));
		}
		if (j.contains("characters")) {
			for (const auto& [name, c] : j.at("characters").items()) {
				order.emplace_back("npc:" + name, &c);
			}
		}
		order.emplace_back(p.fallback, &j.at("groups").at(p.fallback));
		for (const auto& [name, gp] : order) {
			const auto& g = *gp;
			Group out;
			out.name = name;
			if (g.contains("forms")) {
				for (const auto& f : g.at("forms")) {
					out.members.push_back({ f.at(0).get<std::string>(), f.at(1).get<std::string>(), f.at(2).get<std::uint32_t>() });
				}
			}
			if (g.value("untouched", false)) {
				out.untouched = true;
				out.count = { 100, 0, 0, 0, 0 };
				out.hair = "any";
				p.groups.push_back(std::move(out));
				continue;
			}
			for (const auto& f : g.value("factions", nlohmann::ordered_json::array())) {
				out.factions.push_back({ f.at(0).get<std::string>(), f.at(1).get<std::string>(), f.size() > 2 ? f.at(2).get<std::uint32_t>() : 0u });
			}
			const auto count = g.at("count");
			if (count.size() != 5) {
				throw std::runtime_error(std::format("group {}: count needs 5 numbers", name));
			}
			int sum = 0;
			for (std::size_t i = 0; i < 5; ++i) {
				out.count[i] = count.at(i).get<int>();
				sum += out.count[i];
			}
			if (sum != 100) {
				throw std::runtime_error(std::format("group {}: count adds up to {}, not 100", name, sum));
			}
			for (const auto& [k, v] : g.at("kinds").items()) {
				if (!p.kinds.contains(k)) {
					throw std::runtime_error(std::format("group {}: no feature kind {}", name, k));
				}
				out.kinds.emplace_back(k, v.get<int>());
			}
			out.styles = Strings(g.at("styles"));
			out.emblems = Strings(g.at("emblems"));
			out.sizes = Strings(g.at("sizes"));
			out.hair = g.at("hair").get<std::string>();
			if (!p.hair.contains(out.hair)) {
				throw std::runtime_error(std::format("group {}: no hair style {}", name, out.hair));
			}
			out.adult = g.at("adult").get<int>();
			p.groups.push_back(std::move(out));
		}
		return p;
	}

	std::vector<Template> ParseCatalog(const nlohmann::json& a_tags, const std::set<std::string>& a_installed)
	{
		std::vector<Template> out;
		for (const auto& [key, t] : a_tags.items()) {  // std::map: sorted by key, as Python's sorted()
			if (key.size() < 3 || key[1] != ':') {
				continue;
			}
			if (t.value("quality", "") != "ok" || t.value("lore", "") == "breaks") {
				continue;
			}
			if (!a_installed.empty() && !a_installed.contains(key)) {
				continue;
			}
			Template x;
			x.key = key;
			x.id = key.substr(2);
			x.female = key[0] == 'f';
			x.kind = t.value("kind", "");
			if (t.contains("regions") && t["regions"].is_array()) {
				for (const auto& r : t["regions"]) {
					x.regions.push_back(r.get<std::string>());
				}
			}
			x.size = t.value("size", "");
			if (t.contains("style") && t["style"].is_array()) {
				for (const auto& s : t["style"]) {
					x.style.push_back(s.get<std::string>());
				}
			}
			if (t.contains("emblem") && t["emblem"].is_string()) {
				x.emblem = t["emblem"].get<std::string>();
			}
			x.adult = t.value("adult", false);
			out.push_back(std::move(x));
		}
		return out;
	}

	std::vector<Pick> Compose(const Profiles& a_profiles, const std::vector<Template>& a_catalog, bool a_female, const Group& a_group,
		std::uint64_t a_seed, bool a_adultAllowed)
	{
		if (a_group.untouched) {
			return {};
		}
		Rng                             rng(a_seed);
		std::vector<const Template*>    mine;
		for (const auto& t : a_catalog) {
			if (t.female == a_female) {
				mine.push_back(&t);
			}
		}
		std::vector<Pick>     picks;
		std::set<std::string> usedRegions;
		bool                  large = false;

		const auto take = [&](const Template& a_t, const std::string& a_kind) {
			picks.push_back({ a_t.key, a_t.id, a_kind, Layer(a_t.kind) + static_cast<int>(picks.size()) });
			if (a_t.kind == "tattoo" || a_t.kind == "brand" || a_t.kind == "scar" || a_t.kind == "wound" || a_t.kind == "burn") {
				usedRegions.insert(a_t.regions.begin(), a_t.regions.end());
			}
			if (a_t.size == "large" || a_t.size == "full") {
				large = true;
			}
		};
		const auto picked = [&](const Template& a_t) {
			return std::ranges::any_of(picks, [&](const Pick& p) { return p.key == a_t.key; });
		};

		// 1. universal
		for (const auto& u : a_female ? a_profiles.female : a_profiles.male) {
			const auto roll = rng.Percent();
			if (roll >= u.percent) {
				continue;
			}
			std::vector<const Template*> cands;
			for (const auto* t : mine) {
				// Emblems only for members here too: some pubic hair is trimmed into a faction's mark.
				if (t->kind == u.kind && !Adultish(*t) && (t->emblem.empty() || Has(a_group.emblems, t->emblem))) {
					cands.push_back(t);
				}
			}
			if (u.kind == "pubic_hair") {
				const auto& sizes = a_profiles.hair.at(a_group.hair);
				std::vector<const Template*> sized;
				for (const auto* t : cands) {
					if (Has(sizes, t->size)) {
						sized.push_back(t);
					}
				}
				if (!sized.empty()) {
					cands = std::move(sized);
				}
			}
			if (!cands.empty()) {
				take(*cands[rng.Pick(cands.size())], u.kind);
			}
		}

		// 2. count
		auto roll = rng.Percent();
		int  n = 0;
		for (int i = 0; i < 5; ++i) {
			if (roll < a_group.count[i]) {
				n = i;
				break;
			}
			roll -= a_group.count[i];
		}
		n = std::max(0, std::min(n, a_profiles.cap - static_cast<int>(picks.size())));

		// 3. style
		const std::set<std::string> allowedEmblems(a_group.emblems.begin(), a_group.emblems.end());
		const auto candidates = [&](const std::string& a_kind, bool a_adultOk) {
			std::vector<const Template*> out;
			const auto& kinds = a_profiles.kinds.at(a_kind);
			for (const auto* t : mine) {
				if (!Has(kinds, t->kind) || picked(*t)) {
					continue;
				}
				if (!t->emblem.empty() && !allowedEmblems.contains(t->emblem)) {
					continue;
				}
				if (Adultish(*t) && !a_adultOk) {
					continue;
				}
				if (a_kind == "tattoo" || a_kind == "brand") {
					if (!Has(a_group.sizes, t->size)) {
						continue;
					}
					if ((t->size == "large" || t->size == "full") && large && a_profiles.oneLarge) {
						continue;
					}
				}
				if (a_profiles.regionsUnique && !t->regions.empty()) {
					bool clash = usedRegions.contains("full_body") ||
					             (Has(t->regions, "full_body") && !usedRegions.empty());
					for (const auto& r : t->regions) {
						clash = clash || usedRegions.contains(r);
					}
					if (clash) {
						continue;
					}
				}
				out.push_back(t);
			}
			return out;
		};

		std::vector<std::string> styles;
		{
			const auto tattoos = candidates("tattoo", true);
			for (const auto& s : a_group.styles) {
				if (std::ranges::any_of(tattoos, [&](const Template* t) { return Has(t->style, s); })) {
					styles.push_back(s);
				}
			}
		}
		std::string style = styles.empty() ? std::string{} : styles[rng.Pick(styles.size())];

		// 4. features
		std::map<std::string, int> times;
		for (int i = 0; i < n; ++i) {
			const bool adultOk = a_adultAllowed && a_group.adult > 0 && rng.Percent() < a_group.adult;
			std::vector<std::pair<std::string, double>> weights;
			for (const auto& [kind, w] : a_group.kinds) {
				if (!candidates(kind, adultOk).empty()) {
					weights.emplace_back(kind, w * std::pow(a_profiles.sameKindDecay, times[kind]));
				}
			}
			if (weights.empty()) {
				break;
			}
			double total = 0;
			for (const auto& [k, w] : weights) {
				total += w;
			}
			double r = static_cast<double>(rng.Next() % 1000000) / 1000000.0 * total;
			std::string kind = weights.back().first;
			for (const auto& [k, w] : weights) {
				if (r < w) {
					kind = k;
					break;
				}
				r -= w;
			}
			auto cands = candidates(kind, adultOk);
			if (kind == "tattoo" || kind == "brand") {
				std::vector<const Template*> fitting;
				for (const auto* t : cands) {
					const bool emblem = !t->emblem.empty() && allowedEmblems.contains(t->emblem);
					const bool styled = std::ranges::any_of(t->style, [&](const std::string& s) { return Has(a_group.styles, s); });
					if (emblem || styled || (adultOk && Adultish(*t))) {
						fitting.push_back(t);
					}
				}
				if (!fitting.empty()) {
					cands = std::move(fitting);
				} else if (!a_group.styles.empty() || !a_group.emblems.empty()) {
					cands.clear();
				}
				if (!style.empty() && rng.Percent() < a_profiles.styleShare * 100) {
					std::vector<const Template*> styledCands;
					for (const auto* t : cands) {
						if (Has(t->style, style)) {
							styledCands.push_back(t);
						}
					}
					if (!styledCands.empty()) {
						cands = std::move(styledCands);
					}
				}
			}
			if (cands.empty()) {
				continue;
			}
			take(*cands[rng.Pick(cands.size())], kind);
			times[kind] += 1;
		}
		return picks;
	}
}

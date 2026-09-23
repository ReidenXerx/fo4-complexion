#include "Plan.h"

namespace SH
{
	namespace
	{
		std::uint32_t Fnv1a(std::string_view a_text, std::uint32_t a_hash = 2166136261u)
		{
			for (const unsigned char c : a_text) {
				a_hash ^= c;
				a_hash *= 16777619u;
			}
			return a_hash;
		}

		std::uint32_t Mix(std::uint32_t a_x)
		{
			a_x = (a_x ^ (a_x >> 16)) * 0x85EBCA6Bu;
			a_x = (a_x ^ (a_x >> 13)) * 0xC2B2AE35u;
			return a_x ^ (a_x >> 16);
		}

		bool IsState(const Catalog& a_catalog, bool a_female, std::string_view a_morph)
		{
			return std::ranges::any_of(a_catalog.states[a_female ? 1 : 0], [&](const std::string& s) { return IEquals(s, a_morph); });
		}
	}

	float Draw(std::uint32_t a_seed, std::string_view a_morph, float a_low, float a_high)
	{
		if (!(a_low < a_high)) {
			return a_low;
		}
		// 24 random bits: every one of them lands exactly in a float's mantissa.
		const auto bits = Mix(Mix(a_seed + 0x9E3779B9u) ^ Fnv1a(a_morph)) >> 8;
		const auto u = static_cast<double>(bits) / static_cast<double>(1u << 24);  // [0, 1)
		return static_cast<float>(a_low + (static_cast<double>(a_high) - a_low) * u);
	}

	Morphs BodyFor(const Catalog& a_catalog, const Preset& a_preset, std::uint32_t a_seed, VarietySwitches a_switches)
	{
		const int sex = a_preset.female ? 1 : 0;
		Morphs    out;
		out.reserve(a_preset.values.size() + a_catalog.variety[sex].size() + 1);

		const auto ranged = [&](std::string_view a_morph) -> const VarietyRange* {
			for (const auto& r : a_catalog.variety[sex]) {
				if (r.morph == a_morph) {
					const bool on = r.group == "nipples" ? a_switches.nipples : a_switches.genitals;
					return on ? &r : nullptr;
				}
			}
			return nullptr;
		};

		for (const auto& [morph, value] : a_preset.values) {
			if (IsState(a_catalog, a_preset.female, morph) || ranged(morph)) {
				continue;
			}
			out.emplace_back(morph, value);
		}
		// Every range, whether or not the preset names the morph: BodyGen writes the range into every
		// template of the sex (S-17, S-21), so a preset that never touched a nipple still gets one.
		for (const auto& r : a_catalog.variety[sex]) {
			if (ranged(r.morph)) {
				out.emplace_back(r.morph, Draw(a_seed, r.morph, r.low, r.high));
			}
		}
		std::erase_if(out, [](const auto& p) { return std::abs(p.second) < 1e-6F; });
		out.emplace_back(a_preset.marker, static_cast<float>(a_catalog.stamp));
		return out;
	}

	Morphs Unrefit(Morphs a_layer, const Morphs& a_refitSnapshot)
	{
		for (const auto& [morph, naked] : a_refitSnapshot) {
			const auto it = std::ranges::find_if(a_layer, [&](const auto& p) { return p.first == morph; });
			if (std::abs(naked) < 1e-6F) {
				if (it != a_layer.end()) {
					a_layer.erase(it);
				}
			} else if (it != a_layer.end()) {
				it->second = naked;
			} else {
				a_layer.emplace_back(morph, naked);
			}
		}
		return a_layer;
	}

	std::uint32_t BodyHash(std::string_view a_marker, std::uint32_t a_stamp)
	{
		const auto h = Mix(Fnv1a(a_marker) ^ Mix(a_stamp));
		return h == 0 ? 1 : h;  // 0 means "never announced"
	}
}

#pragma once

#include "Catalog.h"

// The values the bridge writes, worked out without the game, so the offline tests check exactly what
// a body will hold.

namespace SH
{
	using Morphs = std::vector<std::pair<std::string, float>>;

	// SetNippleRand / SetGenitalRand (S-24). They change the bodies the plugin gives; BodyGen's own
	// rolls come from the files and always carry their ranges.
	struct VarietySwitches
	{
		bool nipples{ true };
		bool genitals{ true };
	};

	// A value in [low, high], the same every time for this person and this morph, and spread across
	// people. BodyGen draws uniformly in the same range, but anew each time it rolls.
	[[nodiscard]] float Draw(std::uint32_t a_seed, std::string_view a_morph, float a_low, float a_high);

	// Everything a preset gives one person, marker last, as BodyGen writes a template: the preset's
	// values, each variety range drawn in place of the preset's own value, runtime states left out
	// (S-16), and zeroes dropped -- LooksMenu stores 0 as "no entry", so writing one after a clear
	// would be a wasted call.
	[[nodiscard]] Morphs BodyFor(const Catalog& a_catalog, const Preset& a_preset, std::uint32_t a_seed, VarietySwitches a_switches);

	// The values a Cancel puts back when the picker's snapshot was taken while a refit was on: the
	// refit's own morphs hold clothed values, and the refit snapshot knows the naked ones.
	[[nodiscard]] Morphs Unrefit(Morphs a_layer, const Morphs& a_refitSnapshot);

	// A marker and the stamp it was written with, as one number, so the co-save can tell whether the
	// body it announced is still the body the actor has.
	[[nodiscard]] std::uint32_t BodyHash(std::string_view a_marker, std::uint32_t a_stamp);
}

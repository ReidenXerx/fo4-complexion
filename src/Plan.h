#pragma once

#include "Catalog.h"

// The values the bridge writes, worked out without the game, so the offline tests check exactly what
// a body will hold.

namespace SH
{
	using Morphs = std::vector<std::pair<std::string, float>>;

	// SetNippleRand / SetGenitalRand (S-24). They change the bodies the plugin gives and tops up;
	// BodyGen's own rolls come from the files and always carry their ranges.
	struct VarietySwitches
	{
		bool nipples{ true };
		bool genitals{ true };
	};

	// A value in [low, high], the same every time for this person and this morph, and spread across
	// people. BodyGen draws uniformly in the same range, but anew each time it rolls.
	[[nodiscard]] float Draw(std::uint32_t a_seed, std::string_view a_morph, float a_low, float a_high);

	// Everything a preset gives one person, marker last, as BodyGen writes a template: the preset's
	// values, each variety range drawn in place of the preset's own value (S-21), nothing that is never
	// part of a body (S-16, S-29), and zeroes dropped -- LooksMenu stores 0 as "no entry".
	//
	// a_keep: what the person holds now. A variety value they already have, inside its range, is kept:
	// giving the same preset again (Refresh, Reapply) leaves the variety BodyGen rolled for them.
	[[nodiscard]] Morphs BodyFor(const Catalog& a_catalog, const Preset& a_preset, std::uint32_t a_seed, VarietySwitches a_switches,
		const std::unordered_map<std::string, float>* a_keep = nullptr);

	// The variety an existing body lacks (S-44): a drawn value for every enabled range whose morph is not
	// in a_present. Nothing else.
	[[nodiscard]] Morphs TopUp(const Catalog& a_catalog, bool a_female, std::uint32_t a_seed, VarietySwitches a_switches,
		const std::vector<std::string>& a_present);

	// What goes under Silhouette's refit keyword while she is dressed (S-40): the refit marker FIRST, so a
	// refit a save cut short is still recognisable as one, then every floor of the set that applies
	// (heavy-only floors under heavy clothes, S-42). A morph named twice keeps its highest floor.
	[[nodiscard]] Morphs RefitFloors(const RefitSet& a_set, bool a_heavy);

	// A marker and the stamp it was written with, as one number, so the co-save can tell whether the
	// body it knows is still the body the actor has.
	[[nodiscard]] std::uint32_t BodyHash(std::string_view a_marker, std::uint32_t a_stamp);
}

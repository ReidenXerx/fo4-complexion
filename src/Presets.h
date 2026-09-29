#pragma once

#include "Catalog.h"

// S-76: the player's own installed BodySlide presets, read at run time and offered by the pickers (never
// random). The same rules the generator applies (tools/silhouette_gen.py, tools/base_body.py), in C++, so a
// preset looks in game exactly as BodySlide builds it and as the generator would have written it:
//   read_presets   first preset of a name wins (any case); a SetSlider counts by its big (or both) value /100
//   classify/band  fit = share of the preset's sliders the body's .tri carries; full >= 95 %, partial >= 50 %
//                  only for the body's own family; outfit-tuned copies are left out
//   resolve        every morph slider of the set the body was built with: the preset's value, else the
//                  set's default, inverted where the set says so; kept where the body has it and it is not 0
//   plain_marker   Silhouette_ + the name with every run of non-alphanumerics made one '_'
// Pure: no game in it, so the offline tests drive every rule.

namespace SH::Presets
{
	struct SliderPreset
	{
		std::string                                name;
		std::vector<std::string>                   families;  // <Group>s that name a body family
		std::vector<std::pair<std::string, double>> big;      // SetSlider big (or both) values, 0..1, as the generator reads them
	};

	// Every <Preset> of one BodySlide SliderPresets file.
	[[nodiscard]] std::vector<SliderPreset> ParseXml(std::string_view a_text);

	// Every morph name a BodySlide .tri carries, as written (the generator compares them exactly). Empty for bytes
	// that are not a .tri.
	[[nodiscard]] std::unordered_set<std::string> TriMorphs(std::span<const std::byte> a_bytes);

	// "Silhouette_" + the name, each run of characters other than ASCII letters and digits made one '_', the
	// ends trimmed; "" when nothing is left (tools/silhouette_gen.py plain_marker).
	[[nodiscard]] std::string PlainMarker(std::string_view a_name);

	struct Installed
	{
		std::vector<Preset>      added;
		std::vector<std::string> notes;  // one line per preset left out, and why
	};

	// The catalog's pickers extended by the player's presets: a_files is every SliderPresets file's presets in
	// BodySlide's order (sorted paths); a_morphs[sex] the body's .tri morph names ([0] male, [1] female; empty:
	// that sex is skipped). Names and markers the catalog already has stay the catalog's.
	[[nodiscard]] Installed Resolve(const Catalog& a_catalog, const std::vector<SliderPreset>& a_files,
		const std::unordered_set<std::string> (&a_morphs)[2]);

	// Resolve() over a game's Data folder: the loose FemaleBody.tri / MaleBody.tri and every *.xml under
	// Tools/BodySlide/SliderPresets, recursive, in sorted order. The plugin calls it with "Data"; the offline
	// tests' --presets mode with any folder, so the game's code path is the one compared with the generator.
	struct Read
	{
		Installed   installed;
		std::size_t files{ 0 };
		bool        body[2]{ false, false };  // [0] male, [1] female: a .tri with morphs was found
	};
	[[nodiscard]] Read ReadInstalled(const Catalog& a_catalog, const std::filesystem::path& a_data);

	// The loose body .tri of one sex under a Data folder: its morph names; empty when there is none, or it is
	// not a .tri.
	[[nodiscard]] std::unordered_set<std::string> BodyMorphs(const std::filesystem::path& a_data, bool a_female);

	// Whether Silhouette can shape one sex on this body: the share of the distinct sliders its random pool sets
	// that the body's .tri carries. Under half -- no .tri at all, or another body family's -- and Silhouette
	// leaves that sex alone (the owner, 2026-09-30: "if we don't see a supported body, do nothing on this sex").
	struct BodyFit
	{
		std::size_t used{ 0 };   // the pool's distinct sliders for the sex
		std::size_t found{ 0 };  // of them, in the .tri
		bool        supported{ false };
	};
	[[nodiscard]] BodyFit MeasureBody(const Catalog& a_catalog, bool a_female, const std::unordered_set<std::string>& a_morphs);
}

#pragma once

// Which overlays one NPC gets (C-2, C-5, C-7). A port of tools/compose.py, the reference: the same inputs give
// the same picks, step for step and roll for roll (tests check it against the Python output). No game in here.

namespace CX
{
	// One usable overlay template: what LooksMenu loads, joined with Complexion's tag for it.
	struct Template
	{
		std::string              key;  // "f:<id>" / "m:<id>", the catalog's sort key
		std::string              id;   // the LooksMenu template id
		bool                     female{ false };
		std::string              kind;
		std::vector<std::string> regions;
		std::string              size;
		std::vector<std::string> style;
		std::string              emblem;  // "" for none
		bool                     adult{ false };
		std::string              note;    // what it shows, in words (the tag's note): the overlay window's label
		std::string              hair;    // pubic_hair / body_hair: its colour family (tools/paint/hair.py); "" = unknown
	};

	struct Group
	{
		std::string                               name;
		struct Faction
		{
			std::string   plugin;
			std::string   editorID;
			std::uint32_t id{ 0 };  // the local form id, resolved offline (tools/make_data.py): no faction keeps its editor id at run time
		};
		std::vector<Faction>                      factions;
		std::vector<Faction>                      members;    // a named character: their NPC record(s)
		bool                                      untouched{ false };  // nothing at all, not even the universal layer
		std::array<int, 5>                        count{};
		std::vector<std::pair<std::string, int>>  kinds;  // in file order
		std::vector<std::string>                  styles;
		std::vector<std::string>                  emblems;
		std::vector<std::string>                  sizes;
		std::string                               hair;
		int                                       adult{ 0 };
	};

	struct Universal
	{
		std::string kind;
		int         percent{ 0 };
	};

	// A Rapport persona that adds marks of one style on top of the look (C-14).
	struct Persona
	{
		int                percent{ 0 };
		std::array<int, 4> count{};
		std::string        style;
	};

	// One body hair colour per person, matching their head hair (owner, 2026-10-04; profiles.json "hair_colours").
	struct HairColours
	{
		bool                                             present{ false };
		std::map<std::string, std::vector<std::string>> accept;   // head family -> template families
		std::vector<std::pair<std::string, int>>        unknown;  // a head colour not in accept: rolled, percent
		struct Form
		{
			std::string   plugin;
			std::string   editorID;
			std::uint32_t id{ 0 };
			std::string   family;
		};
		std::vector<Form> forms;  // the game's hair colour records (tools/make_data.py)
	};

	struct Profiles
	{
		int                                                    cap{ 6 };
		std::map<std::string, std::vector<std::string>>       kinds;  // feature kind -> tag kinds
		std::map<std::string, std::vector<std::string>>       hair;   // wild/trim/any -> sizes
		std::vector<Universal>                                 female;
		std::vector<Universal>                                 male;
		double                                                 sameKindDecay{ 0.5 };
		double                                                 styleShare{ 0.75 };
		bool                                                   oneLarge{ true };
		bool                                                   regionsUnique{ true };
		std::string                                            fallback;  // "default"
		std::vector<Group>                                     groups;    // in "order", then the default last
		std::map<std::string, Persona, std::less<>>            personas;
		HairColours                                            hairColours;
		[[nodiscard]] const Group*                             Find(std::string_view a_name) const;
	};

	struct Pick
	{
		std::string key;
		std::string id;
		std::string kind;
		int         priority{ 0 };
	};

	// The text of data/profiles.json; throws on a malformed file.
	[[nodiscard]] Profiles ParseProfiles(std::string_view a_text);

	// build/tags.json joined with what LooksMenu loaded: a_installed holds "f:<id>"/"m:<id>" keys, or is
	// empty to take every tag (the tests). Only quality "ok", lore not "breaks"; sorted by key.
	[[nodiscard]] std::vector<Template> ParseCatalog(const nlohmann::json& a_tags, const std::set<std::string>& a_installed);

	// The priority layer of a kind (skin lowest, nails highest; all negative, C-6).
	[[nodiscard]] int LayerOf(std::string_view a_kind);

	// Explicit or degrading: what the MCM's adult switch turns off.
	[[nodiscard]] bool IsAdult(const Template& a_t);

	[[nodiscard]] std::vector<Pick> Compose(const Profiles& a_profiles, const std::vector<Template>& a_catalog, bool a_female,
		const Group& a_group, std::uint64_t a_seed, bool a_adultAllowed, std::string_view a_persona = {},
		std::string_view a_hair = {});
}

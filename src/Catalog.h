#pragma once

// The catalog the generator writes (S-19): every preset that fits this install, the compiled rules,
// the ORefit sets, and -- from manifests/<stamp>.json -- what every marker any build wrote means.
// No game types in here: the offline tests load the same code.

namespace SH
{
	// A form named by the plugin that defines it and its id without the load-order byte, as the
	// generator reads it from the files. The game side resolves it through TESDataHandler.
	struct FormRef
	{
		std::string   plugin;
		std::uint32_t id{ 0 };

		[[nodiscard]] bool Is(std::string_view a_plugin, std::uint32_t a_id) const;
	};

	struct Preset
	{
		std::string                                 name;
		bool                                        female{ false };
		std::string                                 marker;
		std::vector<std::pair<std::string, float>> values;
		bool                                        random{ false };  // in the random pool
		bool                                        menu{ false };    // offered by the pickers
		bool                                        zeroed{ false };
		std::string                                 fit;     // "full" or "partial"
		std::string                                 family;  // the preset's declared body family
	};

	struct RefitEntry
	{
		enum class Op
		{
			kSet,  // the clothed value is this
			kAdd,  // the clothed value is the naked value plus this
			kMax,  // at least this
			kMin,  // at most this
		};

		std::string morph;
		Op          op{ Op::kSet };
		float       value{ 0.0F };
	};

	struct RefitSet
	{
		std::string             name;
		bool                    female{ false };
		std::vector<RefitEntry> entries;
	};

	struct NameRule
	{
		std::string              name;
		bool                     female{ false };
		std::vector<std::string> presets;
	};

	struct FactionRule
	{
		FormRef                  faction;
		std::string              editorID;  // what the config said, for the log
		bool                     female{ false };
		std::vector<std::string> presets;
	};

	// refitOutfitPresetsFemale / refitOutfitPresetsMale: an outfit, by its in-game name, that brings
	// its own refit set. Names, as OBody's users write them.
	struct OutfitRefit
	{
		std::string outfit;
		bool        female{ false };
		std::string refitSet;
	};

	// A morph BodyGen rolls per NPC (S-17, S-21): `Morph@low:high` in every template of that sex. A
	// body the plugin gives draws it the same way, from the reference id, so the draw is the same
	// every time it is given again.
	struct VarietyRange
	{
		std::string morph;
		float       low{ 0.0F };
		float       high{ 0.0F };
		std::string group;  // "nipples" or "genitals": what SetNippleRand / SetGenitalRand switch
	};

	class Catalog
	{
	public:
		int           schema{ 0 };
		std::string   build;
		std::uint32_t stamp{ 0 };
		std::string   mode;

		std::vector<Preset> presets;
		std::string         playerDefault[2];  // [0] male, [1] female
		std::vector<std::string> states[2];    // runtime states the body carries (S-16), never written
		std::vector<VarietyRange> variety[2];  // [0] male, [1] female
		std::string               blacklistMarker;  // the stored morph that keeps a name-blacklisted NPC bare (S-23)

		// Tiers BodyGen already carries -- the plugin must know them to leave those NPCs alone.
		std::vector<std::string> races;  // distributeRaces, editor ids
		std::vector<FormRef>     npcFormIDRules[2];
		std::vector<FormRef>     blacklistedNpcsFormID;
		std::vector<std::string> blacklistedPlugins[2];
		std::vector<std::string> blacklistedRaces[2];

		// Tiers only the runtime can see (S-23).
		std::vector<NameRule>    nameRules;
		std::vector<std::string> blacklistedNpcNames;
		std::vector<FactionRule> factionRules;

		// ORefit (S-20), with OBody's keys: blacklistedOutfitsFromORefit{FormID,,Plugin},
		// outfitsForceRefit{FormID,}, refitOutfitPresets{Female,Male}.
		bool                     orefitEnabled{ true };
		std::vector<int>         clothedSlots;  // biped slot numbers, 30..61
		std::vector<FormRef>     outfitBlacklist;
		std::vector<std::string> outfitBlacklistNames;
		std::vector<std::string> outfitBlacklistPlugins;
		std::vector<FormRef>     forceRefit;
		std::vector<std::string> forceRefitNames;
		std::vector<OutfitRefit> outfitRefits;
		std::vector<RefitSet>    refitSets;

		[[nodiscard]] const Preset* Find(std::string_view a_name, bool a_female) const;
		[[nodiscard]] const Preset* FindByMarker(std::string_view a_marker) const;
		[[nodiscard]] std::vector<const Preset*> MenuPresets(bool a_female) const;
		[[nodiscard]] const RefitSet* FindRefit(std::string_view a_name, bool a_female) const;

		// The refit set an outfit brings by its name, or "".
		[[nodiscard]] std::string OutfitRefitSet(std::string_view a_outfitName, bool a_female) const;

		// Whether a morph name is one of Silhouette's markers (a body's, or the blacklist's).
		[[nodiscard]] static bool IsMarker(std::string_view a_morph);

		// The refit for someone wearing this body: the outfit's own set if any, then
		// "<Preset>-Refit", then "Female-Refit"/"Male-Refit", then the built-in set.
		[[nodiscard]] const RefitSet* RefitFor(std::string_view a_preset, bool a_female, std::string_view a_outfitSet) const;

		// A marker of ANY build: the preset it names, from that build's manifest.
		void AddManifest(std::uint32_t a_stamp, std::unordered_map<std::string, std::string> a_markers);
		[[nodiscard]] std::optional<std::string> PresetForMarker(std::string_view a_marker, std::uint32_t a_stamp) const;
		[[nodiscard]] std::size_t ManifestCount() const { return _manifests.size(); }

	private:
		std::unordered_map<std::uint32_t, std::unordered_map<std::string, std::string>> _manifests;
	};

	// Parses catalog.json. On failure returns nullopt and says why in a_error: a catalog that half
	// parses is refused whole, because acting on half the rules is worse than acting on none.
	[[nodiscard]] std::optional<Catalog> ParseCatalog(const nlohmann::json& a_doc, std::string& a_error);

	// manifests/<stamp>.json -> marker -> exact preset name.
	[[nodiscard]] std::optional<std::pair<std::uint32_t, std::unordered_map<std::string, std::string>>>
		ParseManifest(const nlohmann::json& a_doc, std::string& a_error);

	// The clothed values: every entry of the set applied to what the NPC has now. Morphs the set does
	// not name are not in the result; a morph the NPC does not have counts as 0.
	[[nodiscard]] std::vector<std::pair<std::string, float>> ApplyRefit(
		const RefitSet& a_set, const std::unordered_map<std::string, float>& a_current);

	[[nodiscard]] bool IEquals(std::string_view a_lhs, std::string_view a_rhs);
}

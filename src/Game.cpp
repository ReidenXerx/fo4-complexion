#include "Game.h"

namespace SH::Game
{
	namespace
	{
		constexpr auto kFolder = "Data/F4SE/Plugins/Silhouette"sv;
		constexpr auto kTemplates = "Data/F4SE/Plugins/F4EE/BodyGen/Loose/Silhouette_templates.ini"sv;

		// The two character-creation dummies (Fallout4.esm). LooksMenu CLONES the chosen one's body
		// onto the player when character creation ends, so nothing of ours may ever be on them.
		constexpr std::uint32_t kSpouseMale = 0x0A7D34;
		constexpr std::uint32_t kSpouseFemale = 0x0A7D35;

		struct Resolved
		{
			std::vector<std::pair<RE::TESFaction*, FormRef>> factions;  // the faction rules' factions
			std::unordered_set<std::uint32_t>                 blacklist;  // ORefit, runtime form ids
			std::unordered_set<std::uint32_t>                 force;
			std::uint32_t                                     clothedMask{ 0 };
		};

		struct Inbox
		{
			struct Equip
			{
				std::uint32_t ref;
				std::uint32_t item;
				bool          equipped;
			};

			std::mutex                 lock;
			std::vector<std::uint32_t> loaded;
			std::vector<Equip>         equips;
		};

		Director                 g_director;
		Resolved                 g_resolved;
		Inbox                    g_inbox;
		std::atomic<std::uint32_t> g_crosshair{ 0 };
		std::atomic<std::uint32_t> g_lastAimed{ 0 };
		std::atomic<std::int64_t>  g_lastAimedMs{ 0 };

		std::int64_t NowMs()
		{
			return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
		}

		std::optional<nlohmann::json> ReadJson(const std::filesystem::path& a_path, std::string& a_error)
		{
			std::ifstream in(a_path, std::ios::binary);
			if (!in) {
				a_error = std::format("{} is missing", a_path.generic_string());
				return std::nullopt;
			}
			try {
				return nlohmann::json::parse(in);
			} catch (const std::exception& e) {
				a_error = std::format("{} is not valid JSON: {}", a_path.generic_string(), e.what());
				return std::nullopt;
			}
		}

		// The header the generator writes on the BodyGen templates: "... Build <hex>, marker stamp <n> ...".
		std::optional<std::pair<std::string, std::uint32_t>> TemplatesBuild(std::string& a_error)
		{
			std::ifstream in{ std::filesystem::path{ kTemplates } };
			if (!in) {
				a_error = std::format("{} is missing: Silhouette's BodyGen files are not installed", kTemplates);
				return std::nullopt;
			}
			std::string line;
			for (int i = 0; i < 12 && std::getline(in, line); ++i) {
				const auto b = line.find("Build ");
				const auto s = line.find("marker stamp ");
				if (b == std::string::npos || s == std::string::npos) {
					continue;
				}
				auto       build = line.substr(b + 6);
				const auto comma = build.find(',');
				build = build.substr(0, comma);
				std::uint32_t stamp = 0;
				const auto    digits = line.c_str() + s + 13;
				const auto [end, ec] = std::from_chars(digits, line.c_str() + line.size(), stamp);
				if (ec == std::errc{} && !build.empty()) {
					return std::make_pair(build, stamp);
				}
			}
			a_error = std::format("{} names no build in its header", kTemplates);
			return std::nullopt;
		}

		std::uint32_t Resolve(const FormRef& a_ref)
		{
			auto* dh = RE::TESDataHandler::GetSingleton();
			auto* form = dh ? dh->LookupForm(a_ref.id, a_ref.plugin) : nullptr;
			return form ? form->GetFormID() : 0;
		}

		std::string PluginOf(const RE::TESForm* a_form)
		{
			const auto* file = a_form ? a_form->GetFile(0) : nullptr;
			return file ? std::string{ file->filename } : std::string{};
		}

		std::string NameOfForm(const RE::TESForm* a_form)
		{
			return a_form ? std::string{ RE::TESFullName::GetFullName(*a_form) } : std::string{};
		}

		// Loaded as far as a body is concerned: the biped is built with the 3D and let go with it. A
		// member read, where Get3D() would be a virtual call on a table this library maps by hand.
		bool Has3D(RE::Actor* a_actor)
		{
			const auto& biped = a_actor->biped;
			return biped && biped->root;
		}

		// TESObjectARMO has GetFilledSlots twice over (two of its bases); the biped object form's is
		// the one that says which slots it takes.
		std::uint32_t SlotsOf(const RE::TESObjectARMO* a_item)
		{
			return static_cast<const RE::BGSBipedObjectForm*>(a_item)->GetFilledSlots();
		}

		RE::TESObjectARMO* SkinOf(RE::Actor* a_actor)
		{
			auto* npc = a_actor->GetNPC();
			if (npc && npc->formSkin) {
				return npc->formSkin;
			}
			return a_actor->race ? a_actor->race->formSkin : nullptr;
		}

		struct Worn
		{
			bool        clothed{ false };
			std::string outfitSet;
			bool        changingDresses{ false };  // the event's item is one that dresses them
		};

		bool Dresses(const Catalog& a_catalog, RE::TESObjectARMO* a_item)
		{
			const auto id = a_item->GetFormID();
			const auto name = NameOfForm(a_item);
			const bool forced = g_resolved.force.contains(id) ||
			                    std::ranges::any_of(a_catalog.forceRefitNames, [&](const std::string& n) { return IEquals(n, name); });
			if (forced) {
				return true;
			}
			if ((SlotsOf(a_item) & g_resolved.clothedMask) == 0) {
				return false;
			}
			const bool blacklisted = g_resolved.blacklist.contains(id) ||
			                         std::ranges::any_of(a_catalog.outfitBlacklistNames, [&](const std::string& n) { return IEquals(n, name); }) ||
			                         std::ranges::any_of(a_catalog.outfitBlacklistPlugins, [&](const std::string& p) { return IEquals(p, PluginOf(a_item)); });
			return !blacklisted;
		}

		// What they wear, from the biped, as OBody decides it (S-20): the item of the equip event
		// being handled counts as already off or already on, since the biped may not show it yet.
		Worn ReadWorn(RE::Actor* a_actor, const Catalog& a_catalog, bool a_female, RE::TESForm* a_changing, bool a_equipping)
		{
			std::array<RE::TESObjectARMO*, 32> bySlot{};
			if (const auto& biped = a_actor->biped; biped) {
				for (std::size_t i = 0; i < bySlot.size(); ++i) {
					auto* form = biped->object[i].parent.object;
					bySlot[i] = form && form->Is(RE::ENUM_FORM_ID::kARMO) ? static_cast<RE::TESObjectARMO*>(form) : nullptr;
				}
			}
			auto* changing = a_changing && a_changing->Is(RE::ENUM_FORM_ID::kARMO) ? static_cast<RE::TESObjectARMO*>(a_changing) : nullptr;
			if (changing) {
				if (a_equipping) {
					const auto slots = SlotsOf(changing);
					for (std::size_t i = 0; i < bySlot.size(); ++i) {
						if (slots & (1u << i)) {
							bySlot[i] = changing;
						}
					}
				} else {
					for (auto& item : bySlot) {
						if (item == changing) {
							item = nullptr;
						}
					}
				}
			}

			Worn       worn;
			const auto skin = SkinOf(a_actor);
			std::unordered_set<RE::TESObjectARMO*> checked;
			for (auto* item : bySlot) {
				if (!item || item == skin || !checked.insert(item).second) {
					continue;
				}
				if (Dresses(a_catalog, item)) {
					worn.clothed = true;
					break;
				}
			}
			if (worn.clothed) {
				for (const int slot : a_catalog.clothedSlots) {
					auto* item = bySlot[static_cast<std::size_t>(slot - 30)];
					if (!item || item == skin) {
						continue;
					}
					if (auto set = a_catalog.OutfitRefitSet(NameOfForm(item), a_female); !set.empty()) {
						worn.outfitSet = std::move(set);
						break;
					}
				}
			}
			worn.changingDresses = changing && changing != skin && Dresses(a_catalog, changing);
			return worn;
		}

		std::optional<Sighting> Read(RE::Actor* a_actor, const Catalog& a_catalog, RE::TESForm* a_changing, bool a_equipping, bool* a_changingDresses)
		{
			auto* npc = a_actor ? a_actor->GetNPC() : nullptr;
			if (!npc) {
				return std::nullopt;
			}
			Sighting s;
			s.ref = a_actor->GetFormID();
			s.base = npc->GetFormID();
			s.facts.female = npc->GetSex() == RE::SEX::kFemale;
			s.facts.seed = s.ref;
			if (const char* name = a_actor->GetDisplayFullName(); name) {
				s.facts.baseName = name;
			}
			s.eligible = a_actor != RE::PlayerCharacter::GetSingleton();

			// The record and every template up its chain, as BodyGen matches a form-id line.
			int depth = 0;
			for (auto* n = npc; n && depth < 16; n = n->faceNPC, ++depth) {
				if (const auto* file = n->GetFile(0)) {
					const auto local = n->GetLocalFormID();
					s.facts.bases.push_back(FormRef{ file->filename, local });
					if (s.facts.originPlugin.empty()) {
						s.facts.originPlugin = file->filename;
					}
					if (IEquals(file->filename, "Fallout4.esm") && (local == kSpouseMale || local == kSpouseFemale)) {
						s.eligible = false;
					}
				}
				for (const auto& [faction, ref] : g_resolved.factions) {
					if (faction && n->IsInFaction(faction) &&
						std::ranges::none_of(s.facts.factions, [&](const FormRef& f) { return f.Is(ref.plugin, ref.id); })) {
						s.facts.factions.push_back(ref);
					}
				}
			}
			if (a_actor->race) {
				if (const char* edid = a_actor->race->GetFormEditorID(); edid) {
					s.facts.race = edid;
				}
			}
			const auto worn = ReadWorn(a_actor, a_catalog, s.facts.female, a_changing, a_equipping);
			s.clothed = worn.clothed;
			s.outfitSet = worn.outfitSet;
			if (a_changingDresses) {
				*a_changingDresses = worn.changingDresses;
			}
			return s;
		}
	}

	Director& TheDirector()
	{
		return g_director;
	}

	void Load()
	{
		std::string error;
		const auto  doc = ReadJson(std::filesystem::path{ kFolder } / "catalog.json", error);
		if (!doc) {
			logger::error("catalog: {} - rules, ORefit and the picker are off (BodyGen still gives bodies)", error);
			g_director.Refuse(std::format("no catalog: {}", error));
			return;
		}
		auto catalog = ParseCatalog(*doc, error);
		if (!catalog) {
			logger::error("catalog refused: {}", error);
			g_director.Refuse(std::format("catalog refused: {}", error));
			return;
		}

		// The catalog and the BodyGen files come from one generator run, or neither can be trusted:
		// a marker would name a preset of another build (S-19).
		const auto templates = TemplatesBuild(error);
		if (!templates) {
			logger::error("catalog: {}", error);
			g_director.Refuse(error);
			return;
		}
		if (templates->first != catalog->build || templates->second != catalog->stamp) {
			const auto why = std::format("the catalog is build {} (stamp {}) but the BodyGen files are build {} (stamp {}): install one generator run's files together",
				catalog->build, catalog->stamp, templates->first, templates->second);
			logger::error("catalog refused: {}", why);
			g_director.Refuse(why);
			return;
		}

		std::size_t manifests = 0;
		std::error_code ec;
		for (const auto& entry : std::filesystem::directory_iterator(std::filesystem::path{ kFolder } / "manifests", ec)) {
			if (entry.path().extension() != ".json") {
				continue;
			}
			std::string merror;
			const auto  m = ReadJson(entry.path(), merror);
			auto        parsed = m ? ParseManifest(*m, merror) : std::nullopt;
			if (!parsed) {
				logger::warn("manifest {}: {}", entry.path().filename().string(), merror);
				continue;
			}
			catalog->AddManifest(parsed->first, std::move(parsed->second));
			++manifests;
		}

		g_resolved = {};
		for (const auto& rule : catalog->factionRules) {
			auto* dh = RE::TESDataHandler::GetSingleton();
			auto* faction = dh ? dh->LookupForm<RE::TESFaction>(rule.faction.id, rule.faction.plugin) : nullptr;
			if (!faction) {
				logger::warn("faction rule {} ({}|{:X}): not in this load order - the rule never matches", rule.editorID, rule.faction.plugin, rule.faction.id);
			}
			g_resolved.factions.emplace_back(faction, rule.faction);
		}
		for (const auto& f : catalog->outfitBlacklist) {
			if (const auto id = Resolve(f)) {
				g_resolved.blacklist.insert(id);
			}
		}
		for (const auto& f : catalog->forceRefit) {
			if (const auto id = Resolve(f)) {
				g_resolved.force.insert(id);
			}
		}
		for (const int slot : catalog->clothedSlots) {
			g_resolved.clothedMask |= 1u << (slot - 30);
		}

		logger::info("catalog: build {}, stamp {}, {} presets, {} manifest(s), {} faction rule(s)",
			catalog->build, catalog->stamp, catalog->presets.size(), manifests, catalog->factionRules.size());
		g_director.SetCatalog(std::make_shared<const Catalog>(std::move(*catalog)));
		logger::info("{}", g_director.Status());
	}

	void NoteLoaded(std::uint32_t a_ref)
	{
		std::scoped_lock l{ g_inbox.lock };
		if (g_inbox.loaded.size() < 4096) {
			g_inbox.loaded.push_back(a_ref);
		}
	}

	void NoteEquip(std::uint32_t a_ref, std::uint32_t a_item, bool a_equipped)
	{
		std::scoped_lock l{ g_inbox.lock };
		if (g_inbox.equips.size() < 4096) {
			g_inbox.equips.push_back({ a_ref, a_item, a_equipped });
		}
	}

	void NoteCrosshair(std::uint32_t a_ref)
	{
		g_crosshair.store(a_ref);
		if (a_ref != 0) {
			g_lastAimed.store(a_ref);
			g_lastAimedMs.store(NowMs());
		}
	}

	void ForgetInbox()
	{
		std::scoped_lock l{ g_inbox.lock };
		g_inbox.loaded.clear();
		g_inbox.equips.clear();
		g_crosshair.store(0);
		g_lastAimed.store(0);
	}

	RE::Actor* ActorFor(std::uint32_t a_ref)
	{
		if (a_ref == 0) {
			return nullptr;
		}
		auto* form = RE::TESForm::GetFormByID(a_ref);
		if (!form || !form->Is(RE::ENUM_FORM_ID::kACHR)) {
			return nullptr;
		}
		return static_cast<RE::Actor*>(form);
	}

	bool IsFemale(RE::Actor* a_actor)
	{
		auto* npc = a_actor ? a_actor->GetNPC() : nullptr;
		return npc && npc->GetSex() == RE::SEX::kFemale;
	}

	std::uint32_t BaseOf(RE::Actor* a_actor)
	{
		auto* npc = a_actor ? a_actor->GetNPC() : nullptr;
		return npc ? npc->GetFormID() : 0;
	}

	std::string NameOf(RE::Actor* a_actor)
	{
		const char* name = a_actor ? a_actor->GetDisplayFullName() : nullptr;
		return name ? std::string{ name } : std::string{};
	}

	void Pump()
	{
		std::vector<std::uint32_t> loaded;
		std::vector<Inbox::Equip>  equips;
		{
			std::scoped_lock l{ g_inbox.lock };
			loaded.swap(g_inbox.loaded);
			equips.swap(g_inbox.equips);
		}
		const auto catalog = g_director.CatalogPtr();
		if (catalog) {
			std::unordered_set<std::uint32_t> done;
			for (const auto ref : loaded) {
				if (!done.insert(ref).second) {
					continue;
				}
				auto* actor = ActorFor(ref);
				if (!actor || !Has3D(actor)) {
					continue;
				}
				if (const auto s = Read(actor, *catalog, nullptr, false, nullptr)) {
					g_director.Seen(*s);
				}
			}
			for (const auto& e : equips) {
				auto* actor = ActorFor(e.ref);
				if (!actor || !Has3D(actor)) {
					continue;  // no biped to read: they are read again when they load
				}
				auto* item = RE::TESForm::GetFormByID(e.item);
				bool  dresses = false;
				if (const auto s = Read(actor, *catalog, item, e.equipped, &dresses)) {
					g_director.Dressed(*s, !e.equipped && dresses);
				}
			}
		}
		FlushLog();
	}

	std::uint32_t CrosshairActor(float a_recentSeconds)
	{
		auto ref = g_crosshair.load();
		if (ref == 0 && a_recentSeconds > 0.0F && NowMs() - g_lastAimedMs.load() <= static_cast<std::int64_t>(a_recentSeconds * 1000.0F)) {
			ref = g_lastAimed.load();
		}
		auto* actor = ActorFor(ref);
		if (!actor || actor == RE::PlayerCharacter::GetSingleton() || !actor->GetNPC()) {
			return 0;
		}
		return ref;
	}

	void FlushLog()
	{
		for (const auto& line : g_director.TakeLog()) {
			logger::info("{}", line);
		}
	}
}

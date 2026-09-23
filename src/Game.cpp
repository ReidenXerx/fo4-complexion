#include "Game.h"

namespace SH::Game
{
	namespace
	{
		constexpr auto kFolder = "Data/F4SE/Plugins/Silhouette"sv;
		constexpr auto kTemplates = "Data/F4SE/Plugins/F4EE/BodyGen/Loose/Silhouette_templates.ini"sv;
		constexpr auto kMorphs = "Data/F4SE/Plugins/F4EE/BodyGen/Loose/Silhouette_morphs.ini"sv;

		// The two character-creation dummies (Fallout4.esm). LooksMenu CLONES the chosen one's body
		// onto the player when character creation ends, so nothing of ours may ever be on them.
		constexpr std::uint32_t kSpouseMale = 0x0A7D34;
		constexpr std::uint32_t kSpouseFemale = 0x0A7D35;

		// Power armour (Fallout4.esm): a frame is a machine an NPC climbs into, not clothes (L5 #8).
		constexpr std::uint32_t kPowerArmorFrameKeyword = 0x15503F;  // isPowerArmorFrame
		constexpr std::uint32_t kPowerArmorPieceKeyword = 0x04D8A1;  // ArmorTypePower

		constexpr std::size_t  kInboxLimit = 4096;
		constexpr std::int64_t kSilentBridgeMs = 60'000;
		constexpr std::int64_t kSummaryMs = 30'000;

		struct Resolved
		{
			std::vector<std::pair<RE::TESFaction*, FormRef>> factions;  // the faction rules' factions
			std::unordered_set<std::uint32_t>                 blacklist;  // ORefit, runtime form ids
			std::unordered_set<std::uint32_t>                 force;
			std::unordered_set<std::uint32_t>                 heavy;  // S-48: the explicit lists
			std::unordered_set<std::uint32_t>                 light;
			std::uint32_t                                     clothedMask{ 0 };
			std::array<const RE::BGSKeyword*, 2>              powerArmor{};
			std::unordered_map<std::uint32_t, bool>           heavyOf;  // each item decided once (main thread only)
		};

		struct Inbox
		{
			struct Equip
			{
				std::uint32_t ref;
				std::uint32_t item;
				bool          equipped;
			};

			std::mutex                lock;
			std::deque<std::uint32_t> loaded;
			std::deque<Equip>         equips;
			std::size_t               dropped{ 0 };  // since the last load
			bool                      warned{ false };
		};

		Director                   g_director;
		Resolved                   g_resolved;
		Inbox                      g_inbox;
		std::atomic<std::uint32_t> g_crosshair{ 0 };
		std::atomic<std::uint32_t> g_lastAimed{ 0 };
		std::atomic<std::int64_t>  g_lastAimedMs{ 0 };
		std::atomic<std::int64_t>  g_loadedMs{ 0 };  // when the last load finished, 0 before any
		std::atomic<std::int64_t>  g_pumpedMs{ 0 };  // the bridge's last poll
		std::atomic<bool>          g_watching{ false };
		std::int64_t               g_summaryMs{ 0 };  // main thread: the last summary line

		std::int64_t NowMs()
		{
			return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
		}

		bool AnyIEquals(const std::vector<std::string>& a_list, std::string_view a_name)
		{
			return std::ranges::any_of(a_list, [&](const std::string& n) { return IEquals(n, a_name); });
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

		std::optional<FilesHeader> ReadHeader(std::string_view a_file, std::string& a_error)
		{
			std::ifstream in{ std::filesystem::path{ a_file } };
			if (!in) {
				a_error = std::format("{} is missing: Silhouette's BodyGen files are not installed", a_file);
				return std::nullopt;
			}
			auto header = ParseFilesHeader(in);
			if (!header) {
				a_error = std::format("{} names no build in its header", a_file);
			}
			return header;
		}

		std::uint32_t Resolve(const FormRef& a_ref)
		{
			auto* dh = RE::TESDataHandler::GetSingleton();
			auto* form = dh ? dh->LookupForm(a_ref.id, a_ref.plugin) : nullptr;
			return form ? form->GetFormID() : 0;
		}

		std::unordered_set<std::uint32_t> ResolveAll(const std::vector<FormRef>& a_refs)
		{
			std::unordered_set<std::uint32_t> out;
			for (const auto& f : a_refs) {
				if (const auto id = Resolve(f)) {
					out.insert(id);
				}
			}
			return out;
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

		// The item's own keywords, read from the members: no virtual call on a table mapped by hand.
		bool HasKeyword(const RE::TESObjectARMO* a_item, const RE::BGSKeyword* a_keyword)
		{
			const auto* form = static_cast<const RE::BGSKeywordForm*>(a_item);
			if (!a_keyword || !form->keywords) {
				return false;
			}
			for (std::uint32_t i = 0; i < form->numKeywords; ++i) {
				if (form->keywords[i] == a_keyword) {
					return true;
				}
			}
			return false;
		}

		bool PowerArmor(const RE::TESObjectARMO* a_item)
		{
			return std::ranges::any_of(g_resolved.powerArmor, [&](const RE::BGSKeyword* k) { return HasKeyword(a_item, k); });
		}

		// A race's editor id, from the member (as LooksMenu reads it): the virtual getter returns "" for
		// most forms on this runtime.
		std::string RaceName(const RE::TESRace* a_race)
		{
			const char* edid = a_race ? a_race->formEditorID.c_str() : nullptr;
			return edid ? std::string{ edid } : std::string{};
		}

		bool IsDummy(RE::TESNPC* a_npc)
		{
			int depth = 0;
			for (auto* n = a_npc; n && depth < 16; n = n->faceNPC, ++depth) {
				const auto* file = n->GetFile(0);
				if (file && IEquals(file->filename, "Fallout4.esm")) {
					const auto local = n->GetLocalFormID();
					if (local == kSpouseMale || local == kSpouseFemale) {
						return true;
					}
				}
			}
			return false;
		}

		// Every skin the actor's body could be: the record's, each template's up the chain, the race's.
		// The one on the biped is not clothing, whichever of them it is -- counting a template's skin as
		// clothes would refit a naked woman.
		std::vector<RE::TESObjectARMO*> SkinsOf(RE::Actor* a_actor)
		{
			std::vector<RE::TESObjectARMO*> out;
			int                             depth = 0;
			for (auto* n = a_actor->GetNPC(); n && depth < 16; n = n->faceNPC, ++depth) {
				if (n->formSkin) {
					out.push_back(n->formSkin);
				}
			}
			if (a_actor->race && a_actor->race->formSkin) {
				out.push_back(a_actor->race->formSkin);
			}
			return out;
		}

		struct Worn
		{
			bool        clothed{ false };
			bool        heavy{ false };
			std::string outfitSet;
			bool        removing{ false };  // the event's item comes off a body, chest or pelvis slot
		};

		bool Dresses(const Catalog& a_catalog, RE::TESObjectARMO* a_item)
		{
			const auto id = a_item->GetFormID();
			const auto name = NameOfForm(a_item);
			if (g_resolved.force.contains(id) || AnyIEquals(a_catalog.forceRefitNames, name)) {
				return true;
			}
			if ((SlotsOf(a_item) & g_resolved.clothedMask) == 0 || PowerArmor(a_item)) {
				return false;
			}
			const bool blacklisted = g_resolved.blacklist.contains(id) || AnyIEquals(a_catalog.outfitBlacklistNames, name) ||
			                         AnyIEquals(a_catalog.outfitBlacklistPlugins, PluginOf(a_item));
			return !blacklisted;
		}

		// S-48: heavy only where it is plain. The catalog's lists decide first; then a whole word or
		// phrase of the item's name from orefit.heavy.words ("armor", "jacket", ...). Whatever the name
		// does not say is light: a chest flattened under a shirt is worse than a nipple showing through a
		// coat. Each item is decided once, and a heavy or listed one says why in the log.
		bool Heavy(const Catalog& a_catalog, RE::TESObjectARMO* a_item)
		{
			const auto id = a_item->GetFormID();
			if (const auto it = g_resolved.heavyOf.find(id); it != g_resolved.heavyOf.end()) {
				return it->second;
			}
			const auto  name = NameOfForm(a_item);
			bool        heavy = false;
			std::string why;
			if (g_resolved.heavy.contains(id) || AnyIEquals(a_catalog.heavyNames, name)) {
				heavy = true;
				why = "listed as heavy";
			} else if (g_resolved.light.contains(id) || AnyIEquals(a_catalog.lightNames, name)) {
				why = "listed as light";
			} else if (auto word = a_catalog.HeavyWord(name); !word.empty()) {
				heavy = true;
				why = std::format("the name says \"{}\"", word);
			}
			g_resolved.heavyOf.emplace(id, heavy);
			if (!why.empty()) {
				logger::info("clothing {:08X} \"{}\" ({}): {} - {}", id, name, PluginOf(a_item), heavy ? "heavy" : "light", why);
			}
			return heavy;
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
			const auto skins = SkinsOf(a_actor);
			const auto skin = [&](RE::TESObjectARMO* a_item) { return std::ranges::find(skins, a_item) != skins.end(); };
			std::unordered_set<RE::TESObjectARMO*> checked;
			for (auto* item : bySlot) {
				if (!item || skin(item) || !checked.insert(item).second || !Dresses(a_catalog, item)) {
					continue;
				}
				worn.clothed = true;
				worn.heavy = worn.heavy || Heavy(a_catalog, item);
			}
			if (worn.clothed) {
				for (const int slot : a_catalog.clothedSlots) {
					auto* item = bySlot[static_cast<std::size_t>(slot - 30)];
					if (!item || skin(item)) {
						continue;
					}
					if (auto set = a_catalog.OutfitRefitSet(NameOfForm(item), a_female); !set.empty()) {
						worn.outfitSet = std::move(set);
						break;
					}
				}
			}
			// OBody raises OnActorRemovingClothes for whatever leaves the body, chest or pelvis slots,
			// whatever ORefit's own lists say about it.
			worn.removing = changing && !a_equipping && !skin(changing) && (SlotsOf(changing) & g_resolved.clothedMask) != 0;
			return worn;
		}

		std::optional<Sighting> Read(RE::Actor* a_actor, const Catalog& a_catalog, RE::TESForm* a_changing, bool a_equipping, bool* a_removing)
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
			// The NPC record's name, as OBody reads it: a reference renamed at runtime (Rapport names the
			// settlers it befriends) keeps the rule its record matched.
			s.facts.baseName = NameOfForm(npc);
			s.eligible = !NeverShaped(a_actor);

			// The record and every template up its chain, as BodyGen matches a form-id line; the plugin
			// of the chain's root, as BodyGen applies a plugin line (only to records with no template).
			int depth = 0;
			for (auto* n = npc; n && depth < 16; n = n->faceNPC, ++depth) {
				if (const auto* file = n->GetFile(0)) {
					s.facts.bases.push_back(FormRef{ file->filename, n->GetLocalFormID() });
					s.facts.originPlugin = file->filename;
				}
			}
			// The record's own factions, as OBody reads them. A leveled record that takes its factions
			// from a template already carries them; walking the chain could only add false matches.
			for (const auto& [faction, ref] : g_resolved.factions) {
				if (faction && npc->IsInFaction(faction) &&
					std::ranges::none_of(s.facts.factions, [&](const FormRef& f) { return f.Is(ref.plugin, ref.id); })) {
					s.facts.factions.push_back(ref);
				}
			}
			s.facts.race = RaceOf(a_actor);
			const auto worn = ReadWorn(a_actor, a_catalog, s.facts.female, a_changing, a_equipping);
			s.clothed = worn.clothed;
			s.heavy = worn.heavy;
			s.outfitSet = worn.outfitSet;
			if (a_removing) {
				*a_removing = worn.removing;
			}
			return s;
		}

		template <class T>
		void PushCapped(std::deque<T>& a_queue, T a_item)
		{
			if (a_queue.size() >= kInboxLimit) {
				a_queue.pop_front();  // the oldest: an actor seen again later is read again then
				++g_inbox.dropped;
			}
			a_queue.push_back(a_item);
		}

		void Watch()
		{
			for (;;) {
				std::this_thread::sleep_for(std::chrono::seconds{ 20 });
				auto loaded = g_loadedMs.load();
				if (loaded != 0 && g_pumpedMs.load() < loaded && NowMs() - loaded > kSilentBridgeMs) {
					// Once per load -- and not over a newer load's stamp, set while this one was being checked.
					if (g_loadedMs.compare_exchange_strong(loaded, 0)) {
						logger::warn("the bridge has not polled in the minute since the save loaded. If that goes on, check that Silhouette.esp is "
									 "enabled and its scripts are installed: until it polls, nobody is shaped one by one (BodyGen still gives bodies)");
					}
				}
			}
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

		// The catalog and the BodyGen files come from one generator run, or neither can be trusted: a
		// marker would name a preset of another build (S-19), or the runtime would apply rules the
		// BodyGen lines do not agree with.
		for (const auto file : { kTemplates, kMorphs }) {
			const auto header = ReadHeader(file, error);
			if (!header) {
				logger::error("catalog: {}", error);
				g_director.Refuse(error);
				return;
			}
			if (header->build != catalog->build || header->stamp != catalog->stamp || (!header->rules.empty() && header->rules != catalog->rulesHash)) {
				const auto why = std::format("the catalog is build {} (stamp {}, rules {}) but {} is build {} (stamp {}, rules {}): install one generator run's files together",
					catalog->build, catalog->stamp, catalog->rulesHash, file, header->build, header->stamp, header->rules.empty() ? "?" : header->rules);
				logger::error("catalog refused: {}", why);
				g_director.Refuse(why);
				return;
			}
		}

		// Walked with increment(ec): the range-for's ++ throws on an error, and a throw here would take
		// the game down at data load.
		std::size_t     manifests = 0;
		std::error_code ec;
		for (std::filesystem::directory_iterator it{ std::filesystem::path{ kFolder } / "manifests", ec }, end; !ec && it != end; it.increment(ec)) {
			const auto& path = it->path();
			if (path.extension() != ".json") {
				continue;
			}
			std::string merror;
			const auto  m = ReadJson(path, merror);
			auto        parsed = m ? ParseManifest(*m, merror) : std::nullopt;
			if (!parsed) {
				logger::warn("manifest {}: {}", path.filename().string(), merror);
				continue;
			}
			catalog->AddManifest(parsed->first, std::move(parsed->second));
			++manifests;
		}
		if (ec) {
			logger::warn("manifests: {} - bodies of older builds may not be named or healed", ec.message());
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
		g_resolved.blacklist = ResolveAll(catalog->outfitBlacklist);
		g_resolved.force = ResolveAll(catalog->forceRefit);
		g_resolved.heavy = ResolveAll(catalog->heavyItems);
		g_resolved.light = ResolveAll(catalog->lightItems);
		for (const int slot : catalog->clothedSlots) {
			g_resolved.clothedMask |= 1u << (slot - 30);
		}
		if (auto* dh = RE::TESDataHandler::GetSingleton()) {
			g_resolved.powerArmor = { dh->LookupForm<RE::BGSKeyword>(kPowerArmorFrameKeyword, "Fallout4.esm"sv),
				dh->LookupForm<RE::BGSKeyword>(kPowerArmorPieceKeyword, "Fallout4.esm"sv) };
		}
		if (!g_resolved.powerArmor[0] || !g_resolved.powerArmor[1]) {
			logger::warn("power armour keywords not found in Fallout4.esm: NPCs in power armour count as dressed");
		}

		logger::info("catalog: build {}, stamp {}, rules {}, {} presets, {} manifest(s), {} faction rule(s), {} refit set(s)",
			catalog->build, catalog->stamp, catalog->rulesHash, catalog->presets.size(), manifests, catalog->factionRules.size(), catalog->refitSets.size());
		g_director.SetCatalog(std::make_shared<const Catalog>(std::move(*catalog)));
		logger::info("{}", g_director.Status());
	}

	void NoteLoaded(std::uint32_t a_ref)
	{
		std::scoped_lock l{ g_inbox.lock };
		PushCapped(g_inbox.loaded, a_ref);
	}

	void NoteEquip(std::uint32_t a_ref, std::uint32_t a_item, bool a_equipped)
	{
		std::scoped_lock l{ g_inbox.lock };
		PushCapped(g_inbox.equips, Inbox::Equip{ a_ref, a_item, a_equipped });
	}

	void NoteCrosshair(std::uint32_t a_ref, bool a_actor)
	{
		const auto before = g_crosshair.exchange(a_ref);
		if (a_ref != 0 && a_actor) {
			g_lastAimed.store(a_ref);
			g_lastAimedMs.store(NowMs());
		} else if (before != 0 && before == g_lastAimed.load()) {
			// "Aimed at within the last N seconds" counts from when the crosshair LEFT them: a long look
			// followed by opening a menu is the case the window exists for.
			g_lastAimedMs.store(NowMs());
		}
	}

	void ForgetInbox()
	{
		std::scoped_lock l{ g_inbox.lock };
		g_inbox.loaded.clear();
		g_inbox.equips.clear();
		g_inbox.dropped = 0;
		g_inbox.warned = false;
		g_crosshair.store(0);
		g_lastAimed.store(0);
	}

	void NoteGameLoaded()
	{
		g_loadedMs.store(NowMs());
		if (!g_watching.exchange(true)) {
			std::thread{ Watch }.detach();
		}
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

	bool NeverShaped(RE::Actor* a_actor)
	{
		return !a_actor || a_actor == RE::PlayerCharacter::GetSingleton() || IsDummy(a_actor->GetNPC());
	}

	std::string RaceOf(RE::Actor* a_actor)
	{
		auto* npc = a_actor ? a_actor->GetNPC() : nullptr;
		return RaceName(npc && npc->formRace ? npc->formRace : (a_actor ? a_actor->race : nullptr));
	}

	void Pump()
	{
		g_pumpedMs.store(NowMs());
		std::deque<std::uint32_t> loaded;
		std::deque<Inbox::Equip>  equips;
		std::size_t               dropped = 0;
		{
			std::scoped_lock l{ g_inbox.lock };
			loaded.swap(g_inbox.loaded);
			equips.swap(g_inbox.equips);
			if (g_inbox.dropped != 0 && !g_inbox.warned) {
				g_inbox.warned = true;
				dropped = g_inbox.dropped;
			}
		}
		if (dropped != 0) {
			logger::warn("the bridge fell behind: {} actor event(s) dropped, the oldest first; those actors are read again when they next load", dropped);
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
				auto* item = RE::TESForm::GetFormByID(e.item);
				if (!item || !item->Is(RE::ENUM_FORM_ID::kARMO)) {
					continue;  // a weapon, ammunition, aid: nothing anyone wears
				}
				auto* actor = ActorFor(e.ref);
				if (!actor || !Has3D(actor)) {
					continue;  // no biped to read: they are read again when they load
				}
				bool removing = false;
				if (const auto s = Read(actor, *catalog, item, e.equipped, &removing)) {
					g_director.Dressed(*s, removing);
				}
			}
		}
		FlushLog();
		// What the bridge did, every half minute while there is anything to say (L5 #2).
		if (const auto now = NowMs(); now - g_summaryMs >= kSummaryMs) {
			g_summaryMs = now;
			if (const auto line = g_director.TakeSummary(); !line.empty()) {
				logger::info("{}", line);
			}
		}
	}

	std::uint32_t CrosshairActor(float a_recentSeconds)
	{
		auto ref = g_crosshair.load();
		if (!ActorFor(ref) && a_recentSeconds > 0.0F && NowMs() - g_lastAimedMs.load() <= static_cast<std::int64_t>(a_recentSeconds * 1000.0F)) {
			ref = g_lastAimed.load();
		}
		auto* actor = ActorFor(ref);
		if (!actor || NeverShaped(actor) || !actor->GetNPC()) {
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

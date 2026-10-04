#include "Game.h"

#include "Compat.h"
#include "Crosshair.h"
#include "EventSources.h"

namespace CX::Game
{
	namespace
	{
		constexpr auto kFolder = "Data/F4SE/Plugins/Complexion"sv;
		constexpr auto kOverlays = "Data/F4SE/Plugins/F4EE/Overlays"sv;

		// The two character-creation dummies (Fallout4.esm): LooksMenu clones the chosen one onto the player.
		constexpr std::uint32_t kSpouseMale = 0x0A7D34;
		constexpr std::uint32_t kSpouseFemale = 0x0A7D35;

		constexpr std::size_t  kInboxLimit = 4096;
		constexpr std::int64_t kSilentBridgeMs = 60'000;
		constexpr std::int64_t kSweepMs = 30'000;

		// The races whose body the overlays are painted for (the human body's UV). Children, ghouls, synths of
		// the old models and creatures are left alone.
		constexpr std::array kRaces{ "HumanRace"sv };

		struct GroupFactions
		{
			std::string                       group;
			std::vector<RE::TESFaction*>      factions;
			std::unordered_set<std::uint32_t> members;  // a named character's NPC records, runtime form ids
		};

		struct Inbox
		{
			std::mutex                lock;
			std::deque<std::uint32_t> loaded;
			std::size_t               dropped{ 0 };
			bool                      warned{ false };
		};

		Director                   g_director;
		std::vector<GroupFactions> g_groups;  // in the profiles' order: the first that matches wins
		bool                       g_loaded{ false };
		Inbox                      g_inbox;
		std::atomic<std::int64_t>  g_loadedMs{ 0 };
		std::atomic<std::int64_t>  g_pumpedMs{ 0 };
		std::atomic<std::int64_t>  g_askedMs{ 0 };
		std::atomic<bool>          g_watching{ false };
		std::mutex                 g_warningLock;
		std::string                g_warning;
		std::string                g_notice;

		bool                              g_rofLoaded{ false };
		bool                              g_rofChecked{ false };

		bool                              g_sweepArmed{ false };
		std::int64_t                      g_sweepUntilMs{ 0 };
		std::unordered_set<std::uint32_t> g_swept;

		CrosshairTrail                    g_trail;  // the view caster's activate picks, as handles (C-19)

		std::int64_t NowMs()
		{
			return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
		}

		bool IEquals(std::string_view a, std::string_view b)
		{
			return a.size() == b.size() && std::ranges::equal(a, b, [](char x, char y) {
				return std::tolower(static_cast<unsigned char>(x)) == std::tolower(static_cast<unsigned char>(y));
			});
		}

		// A path for the log: path::string() throws for a name the ANSI code page cannot hold.
		std::string Utf8(const std::filesystem::path& a_path)
		{
			const auto u = a_path.generic_u8string();
			return { reinterpret_cast<const char*>(u.data()), u.size() };
		}

		std::optional<std::string> ReadText(const std::filesystem::path& a_path)
		{
			std::ifstream in(a_path, std::ios::binary);
			if (!in) {
				return std::nullopt;
			}
			return std::string{ std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>() };
		}

		// jsoncpp, which LooksMenu reads its files with, allows comments; so does this.
		std::optional<nlohmann::json> ReadJson(const std::filesystem::path& a_path, std::string& a_error)
		{
			const auto text = ReadText(a_path);
			if (!text) {
				a_error = std::format("{} is missing", Utf8(a_path));
				return std::nullopt;
			}
			try {
				return nlohmann::json::parse(*text, nullptr, true, true);
			} catch (const std::exception& e) {
				a_error = std::format("{} is not valid JSON: {}", Utf8(a_path), e.what());
				return std::nullopt;
			}
		}

		std::string NameOfForm(const RE::TESForm* a_form)
		{
			return a_form ? std::string{ RE::TESFullName::GetFullName(*a_form) } : std::string{};
		}

		bool Has3D(RE::Actor* a_actor)
		{
			const auto& biped = a_actor->biped;
			return biped && biped->root;
		}

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

		// The loaded plugins, as LooksMenu walks them: full plugins in load order, then light ones.
		std::vector<std::string> LoadedPlugins()
		{
			std::vector<std::string> out;
			auto* dh = RE::TESDataHandler::GetSingleton();
			if (!dh) {
				return out;
			}
			for (auto* f : dh->compiledFileCollection.files) {
				if (f) {
					out.emplace_back(f->filename);
				}
			}
			for (auto* f : dh->compiledFileCollection.smallFiles) {
				if (f) {
					out.emplace_back(f->filename);
				}
			}
			return out;
		}

		// The template keys LooksMenu holds ("f:<id>", "m:<id>"): OverlayInterface::LoadOverlayMods' order and
		// rules -- Overlays\<plugin file name>\overlays.json per loaded plugin, then Overlays\Loose\*.json; gender
		// above 1 is female; an entry with no gender or id is skipped; a file that does not parse is skipped whole.
		std::set<std::string> InstalledTemplates(const std::vector<std::string>& a_plugins, std::size_t& a_files)
		{
			std::set<std::string>              out;
			std::vector<std::filesystem::path> files;
			for (const auto& p : a_plugins) {
				std::filesystem::path f = std::filesystem::path(kOverlays) / std::filesystem::path(p) / "overlays.json";  // the game's own (ANSI) file name
				std::error_code       ec;
				if (std::filesystem::exists(f, ec)) {
					files.push_back(std::move(f));
				}
			}
			std::error_code ec;
			const auto      loose = std::filesystem::path(kOverlays) / "Loose";
			if (std::filesystem::is_directory(loose, ec)) {
				std::vector<std::filesystem::path> found;
				for (const auto& e : std::filesystem::directory_iterator(loose, ec)) {
					if (e.path().extension() == ".json") {
						found.push_back(e.path());
					}
				}
				std::ranges::sort(found);
				files.insert(files.end(), found.begin(), found.end());
			}
			for (const auto& f : files) {
				std::string error;
				const auto  json = ReadJson(f, error);
				if (!json || !json->is_array()) {
					logger::warn("overlays: {} (LooksMenu skips this file too)", error.empty() ? Utf8(f) + " is not a list" : error);
					continue;
				}
				++a_files;
				for (const auto& e : *json) {
					if (!e.is_object() || !e.contains("gender") || !e.contains("id") || !e["id"].is_string() || !e["gender"].is_number()) {
						continue;
					}
					const bool female = e["gender"].get<double>() >= 1;
					out.insert(std::string(female ? "f:" : "m:") + e["id"].get<std::string>());
				}
			}
			return out;
		}

		void Warn(std::string a_line)
		{
			std::scoped_lock l{ g_warningLock };
			g_warning += (g_warning.empty() ? "" : "\n\n") + a_line;
		}

		void Notify(std::string a_line)
		{
			std::scoped_lock l{ g_warningLock };
			g_notice = std::move(a_line);
		}

		void Sweep(std::deque<std::uint32_t>& a_loaded)
		{
			const auto lists = RE::ProcessLists::GetSingleton();
			if (!lists) {
				return;
			}
			for (const auto* handles : { &lists->highActorHandles, &lists->middleHighActorHandles }) {
				for (const auto& handle : *handles) {
					const auto ptr = handle.get();
					auto*      actor = ptr.get();
					if (actor && Has3D(actor) && g_swept.insert(actor->GetFormID()).second) {
						a_loaded.push_back(actor->GetFormID());
					}
				}
			}
		}

		// The members this plugin reads, checked once on the player before any is trusted (Silhouette S-75).
		enum class Layout
		{
			kUnchecked,
			kGood,
			kBad
		};
		Layout g_layout = Layout::kUnchecked;

		// The game's hair colour records -> their family (profiles.json hair_colours, resolved by tools/make_data.py).
		std::unordered_map<std::uint32_t, std::string> g_hairFamilies;

		// A record's head hair colour: its own, or up its face template chain (a generic NPC carries the face of the
		// record it was built from). Members only (rule 5); the layout check reads one on the player first.
		const RE::TESForm* HairColourOf(RE::TESNPC* a_npc)
		{
			int depth = 0;
			for (auto* n = a_npc; n && depth < 16; n = n->faceNPC, ++depth) {
				if (n->headRelatedData && n->headRelatedData->hairColor) {
					return reinterpret_cast<const RE::TESForm*>(n->headRelatedData->hairColor);
				}
			}
			return nullptr;
		}

		// Their skin tone from the record's body tint (TESNPC::bodyTintColor, the QNAM the game tints the body
		// with), up the face template chain: pale, light, olive or dark; "" when not read. Thresholds from the
		// game's own records: Cait 0.97 and the default 0.95 pale, Deacon 0.85 light, Amari 0.72 olive, Preston 0.56.
		std::string ToneOf(RE::TESNPC* a_npc)
		{
			if (g_layout != Layout::kGood) {
				return {};
			}
			int depth = 0;
			for (auto* n = a_npc; n && depth < 16; n = n->faceNPC, ++depth) {
				const auto r = static_cast<std::uint8_t>(n->bodyTintColorR);
				const auto g = static_cast<std::uint8_t>(n->bodyTintColorG);
				const auto b = static_cast<std::uint8_t>(n->bodyTintColorB);
				if (r == 0 && g == 0 && b == 0) {
					continue;  // no tint on this record: the next one up
				}
				const double l = (0.3 * r + 0.59 * g + 0.11 * b) / 255.0;
				return l >= 0.9 ? "pale" : l >= 0.78 ? "light" : l >= 0.66 ? "olive" : "dark";
			}
			return {};
		}

		// Their family, "" when the colour is not one of the game's (another mod's, a dye) or not read.
		std::string HairFamily(RE::TESNPC* a_npc)
		{
			if (g_layout != Layout::kGood) {
				return {};
			}
			const auto* colour = HairColourOf(a_npc);
			if (!colour) {
				return {};
			}
			const auto it = g_hairFamilies.find(colour->GetFormID());
			return it != g_hairFamilies.end() ? it->second : std::string{};
		}

		struct LayoutRun
		{
			std::vector<std::string> problems;
			bool                     complete{ false };
		};

		void CheckLayout(void* a_run)
		{
			auto& run = *static_cast<LayoutRun*>(a_run);
			auto* player = RE::PlayerCharacter::GetSingleton();
			if (!player) {
				return;
			}
			const auto is = [&](const void* a_form, RE::ENUM_FORM_ID a_type, std::string_view a_what, bool a_emptyOk) {
				if (!a_form) {
					if (!a_emptyOk) {
						run.problems.push_back(std::format("{} is empty", a_what));
					}
					return false;
				}
				const auto type = Events::SafeFormType(a_form);
				if (type != std::to_underlying(a_type)) {
					run.problems.push_back(std::format("{} is not the form it should be (type {})", a_what, type));
					return false;
				}
				return true;
			};
			auto*      npc = player->GetNPC();
			const bool npcOk = is(npc, RE::ENUM_FORM_ID::kNPC_, "the player's base record", false);
			const bool raceOk = is(player->race, RE::ENUM_FORM_ID::kRACE, "Actor::race", false);
			if (npcOk) {
				is(npc->formRace, RE::ENUM_FORM_ID::kRACE, "TESNPC::formRace", false);
				is(npc->faceNPC, RE::ENUM_FORM_ID::kNPC_, "TESNPC::faceNPC", true);
				// The body hair colour (0.1.3): a hair colour record where TESNPC::headRelatedData says, or none.
				if (const auto* colour = HairColourOf(npc)) {
					is(colour, RE::ENUM_FORM_ID::kCLFM, "TESNPC::headRelatedData->hairColor", false);
				}
				for (const auto& f : npc->factions) {
					if (!is(f.faction, RE::ENUM_FORM_ID::kFACT, "TESNPC::factions", false)) {
						break;
					}
				}
			}
			if (raceOk) {
				const auto edid = RaceName(player->race);
				if (edid.empty() || edid.size() > 128 || !std::ranges::all_of(edid, [](char c) { return c > 32 && c < 127; })) {
					run.problems.push_back(std::format("TESForm::formEditorID reads \"{}\" for the player's race", edid.substr(0, 40)));
				}
			}
			if (const auto lists = RE::ProcessLists::GetSingleton()) {
				std::size_t checked = 0;
				for (const auto& handle : lists->highActorHandles) {
					if (checked++ == 8) {
						break;
					}
					if (auto ptr = handle.get(); ptr && !is(ptr.get(), RE::ENUM_FORM_ID::kACHR, "ProcessLists::highActorHandles", false)) {
						break;
					}
				}
			}
			if (!Has3D(player)) {
				return;
			}
			run.complete = true;
		}

		void GuardLayout()
		{
			if (g_layout != Layout::kUnchecked) {
				return;
			}
			LayoutRun run;
			if (!Events::Guarded(&CheckLayout, &run)) {
				run.problems.push_back("a read faulted");
				run.complete = true;
			}
			if (!run.complete && run.problems.empty()) {
				return;
			}
			if (run.problems.empty()) {
				g_layout = Layout::kGood;
				logger::info("layout: every member Complexion reads checks out on this runtime");
				return;
			}
			g_layout = Layout::kBad;
			std::string all;
			for (const auto& p : run.problems) {
				all += (all.empty() ? "" : "; ") + p;
			}
			logger::error("layout: this game's classes are laid out differently from what Complexion.dll reads ({}) - Complexion is off. "
						  "Please report it with Complexion.log",
				all);
			g_director.SetEnabled(false);
		}

		std::optional<Facts> Read(RE::Actor* a_actor)
		{
			auto* npc = a_actor ? a_actor->GetNPC() : nullptr;
			if (!npc) {
				return std::nullopt;
			}
			Facts f;
			f.ref = a_actor->GetFormID();
			f.base = npc->GetFormID();
			f.female = Compat::Female(npc);
			f.name = std::format("{}", Compat::DisplayName(a_actor));
			if (a_actor == RE::PlayerCharacter::GetSingleton() || IsDummy(npc)) {
				f.skip = "player";
				return f;
			}
			const auto race = RaceName(npc->formRace ? npc->formRace : a_actor->race);
			if (std::ranges::none_of(kRaces, [&](std::string_view r) { return IEquals(r, race); })) {
				f.skip = "race " + race;
				return f;
			}
			f.hair = HairFamily(npc);
			f.tone = ToneOf(npc);
			// A named character first: their record, or any template up its chain.
			for (const auto& g : g_groups) {
				if (g.members.empty()) {
					continue;
				}
				int depth = 0;
				for (auto* n = npc; n && depth < 16; n = n->faceNPC, ++depth) {
					if (g.members.contains(n->GetFormID())) {
						f.group = g.group;
						return f;
					}
				}
			}
			// The record's own factions, as Silhouette's faction pools read them (a template's are carried by
			// the record it builds).
			for (const auto& g : g_groups) {
				if (std::ranges::any_of(g.factions, [&](RE::TESFaction* a_f) { return a_f && npc->IsInFaction(a_f); })) {
					f.group = g.group;
					break;
				}
			}
			return f;
		}

		void Watch()
		{
			for (;;) {
				std::this_thread::sleep_for(std::chrono::seconds{ 20 });
				auto loaded = g_loadedMs.load();
				if (loaded != 0 && g_pumpedMs.load() < loaded && NowMs() - loaded > kSilentBridgeMs && g_loadedMs.compare_exchange_strong(loaded, 0)) {
					if (g_askedMs.load() >= loaded) {
						logger::warn("Complexion's scripts answered but the bridge does not poll: Complexion.esp is not enabled, its scripts are "
									 "from another release than Complexion.dll, or LooksMenu is not loaded. Until it polls, nobody gets overlays");
					} else {
						logger::warn("the bridge has not polled in the minute since the save loaded: check that Complexion.esp is enabled, "
									 "its scripts are installed and LooksMenu is loaded");
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
		if (g_loaded) {
			return;
		}
		g_loaded = true;
		std::string error;
		const auto  profilesText = ReadText(std::filesystem::path(kFolder) / "profiles.json");
		auto        tags = ReadJson(std::filesystem::path(kFolder) / "tags.json", error);
		if (!profilesText || !tags) {
			const auto why = !profilesText ? std::string("Data/F4SE/Plugins/Complexion/profiles.json is missing") : error;
			logger::error("{} - Complexion hands out nothing", why);
			Warn(std::format("Complexion's own files are not installed ({}): nobody gets overlays. Reinstall Complexion.", why));
			return;
		}
		// A player's own tags for packs Complexion does not know: tags\*.json, in name order, the later file wins.
		std::error_code ec;
		const auto      includes = std::filesystem::path(kFolder) / "tags";
		if (std::filesystem::is_directory(includes, ec)) {
			std::vector<std::filesystem::path> found;
			for (const auto& e : std::filesystem::directory_iterator(includes, ec)) {
				if (e.path().extension() == ".json") {
					found.push_back(e.path());
				}
			}
			std::ranges::sort(found);
			for (const auto& f : found) {
				std::string e2;
				if (const auto more = ReadJson(f, e2); more && more->is_object()) {
					for (const auto& [k, v] : more->items()) {
						(*tags)[k] = v;
					}
					logger::info("tags: {} adds {} template(s)", Utf8(f), more->size());
				} else {
					logger::warn("tags: {}", e2.empty() ? Utf8(f) + " is not an object" : e2);
				}
			}
		}

		Profiles profiles;
		try {
			profiles = ParseProfiles(*profilesText);
		} catch (const std::exception& e) {
			logger::error("profiles.json: {} - Complexion hands out nothing", e.what());
			Warn(std::format("Complexion's profiles.json is broken ({}): nobody gets overlays.", e.what()));
			return;
		}

		const auto  plugins = LoadedPlugins();
		std::size_t files = 0;
		const auto  installed = InstalledTemplates(plugins, files);
		auto        catalog = ParseCatalog(*tags, installed);
		std::size_t female = 0;
		for (const auto& t : catalog) {
			female += t.female ? 1 : 0;
		}
		logger::info("overlays: LooksMenu loads {} template(s) from {} file(s); {} of them tagged and usable ({} female, {} male); "
					 "the others are never handed out at random",
			installed.size(), files, catalog.size(), female, catalog.size() - female);

		auto* dh = RE::TESDataHandler::GetSingleton();
		g_hairFamilies.clear();
		for (const auto& f : profiles.hairColours.forms) {
			auto* form = dh && f.id ? dh->LookupForm(f.id, f.plugin) : nullptr;
			if (form && form->Is(RE::ENUM_FORM_ID::kCLFM)) {
				g_hairFamilies[form->GetFormID()] = f.family;
			}
		}
		logger::info("hair: {} of the game's {} hair colour(s) known; body hair matches the head's", g_hairFamilies.size(),
			profiles.hairColours.forms.size());
		g_groups.clear();
		for (const auto& g : profiles.groups) {
			GroupFactions gf{ g.name, {}, {} };
			for (const auto& f : g.members) {
				auto* form = dh && f.id ? dh->LookupForm(f.id, f.plugin) : nullptr;
				if (form && form->Is(RE::ENUM_FORM_ID::kNPC_)) {
					gf.members.insert(form->GetFormID());
				}
			}
			for (const auto& f : g.factions) {
				auto* form = dh && f.id ? dh->LookupForm(f.id, f.plugin) : nullptr;
				if (form && form->Is(RE::ENUM_FORM_ID::kFACT)) {
					gf.factions.push_back(static_cast<RE::TESFaction*>(form));
				} else {
					logger::info("group {}: {}|{} ({:06X}) is not in this load order", g.name, f.plugin, f.editorID, f.id);
				}
			}
			g_groups.push_back(std::move(gf));
		}

		// C-11: ROF stays for its tattoo packs; Complexion's RobCo ini switches its distributor off. Checked at the
		// first poll, once RobCo Patcher has surely patched the races.
		g_rofLoaded = std::ranges::any_of(plugins, [](const std::string& p) { return IEquals(p, "INVB_OverlayFramework.esp"); });
		g_director.SetData(std::move(profiles), std::move(catalog));

		// C-19: where each of Complexion's own templates has its picture in the window's atlases
		// (tools/paint/thumbs.py). Without the file the window works, with text cards.
		std::string thumbError;
		if (const auto thumbs = ReadJson(std::filesystem::path(kFolder) / "thumbs.json", thumbError); thumbs && thumbs->is_object() &&
																										(*thumbs).contains("cells")) {
			std::unordered_map<std::string, std::pair<int, int>> cells;
			for (const auto& [k, v] : (*thumbs)["cells"].items()) {
				if (v.is_array() && v.size() == 2) {
					cells[k] = { v[0].get<int>(), v[1].get<int>() };
				}
			}
			std::unordered_map<std::string, std::array<float, 8>> spots;
			if ((*thumbs).contains("focus") && (*thumbs)["focus"].is_object()) {
				for (const auto& [k, v] : (*thumbs)["focus"].items()) {
					if (v.is_array() && v.size() == 8) {
						std::array<float, 8> a{};
						for (std::size_t i = 0; i < 8; ++i) {
							a[i] = v[i].get<float>();
						}
						spots[k] = a;
					}
				}
			}
			logger::info("window: {} picture(s) in the atlases, {} spot(s) for the camera", cells.size(), spots.size());
			g_director.SetThumbs(std::move(cells), (*thumbs).value("build", std::string{}));
			g_director.SetSpots(std::move(spots));
		} else {
			logger::info("window: no thumbs.json ({}) - the window shows text cards", thumbError.empty() ? "missing" : thumbError);
		}
	}

	std::string TakeWarning()
	{
		std::scoped_lock l{ g_warningLock };
		return std::exchange(g_warning, {});
	}

	std::string TakeNotice()
	{
		std::scoped_lock l{ g_warningLock };
		return std::exchange(g_notice, {});
	}

	void NoteLoaded(std::uint32_t a_ref)
	{
		std::scoped_lock l{ g_inbox.lock };
		if (g_inbox.loaded.size() >= kInboxLimit) {
			g_inbox.loaded.pop_front();
			++g_inbox.dropped;
		}
		g_inbox.loaded.push_back(a_ref);
	}

	void NoteCrosshair(std::uint32_t a_handle)
	{
		// "Aimed at within the last N seconds" counts from when the crosshair LEFT them: a long look followed by
		// opening a menu is the case the window exists for.
		g_trail.Note(a_handle, NowMs());
	}

	std::uint32_t CrosshairActor(float a_recentSeconds)
	{
		const auto recentMs = a_recentSeconds > 0.0F ? static_cast<std::int64_t>(a_recentSeconds * 1000.0F) : std::int64_t{ 0 };
		std::uint32_t chosen = 0;
		(void)g_trail.Choose(recentMs, NowMs(), [&](std::uint32_t a_handle) {
			if (a_handle == 0) {
				return false;
			}
			static_assert(sizeof(RE::ObjectRefHandle) == sizeof(std::uint32_t));
			RE::ObjectRefHandle handle;
			std::memcpy(static_cast<void*>(&handle), &a_handle, sizeof(a_handle));
			const auto ref = handle.get();
			auto*      actor = ref ? ActorFor(ref->GetFormID()) : nullptr;
			if (!actor || !actor->GetNPC() || actor == RE::PlayerCharacter::GetSingleton()) {
				return false;
			}
			chosen = actor->GetFormID();
			return true;
		});
		logger::info("window: {}", chosen ? std::format("aimed at {}", NameOf(ActorFor(chosen))) : std::string{ "nobody aimed at - the window opens on the player" });
		return chosen;
	}

	void ForgetInbox()
	{
		{
			std::scoped_lock l{ g_inbox.lock };
			g_inbox.loaded.clear();
			g_inbox.dropped = 0;
			g_inbox.warned = false;
		}
		g_trail.Forget();
		g_sweepArmed = false;
		g_sweepUntilMs = 0;
		g_swept.clear();
	}

	void NoteAsked()
	{
		g_askedMs.store(NowMs());
	}

	void See(RE::Actor* a_actor)
	{
		if (!a_actor || !Has3D(a_actor) || g_layout != Layout::kGood) {
			return;  // nobody is read before the layout check passed: their hair and skin would read as unknown
		}
		if (const auto f = Read(a_actor)) {
			g_director.Seen(*f);
		}
	}

	void NoteGameLoaded()
	{
		g_loadedMs.store(NowMs());
		if (!g_watching.exchange(true)) {
			std::thread{ Watch }.detach();
		}
	}

	void ArmSweep()
	{
		g_sweepArmed = true;
		g_sweepUntilMs = 0;
		g_swept.clear();
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

	std::string NameOf(RE::Actor* a_actor)
	{
		return Compat::DisplayName(a_actor);
	}

	std::string HairOf(RE::Actor* a_actor)
	{
		return a_actor ? HairFamily(a_actor->GetNPC()) : std::string{};
	}

	std::string ToneOfActor(RE::Actor* a_actor)
	{
		return a_actor ? ToneOf(a_actor->GetNPC()) : std::string{};
	}

	namespace
	{
		// The Human race carries ROF's three "already done" keywords (data/.../RobCo_Patcher/race/Complexion_ROF.ini):
		// ROF takes its own exit for everyone. Members only: the race's keyword list.
		void CheckROF()
		{
			if (!g_rofLoaded || g_rofChecked) {
				return;
			}
			g_rofChecked = true;
			auto* dh = RE::TESDataHandler::GetSingleton();
			auto* raceForm = dh ? dh->LookupForm(0x013746, "Fallout4.esm") : nullptr;
			std::size_t found = 0;
			if (raceForm && raceForm->Is(RE::ENUM_FORM_ID::kRACE)) {
				const auto* kw = static_cast<const RE::BGSKeywordForm*>(static_cast<RE::TESRace*>(raceForm));
				for (const std::uint32_t local : { 0x0052BDu, 0x000DCFu, 0x0055A7u }) {
					auto* want = dh->LookupForm(local, "INVB_OverlayFramework.esp");
					for (std::uint32_t i = 0; want && kw->keywords && i < kw->numKeywords && i < 512; ++i) {
						if (kw->keywords[i] == want) {
							++found;
							break;
						}
					}
				}
			}
			if (found == 3) {
				logger::info("Random Overlay Framework is loaded for its tattoo packs; its distributor is switched off (its own done-keywords on "
							 "the Human race, from Complexion_ROF.ini). Its old overlays stay until MCM > Complexion > Clear every overlay");
				Notify("Complexion: Random Overlay Framework switched off, its tattoos kept. Old ROF overlays: MCM > Complexion > Clear every overlay.");
			} else {
				logger::warn("Random Overlay Framework is loaded and still hands out overlays: {} of its 3 done-keywords are on the Human race "
							 "(RobCo Patcher missing, or F4SE/Plugins/RobCo_Patcher/race/Complexion_ROF.ini not installed)",
					found);
				Warn("Random Overlay Framework is loaded and still hands out overlays: Complexion could not switch it off (RobCo Patcher "
					 "is needed). Its overlays will stack on top of Complexion's. Install RobCo Patcher, or uninstall ROF.");
			}
		}
	}

	void Pump()
	{
		g_pumpedMs.store(NowMs());
		GuardLayout();
		if (g_layout != Layout::kGood) {
			return;  // bad: never; unchecked (the player's 3D not loaded yet): the next pump. What came in waits.
		}
		CheckROF();
		std::deque<std::uint32_t> loaded;
		std::size_t               dropped = 0;
		{
			std::scoped_lock l{ g_inbox.lock };
			loaded.swap(g_inbox.loaded);
			if (g_inbox.dropped != 0 && !g_inbox.warned) {
				g_inbox.warned = true;
				dropped = g_inbox.dropped;
			}
		}
		if (dropped != 0) {
			logger::warn("the bridge fell behind: {} actor event(s) dropped; those actors are read again when they next load", dropped);
		}
		// After a load in a running game the game reports nobody already around the player as loaded
		// (Silhouette S-43): for a while from the first poll, every actor it simulates is read once.
		if (g_sweepArmed) {
			const auto now = NowMs();
			if (g_sweepUntilMs == 0) {
				g_sweepUntilMs = now + kSweepMs;
			}
			if (now < g_sweepUntilMs) {
				Sweep(loaded);
			} else {
				g_sweepArmed = false;
				logger::info("after loading: {} actor(s) around the player read", g_swept.size());
			}
		}
		std::unordered_set<std::uint32_t> done;
		for (const auto ref : loaded) {
			if (!done.insert(ref).second) {
				continue;
			}
			See(ActorFor(ref));
		}
		FlushLog();
	}

	void FlushLog()
	{
		for (const auto& line : g_director.TakeLog()) {
			logger::info("{}", line);
		}
	}
}

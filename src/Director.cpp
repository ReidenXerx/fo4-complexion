#include "Director.h"

namespace CX
{
	namespace
	{
		// 2: a record carries the persona (C-14). 3: and whether it was chosen by hand (C-19). Older records load
		// with none.
		constexpr std::uint32_t kSaveVersion = 4;  // 4: the record's hair family

		std::uint64_t Mix(std::uint64_t a_z)
		{
			a_z = (a_z ^ (a_z >> 30)) * 0xBF58476D1CE4E5B9ull;
			a_z = (a_z ^ (a_z >> 27)) * 0x94D049BB133111EBull;
			return a_z ^ (a_z >> 31);
		}

		// The co-save bytes: little-endian, length-prefixed strings.
		class Writer
		{
		public:
			void U8(std::uint8_t a_v) { _b.push_back(a_v); }
			void U32(std::uint32_t a_v)
			{
				for (int i = 0; i < 4; ++i) {
					_b.push_back(static_cast<std::uint8_t>(a_v >> (8 * i)));
				}
			}
			void U64(std::uint64_t a_v)
			{
				U32(static_cast<std::uint32_t>(a_v));
				U32(static_cast<std::uint32_t>(a_v >> 32));
			}
			void I32(std::int32_t a_v) { U32(static_cast<std::uint32_t>(a_v)); }
			void Str(std::string_view a_s)
			{
				U32(static_cast<std::uint32_t>(a_s.size()));
				_b.insert(_b.end(), a_s.begin(), a_s.end());
			}
			std::vector<std::uint8_t> Take() { return std::move(_b); }

		private:
			std::vector<std::uint8_t> _b;
		};

		class Reader
		{
		public:
			explicit Reader(std::span<const std::uint8_t> a_b) :
				_b(a_b) {}
			bool U8(std::uint8_t& a_v)
			{
				if (_at + 1 > _b.size()) {
					return false;
				}
				a_v = _b[_at++];
				return true;
			}
			bool U32(std::uint32_t& a_v)
			{
				if (_at + 4 > _b.size()) {
					return false;
				}
				a_v = 0;
				for (int i = 0; i < 4; ++i) {
					a_v |= static_cast<std::uint32_t>(_b[_at++]) << (8 * i);
				}
				return true;
			}
			bool U64(std::uint64_t& a_v)
			{
				std::uint32_t lo = 0, hi = 0;
				if (!U32(lo) || !U32(hi)) {
					return false;
				}
				a_v = lo | (static_cast<std::uint64_t>(hi) << 32);
				return true;
			}
			bool I32(std::int32_t& a_v)
			{
				std::uint32_t v = 0;
				if (!U32(v)) {
					return false;
				}
				a_v = static_cast<std::int32_t>(v);
				return true;
			}
			bool Str(std::string& a_s)
			{
				std::uint32_t n = 0;
				if (!U32(n) || n > 4096 || _at + n > _b.size()) {
					return false;
				}
				a_s.assign(reinterpret_cast<const char*>(_b.data() + _at), n);
				_at += n;
				return true;
			}

		private:
			std::span<const std::uint8_t> _b;
			std::size_t                   _at{ 0 };
		};
	}

	void Director::SetData(Profiles a_profiles, std::vector<Template> a_catalog)
	{
		std::scoped_lock l{ _lock };
		_profiles = std::move(a_profiles);
		_catalog = std::move(a_catalog);
	}

	void Director::SetEnabled(bool a_enabled)
	{
		std::scoped_lock l{ _lock };
		_enabled = a_enabled;
	}

	void Director::SetAdult(bool a_adult)
	{
		std::scoped_lock l{ _lock };
		_adult = a_adult;
	}

	std::uint64_t Director::SeedFor(std::uint32_t a_ref, std::uint32_t a_base) const
	{
		return Mix(_salt ^ (static_cast<std::uint64_t>(a_ref) << 32 | a_base));
	}

	void Director::Seen(const Facts& a_facts)
	{
		std::scoped_lock l{ _lock };
		if (!_enabled || !a_facts.ref) {
			return;
		}
		if (!a_facts.skip.empty()) {
			// Never decided for -- but a look the player chose for themselves in the window is put back (C-19).
			const auto mine = _records.find(a_facts.ref);
			if (a_facts.skip != "player" || mine == _records.end() || !mine->second.manual) {
				return;
			}
		}
		if (_window.active && _window.ref == a_facts.ref) {
			return;  // the window has them
		}
		auto it = _records.find(a_facts.ref);
		if (it == _records.end()) {
			if (_profiles.groups.empty()) {
				return;  // no data loaded: decide nothing rather than decide from nothing
			}
			const auto* group = _profiles.Find(a_facts.group.empty() ? _profiles.fallback : a_facts.group);
			if (!group) {
				group = _profiles.Find(_profiles.fallback);
			}
			if (!group) {
				return;
			}
			Record r;
			r.female = a_facts.female;
			r.base = a_facts.base;
			r.group = group->name;
			r.hair = a_facts.hair;
			r.picks = Compose(_profiles, _catalog, a_facts.female, *group, SeedFor(a_facts.ref, a_facts.base), _adult, {}, r.hair);
			std::string list;
			for (const auto& p : r.picks) {
				list += (list.empty() ? "" : ", ") + p.id;
			}
			Log(std::format("{} ({:08X}, {}, {}): {}", a_facts.name, a_facts.ref, a_facts.female ? "female" : "male", r.group,
				r.picks.empty() ? "nothing" : list));
			it = _records.emplace(a_facts.ref, std::move(r)).first;
		} else if (!it->second.hairChecked && !a_facts.hair.empty()) {
			// A look from before body hair matched the head (0.1.3): kept, unless its hair is another colour than
			// theirs -- then decided again, once. A look chosen by hand is theirs and stays.
			auto& r = it->second;
			r.hairChecked = true;
			r.hair = a_facts.hair;
			if (!r.manual && HairClashes(r.picks, r.hair)) {
				// An empty look would queue nothing and leave the old one on them: kept then (it cannot happen while
				// every family has pubic hair to give, but the bridge only rebuilds for a look that has entries).
				const auto* group = _profiles.Find(r.group);
				auto        again = group ? Compose(_profiles, _catalog, r.female, *group, SeedFor(a_facts.ref, r.base), _adult, r.persona, r.hair)
				                          : std::vector<Pick>{};
				if (!again.empty()) {
					r.picks = std::move(again);
					r.applied = false;
					Log(std::format("{} ({:08X}): body hair did not match their {} hair, decided again: {} overlay(s)", a_facts.name,
						a_facts.ref, r.hair, r.picks.size()));
				}
			}
		}
		if (it->second.applied || it->second.picks.empty()) {
			return;
		}
		if (std::ranges::find(_queue, a_facts.ref) != _queue.end()) {
			return;
		}
		for (const auto& [id, o] : _inflight) {
			if (o.ref == a_facts.ref) {
				return;
			}
		}
		_queue.push_back(a_facts.ref);
	}

	std::uint32_t Director::NextOrder()
	{
		std::scoped_lock l{ _lock };
		while (!_queue.empty()) {
			const auto ref = _queue.front();
			_queue.pop_front();
			const auto it = _records.find(ref);
			if (it == _records.end() || it->second.applied || it->second.picks.empty()) {
				continue;
			}
			const auto id = _nextId++;
			_inflight.emplace(id, Order{ id, ref, it->second.female, it->second.picks });
			return id;
		}
		return 0;
	}

	std::optional<Order> Director::GetOrder(std::uint32_t a_id) const
	{
		std::scoped_lock l{ _lock };
		const auto it = _inflight.find(a_id);
		if (it == _inflight.end()) {
			return std::nullopt;
		}
		return it->second;
	}

	void Director::Done(std::uint32_t a_id, bool a_landed)
	{
		std::scoped_lock l{ _lock };
		const auto it = _inflight.find(a_id);
		if (it == _inflight.end()) {
			return;
		}
		const auto ref = it->second.ref;
		const bool window = it->second.window;
		_inflight.erase(it);
		if (window) {
			return;  // a preview: the record changes only on Apply
		}
		if (const auto r = _records.find(ref); r != _records.end()) {
			r->second.applied = a_landed;
			if (!a_landed) {
				Log(std::format("{:08X}: LooksMenu did not keep every entry even after a clean rebuild - tried again when they are next seen", ref));
			}
		}
	}

	void Director::Gone(std::uint32_t a_id)
	{
		std::scoped_lock l{ _lock };
		_inflight.erase(a_id);
	}

	bool Director::Regroup(std::uint32_t a_id, std::string_view a_group)
	{
		std::scoped_lock l{ _lock };
		const auto o = _inflight.find(a_id);
		// Papyrus hands strings back in whichever case was interned first: "captives" can arrive as "Captives".
		const Group* group = nullptr;
		for (const auto& g : _profiles.groups) {
			if (g.name.size() == a_group.size() && std::ranges::equal(g.name, a_group, [](char x, char y) {
					return std::tolower(static_cast<unsigned char>(x)) == std::tolower(static_cast<unsigned char>(y));
				})) {
				group = &g;
			}
		}
		if (o == _inflight.end() || !group) {
			return false;
		}
		const auto r = _records.find(o->second.ref);
		if (r == _records.end() || r->second.applied) {
			return false;
		}
		if (r->second.group == group->name) {
			return true;
		}
		r->second.picks = Compose(_profiles, _catalog, r->second.female, *group, SeedFor(o->second.ref, r->second.base), _adult, r->second.persona,
			r->second.hair);
		Log(std::format("{:08X}: {} after all (a faction on the reference), now: {} overlay(s)", o->second.ref, group->name, r->second.picks.size()));
		r->second.group = group->name;
		o->second.picks = r->second.picks;
		return true;
	}

	bool Director::SetPersona(std::uint32_t a_id, std::string_view a_persona)
	{
		std::scoped_lock l{ _lock };
		const auto o = _inflight.find(a_id);
		if (o == _inflight.end()) {
			return false;
		}
		const auto r = _records.find(o->second.ref);
		if (r == _records.end() || r->second.applied || r->second.persona == a_persona) {
			return false;
		}
		r->second.persona = std::string(a_persona);
		const auto* group = _profiles.Find(r->second.group);
		if (!group || !_profiles.personas.contains(a_persona)) {
			return false;  // a persona with nothing to add: the look stands
		}
		r->second.picks = Compose(_profiles, _catalog, r->second.female, *group, SeedFor(o->second.ref, r->second.base), _adult, a_persona,
			r->second.hair);
		Log(std::format("{:08X}: Rapport persona {}, now: {} overlay(s)", o->second.ref, a_persona, r->second.picks.size()));
		o->second.picks = r->second.picks;
		return true;
	}

	std::string Director::GroupOf(std::uint32_t a_id) const
	{
		std::scoped_lock l{ _lock };
		const auto o = _inflight.find(a_id);
		if (o == _inflight.end()) {
			return {};
		}
		const auto r = _records.find(o->second.ref);
		return r == _records.end() ? std::string{} : r->second.group;
	}

	void Director::ResetAll()
	{
		std::scoped_lock l{ _lock };
		_salt = Mix(_salt + 0x9E3779B97F4A7C15ull);
		Log(std::format("Reset: {} decision(s) forgotten; everyone is rolled again as they are seen", _records.size()));
		_records.clear();
		_queue.clear();
		_inflight.clear();
	}

	void Director::Unapply()
	{
		std::scoped_lock l{ _lock };
		for (auto& [ref, r] : _records) {
			r.applied = false;
		}
		_queue.clear();
		_inflight.clear();
	}

	void Director::ForgetQueue()
	{
		std::scoped_lock l{ _lock };
		_queue.clear();
		_inflight.clear();
		_window = {};
	}

	std::size_t Director::RecordCount() const
	{
		std::scoped_lock l{ _lock };
		return _records.size();
	}

	std::size_t Director::PendingCount() const
	{
		std::scoped_lock l{ _lock };
		return _queue.size() + _inflight.size();
	}

	std::optional<Record> Director::RecordFor(std::uint32_t a_ref) const
	{
		std::scoped_lock l{ _lock };
		const auto it = _records.find(a_ref);
		if (it == _records.end()) {
			return std::nullopt;
		}
		return it->second;
	}

	std::vector<std::uint8_t> Director::Save() const
	{
		std::scoped_lock l{ _lock };
		Writer w;
		w.U32(kSaveVersion);
		w.U64(_salt);
		w.U32(static_cast<std::uint32_t>(_records.size()));
		for (const auto& [ref, r] : _records) {
			w.U32(ref);
			w.U8(r.female ? 1 : 0);
			w.U8(r.applied ? 1 : 0);
			w.U32(r.base);
			w.Str(r.group);
			w.Str(r.persona);
			w.U8(r.manual ? 1 : 0);
			w.Str(r.hair);
			w.U32(static_cast<std::uint32_t>(r.picks.size()));
			for (const auto& p : r.picks) {
				w.Str(p.key);
				w.Str(p.kind);
				w.I32(p.priority);
			}
		}
		return w.Take();
	}

	bool Director::Load(std::span<const std::uint8_t> a_bytes, const std::function<std::uint32_t(std::uint32_t)>& a_resolve)
	{
		std::scoped_lock l{ _lock };
		Reader        r(a_bytes);
		std::uint32_t version = 0, count = 0;
		std::uint64_t salt = 0;
		if (!r.U32(version) || version < 1 || version > kSaveVersion || !r.U64(salt) || !r.U32(count)) {
			return false;
		}
		_salt = salt;
		_records.clear();
		std::size_t dropped = 0;
		for (std::uint32_t i = 0; i < count; ++i) {
			std::uint32_t ref = 0, picks = 0;
			std::uint8_t  female = 0, applied = 0, manual = 0;
			Record        rec;
			if (!r.U32(ref) || !r.U8(female) || !r.U8(applied) || !r.U32(rec.base) || !r.Str(rec.group) ||
				(version >= 2 && !r.Str(rec.persona)) || (version >= 3 && !r.U8(manual)) || (version >= 4 && !r.Str(rec.hair)) ||
				!r.U32(picks) || picks > 64) {
				return false;
			}
			rec.hairChecked = version >= 4;
			rec.manual = manual != 0;
			rec.female = female != 0;
			rec.applied = applied != 0;
			for (std::uint32_t k = 0; k < picks; ++k) {
				Pick p;
				if (!r.Str(p.key) || !r.Str(p.kind) || !r.I32(p.priority)) {
					return false;
				}
				p.id = p.key.size() > 2 ? p.key.substr(2) : p.key;
				rec.picks.push_back(std::move(p));
			}
			const auto now = a_resolve ? a_resolve(ref) : ref;
			if (!now) {
				++dropped;
				continue;
			}
			_records[now] = std::move(rec);
		}
		if (dropped) {
			Log(std::format("co-save: {} record(s) of actors no longer in this load order dropped", dropped));
		}
		return true;
	}

	void Director::Revert()
	{
		std::scoped_lock l{ _lock };
		_records.clear();
		_queue.clear();
		_inflight.clear();
		_window = {};
		_salt = 0x436F6D706C786E31ull;
	}

	std::vector<std::string> Director::TakeLog()
	{
		std::scoped_lock l{ _lock };
		return std::exchange(_log, {});
	}

	std::uint64_t Director::Salt() const
	{
		std::scoped_lock l{ _lock };
		return _salt;
	}

	void Director::SetSalt(std::uint64_t a_salt)
	{
		std::scoped_lock l{ _lock };
		_salt = a_salt;
	}

	// ---- the overlay window (C-19) ----

	namespace
	{
		// The window's categories: which tag kinds each shows.
		const std::map<std::string, std::vector<std::string>, std::less<>>& Categories()
		{
			static const std::map<std::string, std::vector<std::string>, std::less<>> c{
				{ "skin", { "skin", "mole", "freckles", "birthmark", "acne", "nipple", "tan" } },
				{ "hair", { "pubic_hair", "body_hair" } },
				{ "scars", { "scar", "wound", "burn" } },
				{ "tattoos", { "tattoo", "brand" } },
				{ "rough", { "bruise", "marks", "blood", "dirt" } },
				{ "paint", { "makeup", "other" } },  // "other": the packs' paint stripes and neon
				{ "nails", { "nails" } },
			};
			return c;
		}

		std::string Lower(std::string_view a_s)
		{
			std::string out(a_s);
			std::ranges::transform(out, out.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
			return out;
		}

		// A label for a card: the tag's note, capitalised; the template id without one. Tabs and bars, which
		// separate fields and entries, never get into one.
		std::string Label(const Template& a_t)
		{
			std::string out = a_t.note.empty() ? a_t.id : a_t.note;
			for (auto& c : out) {
				if (c == '\t' || c == '|') {
					c = ' ';
				}
			}
			if (!out.empty()) {
				out[0] = static_cast<char>(std::toupper(static_cast<unsigned char>(out[0])));
			}
			return out;
		}

		bool IEq(std::string_view a, std::string_view b)
		{
			return a.size() == b.size() && std::ranges::equal(a, b, [](char x, char y) {
				return std::tolower(static_cast<unsigned char>(x)) == std::tolower(static_cast<unsigned char>(y));
			});
		}

		bool Ours(const Template& a_t)
		{
			return a_t.id.starts_with("Complexion_");
		}
	}

	const Template* Director::Find(std::string_view a_key) const
	{
		const auto it = std::ranges::lower_bound(_catalog, a_key, {}, &Template::key);
		if (it != _catalog.end() && it->key == a_key) {
			return &*it;
		}
		// Papyrus hands strings back in whichever case was interned first (a key through the window's events).
		const auto found = std::ranges::find_if(_catalog, [&](const Template& t) { return IEq(t.key, a_key); });
		return found != _catalog.end() ? &*found : nullptr;
	}

	// The window's picks in their layers: skin under hair under tattoos (C-6), the later of a layer above.
	std::vector<Pick> Director::Repriority(std::vector<Pick> a_picks) const
	{
		for (std::size_t i = 0; i < a_picks.size(); ++i) {
			a_picks[i].priority = LayerOf(a_picks[i].kind) + static_cast<int>(i);
		}
		return a_picks;
	}

	void Director::SetThumbs(std::unordered_map<std::string, std::pair<int, int>> a_cells, std::string a_build)
	{
		std::scoped_lock l{ _lock };
		_thumbs = std::move(a_cells);
		_thumbBuild = std::move(a_build);
	}

	void Director::SetSpots(std::unordered_map<std::string, std::array<float, 8>> a_spots)
	{
		std::scoped_lock l{ _lock };
		_spots = std::move(a_spots);
	}

	std::optional<std::array<float, 8>> Director::SpotOf(std::string_view a_key) const
	{
		std::scoped_lock l{ _lock };
		const auto* t = Find(a_key);
		if (!t) {
			return std::nullopt;
		}
		if (const auto it = _spots.find(t->key); it != _spots.end()) {
			return it->second;
		}
		// Another pack's: where its tagged region is (h, x, y, normal, spread, arm), in body heights.
		static const std::map<std::string, std::array<float, 8>, std::less<>> regions{
			{ "chest", { 0.87F, 0.0F, 0.08F, 0.0F, 1.0F, 0.0F, 0.07F, 0.0F } },
			{ "breasts", { 0.86F, 0.0F, 0.08F, 0.0F, 1.0F, 0.0F, 0.07F, 0.0F } },
			{ "belly", { 0.65F, 0.0F, 0.08F, 0.0F, 1.0F, 0.0F, 0.06F, 0.0F } },
			{ "pubic", { 0.59F, 0.0F, 0.08F, 0.0F, 1.0F, 0.0F, 0.04F, 0.0F } },
			{ "pelvis", { 0.60F, 0.11F, 0.0F, 1.0F, 0.0F, 0.0F, 0.05F, 0.0F } },
			{ "back", { 0.85F, 0.0F, -0.07F, 0.0F, -1.0F, 0.0F, 0.09F, 0.0F } },
			{ "lower_back", { 0.66F, 0.0F, -0.06F, 0.0F, -1.0F, 0.0F, 0.06F, 0.0F } },
			{ "butt", { 0.56F, 0.0F, -0.08F, 0.0F, -1.0F, 0.0F, 0.07F, 0.0F } },
			{ "neck", { 0.95F, 0.0F, -0.06F, 0.0F, -1.0F, 0.0F, 0.03F, 0.0F } },
			{ "arm_l", { 0.80F, -0.2F, 0.0F, -1.0F, 0.0F, 0.0F, 0.1F, 1.0F } },
			{ "arm_r", { 0.80F, 0.2F, 0.0F, 1.0F, 0.0F, 0.0F, 0.1F, 1.0F } },
			{ "hand_l", { 0.55F, -0.2F, 0.0F, -1.0F, 0.0F, 0.0F, 0.06F, 1.0F } },
			{ "hand_r", { 0.55F, 0.2F, 0.0F, 1.0F, 0.0F, 0.0F, 0.06F, 1.0F } },
			{ "leg_l", { 0.36F, -0.08F, 0.03F, 0.0F, 1.0F, 0.0F, 0.1F, 0.0F } },
			{ "leg_r", { 0.36F, 0.08F, 0.03F, 0.0F, 1.0F, 0.0F, 0.1F, 0.0F } },
			{ "feet", { 0.05F, 0.0F, 0.05F, 0.0F, 1.0F, 0.0F, 0.05F, 0.0F } },
		};
		for (const auto& r : t->regions) {
			if (const auto it = regions.find(r); it != regions.end()) {
				return it->second;
			}
		}
		return std::nullopt;
	}

	bool Director::HairClashes(const std::vector<Pick>& a_picks, std::string_view a_hair) const
	{
		const auto& hc = _profiles.hairColours;
		const auto  family = hc.accept.find(std::string(a_hair));
		if (!hc.present || family == hc.accept.end()) {
			return false;
		}
		return std::ranges::any_of(a_picks, [&](const Pick& p) {
			const auto* t = Find(p.key);
			return t && (t->kind == "pubic_hair" || t->kind == "body_hair") &&
			       std::ranges::find(family->second, t->hair) == family->second.end();
		});
	}

	std::string Director::ThumbBuild() const
	{
		std::scoped_lock l{ _lock };
		return _thumbBuild;
	}

	std::string Director::WindowBegin(std::uint32_t a_ref, bool a_female, std::string_view a_hair)
	{
		std::scoped_lock l{ _lock };
		if (!a_ref) {
			return "nobody to show";
		}
		if (_catalog.empty()) {
			return "Complexion's data did not load (Complexion.log says why)";
		}
		_window = {};
		_window.active = true;
		_window.ref = a_ref;
		_window.female = a_female;
		_window.hair = std::string(a_hair);
		if (const auto it = _records.find(a_ref); it != _records.end()) {
			_window.before = it->second;
			_window.draft = it->second.picks;
		}
		// Whatever the poll had queued for them waits: the window has them now.
		std::erase(_queue, a_ref);
		return {};
	}

	void Director::WindowEnd()
	{
		std::scoped_lock l{ _lock };
		_window = {};
	}

	std::string Director::WindowPage(std::string_view a_category, std::string_view a_search, int a_page, int a_per) const
	{
		std::scoped_lock l{ _lock };
		if (!_window.active) {
			return "0";
		}
		const auto  search = Lower(a_search);
		// Lower-cased: a Papyrus string comes back in the case it was first interned in ("All", "SKIN"), and a
		// category missed here showed everything -- "categories switching doesn't change anything" (owner, 10-04).
		const auto  category = Lower(a_category);
		const auto& cats = Categories();
		const auto  cat = cats.find(category);
		const bool  onOnly = category == "on";
		std::vector<const Template*> shown;
		const auto on = [&](const Template& t) {
			return std::ranges::any_of(_window.draft, [&](const Pick& p) { return p.key == t.key; });
		};
		const auto passes = [&](const Template& t) {
			if (t.female != _window.female || (!_adult && IsAdult(t))) {
				return false;
			}
			if (onOnly ? !on(t) : (cat != cats.end() && std::ranges::find(cat->second, t.kind) == cat->second.end())) {
				return false;
			}
			// A category other than "all" it does not know shows nothing, never everything (that hid the case bug).
			if (!onOnly && cat == cats.end() && category != "all") {
				return false;
			}
			return search.empty() || Lower(Label(t)).find(search) != std::string::npos || Lower(t.id).find(search) != std::string::npos;
		};
		for (const auto& t : _catalog) {
			if (passes(t)) {
				shown.push_back(&t);
			}
		}
		// Complexion's own first (they have pictures), each part in the catalog's order.
		std::ranges::stable_partition(shown, [](const Template* t) { return Ours(*t); });
		const int per = std::clamp(a_per, 1, 60);
		const int first = std::max(0, a_page) * per;
		std::string out = std::to_string(shown.size());
		for (int i = first; i < first + per && i < static_cast<int>(shown.size()); ++i) {
			const auto& t = *shown[static_cast<std::size_t>(i)];
			int  atlas = -1, cell = -1;
			if (const auto th = _thumbs.find(t.key); th != _thumbs.end()) {
				atlas = th->second.first;
				cell = th->second.second;
			}
			out += std::format("|{}\t{}\t{}\t{}\t{}\t{}", t.key, Label(t), t.kind, on(t) ? 1 : 0, atlas, cell);
		}
		return out;
	}

	bool Director::WindowToggle(std::string_view a_key)
	{
		std::scoped_lock l{ _lock };
		if (!_window.active) {
			return false;
		}
		if (const auto n = std::erase_if(_window.draft, [&](const Pick& p) { return IEq(p.key, a_key); }); n > 0) {
			return false;
		}
		const auto* t = Find(a_key);
		if (!t || t->female != _window.female || _window.draft.size() >= 24) {
			return false;
		}
		_window.draft.push_back(Pick{ t->key, t->id, t->kind, 0 });
		return true;
	}

	std::size_t Director::WindowCount() const
	{
		std::scoped_lock l{ _lock };
		return _window.active ? _window.draft.size() : 0;
	}

	void Director::WindowClear()
	{
		std::scoped_lock l{ _lock };
		_window.draft.clear();
	}

	void Director::WindowRoll()
	{
		std::scoped_lock l{ _lock };
		if (!_window.active || _profiles.groups.empty()) {
			return;
		}
		const auto* group = _window.before ? _profiles.Find(_window.before->group) : nullptr;
		if (!group) {
			group = _profiles.Find(_profiles.fallback);
		}
		if (!group) {
			return;
		}
		const std::uint32_t base = _window.before ? _window.before->base : 0;
		const auto          persona = _window.before ? _window.before->persona : std::string{};
		_window.draft = Compose(_profiles, _catalog, _window.female, *group, Mix(SeedFor(_window.ref, base) + ++_window.rolls), _adult, persona,
			_window.hair);
	}

	std::uint32_t Director::WindowOrder(std::vector<Pick> a_picks)
	{
		// Every order on them before is over: what the window shows is the latest.
		std::erase_if(_inflight, [&](const auto& kv) { return kv.second.ref == _window.ref; });
		const auto id = _nextId++;
		_inflight.emplace(id, Order{ id, _window.ref, _window.female, Repriority(std::move(a_picks)), true });
		return id;
	}

	std::uint32_t Director::WindowPreview()
	{
		std::scoped_lock l{ _lock };
		return _window.active ? WindowOrder(_window.draft) : 0;
	}

	std::uint32_t Director::WindowRestore()
	{
		std::scoped_lock l{ _lock };
		if (!_window.active) {
			return 0;
		}
		return WindowOrder(_window.before ? _window.before->picks : std::vector<Pick>{});
	}

	void Director::WindowApply()
	{
		std::scoped_lock l{ _lock };
		if (!_window.active) {
			return;
		}
		Record r = _window.before.value_or(Record{});
		r.female = _window.female;
		if (r.group.empty()) {
			r.group = "hand-picked";
		}
		r.picks = Repriority(_window.draft);
		r.applied = true;  // the window's last preview put exactly these on them
		r.manual = true;
		std::string list;
		for (const auto& p : r.picks) {
			list += (list.empty() ? "" : ", ") + p.id;
		}
		Log(std::format("{:08X}: chosen in the window: {}", _window.ref, list.empty() ? "nothing" : list));
		_records[_window.ref] = std::move(r);
		_window.before = _records[_window.ref];
	}

	void Director::Log(std::string a_line)
	{
		if (_log.size() < 2000) {
			_log.push_back(std::move(a_line));
		}
	}
}

#include "Director.h"

namespace CX
{
	namespace
	{
		constexpr std::uint32_t kSaveVersion = 1;

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
		if (!_enabled || !a_facts.ref || !a_facts.skip.empty()) {
			return;
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
			r.picks = Compose(_profiles, _catalog, a_facts.female, *group, SeedFor(a_facts.ref, a_facts.base), _adult);
			std::string list;
			for (const auto& p : r.picks) {
				list += (list.empty() ? "" : ", ") + p.id;
			}
			Log(std::format("{} ({:08X}, {}, {}): {}", a_facts.name, a_facts.ref, a_facts.female ? "female" : "male", r.group,
				r.picks.empty() ? "nothing" : list));
			it = _records.emplace(a_facts.ref, std::move(r)).first;
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
		_inflight.erase(it);
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
		r->second.picks = Compose(_profiles, _catalog, r->second.female, *group, SeedFor(o->second.ref, r->second.base), _adult);
		Log(std::format("{:08X}: {} after all (a faction on the reference), now: {} overlay(s)", o->second.ref, group->name, r->second.picks.size()));
		r->second.group = group->name;
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
		if (!r.U32(version) || version != kSaveVersion || !r.U64(salt) || !r.U32(count)) {
			return false;
		}
		_salt = salt;
		_records.clear();
		std::size_t dropped = 0;
		for (std::uint32_t i = 0; i < count; ++i) {
			std::uint32_t ref = 0, picks = 0;
			std::uint8_t  female = 0, applied = 0;
			Record        rec;
			if (!r.U32(ref) || !r.U8(female) || !r.U8(applied) || !r.U32(rec.base) || !r.Str(rec.group) || !r.U32(picks) || picks > 64) {
				return false;
			}
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

	void Director::Log(std::string a_line)
	{
		if (_log.size() < 2000) {
			_log.push_back(std::move(a_line));
		}
	}
}

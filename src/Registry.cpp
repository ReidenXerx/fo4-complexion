#include "Registry.h"

namespace SH
{
	namespace
	{
		class Writer
		{
		public:
			template <class T>
			void Put(T a_value)
			{
				static_assert(std::is_trivially_copyable_v<T>);
				const auto* p = reinterpret_cast<const std::byte*>(&a_value);
				_out.insert(_out.end(), p, p + sizeof(T));
			}

			void Str(std::string_view a_text)
			{
				const auto size = static_cast<std::uint16_t>(std::min<std::size_t>(a_text.size(), 0xFFFF));
				Put(size);
				const auto* p = reinterpret_cast<const std::byte*>(a_text.data());
				_out.insert(_out.end(), p, p + size);
			}

			void Bytes(const std::vector<std::byte>& a_bytes) { _out.insert(_out.end(), a_bytes.begin(), a_bytes.end()); }

			// A record's fields, without its length: a later version appends after them.
			void Rec(std::uint32_t a_ref, const Record& a_r)
			{
				Put(a_ref);
				Put(a_r.base);
				Put(static_cast<std::uint8_t>(a_r.source));
				Put(a_r.stamp);
				Put(a_r.announced);
				Put(a_r.touched);
				Str(a_r.preset);
			}

			[[nodiscard]] std::size_t            Size() const { return _out.size(); }
			[[nodiscard]] std::vector<std::byte> Take() { return std::move(_out); }

		private:
			std::vector<std::byte> _out;
		};

		class Reader
		{
		public:
			explicit Reader(std::span<const std::byte> a_bytes) :
				_in(a_bytes) {}

			template <class T>
			T Get()
			{
				static_assert(std::is_trivially_copyable_v<T>);
				if (_at + sizeof(T) > _end) {
					throw std::runtime_error(std::format("record list ends early at byte {}", _at));
				}
				T value;
				std::memcpy(&value, _in.data() + _at, sizeof(T));
				_at += sizeof(T);
				return value;
			}

			std::string Str()
			{
				const auto size = Get<std::uint16_t>();
				if (_at + size > _end) {
					throw std::runtime_error(std::format("a string runs past the end at byte {}", _at));
				}
				std::string text(reinterpret_cast<const char*>(_in.data() + _at), size);
				_at += size;
				return text;
			}

			std::pair<std::uint32_t, Record> Rec()
			{
				const auto saved = Get<std::uint32_t>();
				Record     r;
				r.base = Get<std::uint32_t>();
				const auto source = Get<std::uint8_t>();
				// A source a later version added means nothing here: the body stays, nobody's choice.
				r.source = source <= static_cast<std::uint8_t>(Source::kRoll) ? static_cast<Source>(source) : Source::kNone;
				r.stamp = Get<std::uint32_t>();
				r.announced = Get<std::uint32_t>();
				r.touched = Get<std::uint32_t>();
				r.preset = Str();
				return { saved, std::move(r) };
			}

			// Reads a_length bytes as one item: whatever a later version appended after the fields this one
			// knows is skipped, and an item cannot read past its own end.
			template <class F>
			void Item(std::size_t a_length, F&& a_read)
			{
				if (_at + a_length > _end) {
					throw std::runtime_error(std::format("an item of {} bytes runs past the end at byte {}", a_length, _at));
				}
				const auto end = _end;
				const auto stop = _at + a_length;
				_end = stop;
				a_read();
				_at = stop;
				_end = end;
			}

			[[nodiscard]] bool AtEnd() const { return _at == _in.size(); }

			// Bytes left in the item being read: a field a later version appended is there or not.
			[[nodiscard]] std::size_t Left() const { return _end - _at; }

		private:
			std::span<const std::byte> _in;
			std::size_t                _at{ 0 };
			std::size_t                _end{ _in.size() };
		};
	}

	std::string_view SourceName(Source a_source)
	{
		switch (a_source) {
		case Source::kNone:
			return "BodyGen"sv;
		case Source::kNameRule:
			return "npc rule"sv;
		case Source::kFactionRule:
			return "faction rule"sv;
		case Source::kPicker:
			return "picked"sv;
		case Source::kAPI:
			return "another mod"sv;
		case Source::kNameBlacklist:
			return "blacklisted"sv;
		case Source::kReset:
			return "reset"sv;
		case Source::kRoll:
			return "a roll owed"sv;
		}
		return "?"sv;
	}

	bool KeepInCoSave(std::uint32_t a_ref, std::uint32_t a_base, bool a_intent, std::optional<std::uint32_t> a_liveBase)
	{
		if (a_intent || (a_ref >> 24) != 0xFF) {
			return true;
		}
		return a_liveBase && (a_base == 0 || a_base == *a_liveBase);
	}

	Record* Registry::Find(std::uint32_t a_ref)
	{
		const auto it = _records.find(a_ref);
		return it == _records.end() ? nullptr : &it->second;
	}

	const Record* Registry::Find(std::uint32_t a_ref) const
	{
		const auto it = _records.find(a_ref);
		return it == _records.end() ? nullptr : &it->second;
	}

	Record& Registry::Get(std::uint32_t a_ref)
	{
		return _records[a_ref];
	}

	void Registry::Prune(std::uint32_t a_ref)
	{
		if (const auto* r = Find(a_ref); r && r->Empty()) {
			_records.erase(a_ref);
		}
	}

	void Registry::Keep(PickerSave a_save)
	{
		a_save.seq = ++_seq;
		pickings[a_save.ref] = std::move(a_save);
		while (pickings.size() > kMaxPickings) {
			const auto oldest = std::ranges::min_element(pickings, {}, [](const auto& a_p) { return a_p.second.seq; });
			pickings.erase(oldest);
		}
	}

	std::size_t Registry::ForgetChoices()
	{
		std::size_t changed = 0;
		const auto  owe = [&](Record& a_r) {
			if (a_r.source != Source::kRoll) {
				a_r.source = Source::kRoll;
				++changed;
			}
			a_r.preset.clear();
			a_r.salt = 0;
		};
		for (auto& [ref, r] : _records) {
			if (r.source == Source::kPicker || r.source == Source::kAPI) {
				owe(r);
			} else if (r.source == Source::kNameRule || r.source == Source::kFactionRule || r.salt != 0) {
				// The rule decides again as if they were met now: the draw by id alone, not the one they kept.
				if (!r.preset.empty() || r.salt != 0) {
					++changed;
				}
				r.preset.clear();
				r.salt = 0;
			}
		}
		// A picking would put back the body they had; the fresh one replaces it.
		for (const auto& [ref, save] : pickings) {
			auto& r = _records[ref];
			if (r.base == 0) {
				r.base = save.base;
			}
			owe(r);
		}
		pickings.clear();
		return changed;
	}

	std::vector<std::byte> Registry::SerializeReset() const
	{
		if (resetStamps.empty()) {
			return {};
		}
		Writer w;
		const auto count = static_cast<std::uint16_t>(std::min<std::size_t>(resetStamps.size(), 0xFFFF));
		w.Put(count);
		for (std::size_t i = 0; i < count; ++i) {
			w.Put(resetStamps[i]);
		}
		// S-70, after the stamps: the plugin that first wrote this record stops reading there.
		std::vector<std::uint32_t> met(resetMet.begin(), resetMet.end());
		std::ranges::sort(met);
		w.Put(static_cast<std::uint32_t>(met.size()));
		for (const auto ref : met) {
			w.Put(ref);
		}
		return w.Take();
	}

	Registry::Loaded Registry::DeserializeReset(std::span<const std::byte> a_bytes, std::uint32_t a_version, std::string& a_error,
		const std::function<std::uint32_t(std::uint32_t)>& a_resolve)
	{
		if (a_version > kResetVersion) {
			a_error = std::format("reset record version {} is newer than this plugin's ({})", a_version, kResetVersion);
			return Loaded::kNewer;
		}
		if (a_version != kResetVersion) {
			a_error = std::format("reset record version {} (this plugin reads {})", a_version, kResetVersion);
			return Loaded::kRefused;
		}
		try {
			Reader                     r(a_bytes);
			std::vector<std::uint32_t> stamps;
			const auto                 count = r.Get<std::uint16_t>();
			for (std::uint16_t i = 0; i < count; ++i) {
				const auto s = r.Get<std::uint32_t>();
				if (s == 0 || s >= (1u << 24)) {
					throw std::runtime_error(std::format("{} is not a build stamp", s));
				}
				stamps.push_back(s);
			}
			// Who was looked at since the press (S-70). A record from before it ends at the stamps: nobody yet.
			std::unordered_set<std::uint32_t> met;
			if (!r.AtEnd()) {
				const auto n = r.Get<std::uint32_t>();
				for (std::uint32_t i = 0; i < n; ++i) {
					const auto saved = r.Get<std::uint32_t>();
					if (const auto ref = a_resolve ? a_resolve(saved) : saved; ref != 0) {
						met.insert(ref);
					}
				}
			}
			// Whatever a later version appended after that is not this one's to read.
			resetStamps = std::move(stamps);
			resetMet = std::move(met);
			return Loaded::kOk;
		} catch (const std::exception& e) {
			a_error = e.what();
			return Loaded::kRefused;
		}
	}

	std::vector<std::byte> Registry::Serialize(const KeepFn& a_keep) const
	{
		std::vector<std::pair<std::uint32_t, const Record*>> kept;
		for (const auto& [ref, record] : _records) {
			if (!record.Empty() && (!a_keep || a_keep(ref, record.base, record.Intent()))) {
				kept.emplace_back(ref, &record);
			}
		}
		// Stable bytes for the same records, whatever order the map happens to hold them in.
		std::ranges::sort(kept, {}, &std::pair<std::uint32_t, const Record*>::first);

		Writer w;
		w.Put(static_cast<std::uint32_t>(kept.size()));
		for (const auto& [ref, r] : kept) {
			Writer item;
			item.Rec(ref, *r);
			item.Put(r->salt);
			w.Put(static_cast<std::uint16_t>(item.Size()));
			w.Bytes(item.Take());
		}
		std::vector<const PickerSave*> saves;
		for (const auto& [ref, save] : pickings) {
			if (!a_keep || a_keep(ref, save.base, true)) {
				saves.push_back(&save);
			}
		}
		w.Put(static_cast<std::uint32_t>(saves.size()));
		for (const auto* save : saves) {
			Writer item;
			item.Put(save->ref);
			item.Put(save->base);
			item.Put(static_cast<std::uint8_t>(save->female ? 1 : 0));
			const auto count = static_cast<std::uint16_t>(std::min<std::size_t>(save->snapshot.size(), 0xFFFF));
			item.Put(count);
			for (std::size_t i = 0; i < count; ++i) {
				item.Str(save->snapshot[i].first);
				item.Put(save->snapshot[i].second);
			}
			item.Put(static_cast<std::uint8_t>(save->before ? 1 : 0));
			if (save->before) {
				item.Rec(save->ref, *save->before);
			}
			// Appended after the fields version 2 began with: the arrival order the cap goes by, then the
			// salt of the record the picking would put back -- written only when there is one. A field added
			// later goes after both, and its reader follows the same condition.
			item.Put(save->seq);
			if (save->before) {
				item.Put(save->before->salt);
			}
			w.Put(static_cast<std::uint32_t>(item.Size()));
			w.Bytes(item.Take());
		}
		return w.Take();
	}

	Registry::Loaded Registry::Deserialize(std::span<const std::byte> a_bytes, std::uint32_t a_version,
		const std::function<std::uint32_t(std::uint32_t)>& a_resolve, std::string& a_error)
	{
		if (a_version > kVersion) {
			a_error = std::format("record list version {} is newer than this plugin's ({})", a_version, kVersion);
			return Loaded::kNewer;
		}
		if (a_version != kVersion) {
			a_error = std::format("record list version {} (this plugin reads {})", a_version, kVersion);
			return Loaded::kRefused;
		}
		const auto resolve = [&](std::uint32_t a_id) { return a_resolve ? a_resolve(a_id) : a_id; };
		try {
			std::unordered_map<std::uint32_t, Record> loaded;
			std::map<std::uint32_t, PickerSave>       saves;
			Reader                                    r(a_bytes);
			const auto                                count = r.Get<std::uint32_t>();
			for (std::uint32_t i = 0; i < count; ++i) {
				const auto length = r.Get<std::uint16_t>();
				r.Item(length, [&] {
					auto [saved, rec] = r.Rec();
					if (r.Left() >= sizeof(std::uint32_t)) {
						rec.salt = r.Get<std::uint32_t>();
					}
					const auto ref = resolve(saved);
					if (ref == 0) {
						return;  // the reference is gone (its plugin was removed)
					}
					if (rec.base != 0) {
						rec.base = resolve(rec.base);
					}
					loaded[ref] = std::move(rec);
				});
			}
			const auto    pickingCount = r.Get<std::uint32_t>();
			std::uint32_t lastSeq = 0;
			for (std::uint32_t i = 0; i < pickingCount; ++i) {
				const auto length = r.Get<std::uint32_t>();
				r.Item(length, [&] {
					PickerSave p;
					p.ref = resolve(r.Get<std::uint32_t>());
					const auto base = r.Get<std::uint32_t>();
					p.base = base ? resolve(base) : 0;
					p.female = r.Get<std::uint8_t>() != 0;
					const auto n = r.Get<std::uint16_t>();
					for (std::uint16_t k = 0; k < n; ++k) {
						auto       morph = r.Str();
						const auto value = r.Get<float>();
						p.snapshot.emplace_back(std::move(morph), value);
					}
					if (r.Get<std::uint8_t>() != 0) {
						auto rec = r.Rec().second;
						if (rec.base) {
							rec.base = resolve(rec.base);
						}
						p.before = std::move(rec);
					}
					// Written by a build that knew the arrival order: kept. Before it, the file's order.
					p.seq = r.Left() >= sizeof(std::uint32_t) ? r.Get<std::uint32_t>() : i + 1;
					if (p.before && r.Left() >= sizeof(std::uint32_t)) {
						p.before->salt = r.Get<std::uint32_t>();
					}
					if (p.ref != 0) {
						lastSeq = std::max(lastSeq, p.seq);
						saves[p.ref] = std::move(p);
					}
				});
			}
			if (!r.AtEnd()) {
				throw std::runtime_error("bytes left over after the last picking");
			}
			_records = std::move(loaded);
			pickings = std::move(saves);
			_seq = std::max(lastSeq, pickingCount);
			return Loaded::kOk;
		} catch (const std::exception& e) {
			a_error = e.what();
			return Loaded::kRefused;
		}
	}
}

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
				if (_at + sizeof(T) > _in.size()) {
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
				if (_at + size > _in.size()) {
					throw std::runtime_error(std::format("a string runs past the end at byte {}", _at));
				}
				std::string text(reinterpret_cast<const char*>(_in.data() + _at), size);
				_at += size;
				return text;
			}

			[[nodiscard]] bool AtEnd() const { return _at == _in.size(); }

		private:
			std::span<const std::byte> _in;
			std::size_t                _at{ 0 };
		};

		constexpr std::uint8_t kRefitApplied = 1;
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
		}
		return "?"sv;
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

	std::vector<std::byte> Registry::Serialize(const std::function<bool(std::uint32_t)>& a_keep) const
	{
		std::vector<std::pair<std::uint32_t, const Record*>> kept;
		for (const auto& [ref, record] : _records) {
			if (!record.Empty() && (!a_keep || a_keep(ref))) {
				kept.emplace_back(ref, &record);
			}
		}
		// Stable bytes for the same records, whatever order the map happens to hold them in.
		std::ranges::sort(kept, {}, &std::pair<std::uint32_t, const Record*>::first);

		Writer w;
		w.Put(static_cast<std::uint32_t>(kept.size()));
		for (const auto& [ref, r] : kept) {
			w.Put(ref);
			w.Put(r->base);
			w.Put(static_cast<std::uint8_t>(r->source));
			w.Put(static_cast<std::uint8_t>(r->refitApplied ? kRefitApplied : 0));
			w.Put(r->stamp);
			w.Put(r->announced);
			w.Str(r->preset);
			w.Str(r->refitSet);
			const auto count = static_cast<std::uint16_t>(std::min<std::size_t>(r->snapshot.size(), 0xFFFF));
			w.Put(count);
			for (std::size_t i = 0; i < count; ++i) {
				w.Str(r->snapshot[i].first);
				w.Put(r->snapshot[i].second);
			}
		}
		return w.Take();
	}

	bool Registry::Deserialize(std::span<const std::byte> a_bytes, std::uint32_t a_version,
		const std::function<std::uint32_t(std::uint32_t)>& a_resolve, std::string& a_error)
	{
		if (a_version != kVersion) {
			a_error = std::format("record list version {} (this plugin reads {})", a_version, kVersion);
			return false;
		}
		try {
			std::unordered_map<std::uint32_t, Record> loaded;
			Reader                                    r(a_bytes);
			const auto                                count = r.Get<std::uint32_t>();
			for (std::uint32_t i = 0; i < count; ++i) {
				const auto saved = r.Get<std::uint32_t>();
				Record     rec;
				rec.base = r.Get<std::uint32_t>();
				const auto source = r.Get<std::uint8_t>();
				if (source > static_cast<std::uint8_t>(Source::kNameBlacklist)) {
					throw std::runtime_error(std::format("record {:08X}: unknown source {}", saved, source));
				}
				rec.source = static_cast<Source>(source);
				rec.refitApplied = (r.Get<std::uint8_t>() & kRefitApplied) != 0;
				rec.stamp = r.Get<std::uint32_t>();
				rec.announced = r.Get<std::uint32_t>();
				rec.preset = r.Str();
				rec.refitSet = r.Str();
				const auto n = r.Get<std::uint16_t>();
				for (std::uint16_t k = 0; k < n; ++k) {
					auto       morph = r.Str();
					const auto value = r.Get<float>();
					rec.snapshot.emplace_back(std::move(morph), value);
				}
				// Resolved AFTER reading the whole record: a record we drop must still be consumed.
				const auto ref = a_resolve ? a_resolve(saved) : saved;
				if (ref == 0) {
					continue;  // the reference is gone (its plugin was removed)
				}
				if (rec.base != 0 && a_resolve) {
					rec.base = a_resolve(rec.base);
				}
				loaded[ref] = std::move(rec);
			}
			if (!r.AtEnd()) {
				throw std::runtime_error("bytes left over after the last record");
			}
			_records = std::move(loaded);
			return true;
		} catch (const std::exception& e) {
			a_error = e.what();
			return false;
		}
	}
}

#include "EventSources.h"

// Ported from fo4-mcp src/Matrix.cpp (the owner's own project), which found these sources on this
// exact runtime and logs them on every launch ("matrix: equip attached (scan: TESEquipEvent ...)").
// Every read is bounds-checked against the module or guarded, so any address can be asked.

namespace CX::Events
{
	namespace
	{
		bool SafeRead(const void* a_from, void* a_into, std::size_t a_count)
		{
			__try {
				std::memcpy(a_into, a_from, a_count);
				return true;
			} __except (1) {
				return false;
			}
		}

		struct Range
		{
			std::uintptr_t lo{ 0 };
			std::uintptr_t hi{ 0 };
			[[nodiscard]] bool Has(std::uintptr_t a_address) const { return a_address >= lo && a_address < hi; }
		};

		const Range& ModuleRange()
		{
			static const Range range = [] {
				const auto& module = REL::Module::get();
				Range       r{ module.base(), module.base() };
				for (std::size_t i = 0; i < REL::Segment::total; ++i) {
					const auto seg = module.segment(static_cast<REL::Segment::Name>(i));
					if (seg.size()) {
						r.hi = std::max(r.hi, seg.address() + seg.size());
					}
				}
				return r;
			}();
			return range;
		}

		bool ReadU32(std::uintptr_t a_at, std::uint32_t& a_out)
		{
			return ModuleRange().Has(a_at) && SafeRead(reinterpret_cast<const void*>(a_at), &a_out, 4);
		}

		bool ReadI32(std::uintptr_t a_at, std::int32_t& a_out)
		{
			return ModuleRange().Has(a_at) && SafeRead(reinterpret_cast<const void*>(a_at), &a_out, 4);
		}

		std::string ReadName(std::uintptr_t a_typeDescriptor)
		{
			const auto name = a_typeDescriptor + 16;
			if (!ModuleRange().Has(name)) {
				return {};
			}
			char text[160]{};
			if (!SafeRead(reinterpret_cast<const void*>(name), text, sizeof(text) - 1) || text[0] != '.' || text[1] != '?') {
				return {};
			}
			return std::string{ text };
		}

		// The MSVC run-time type name of the object at this address, or "". vtable[-1] is the
		// complete-object locator; its type descriptor carries the decorated name.
		std::string TypeName(std::uintptr_t a_object)
		{
			const auto&    module = ModuleRange();
			std::uintptr_t vtable = 0;
			if (a_object % 8 != 0 || !SafeRead(reinterpret_cast<const void*>(a_object), &vtable, 8) || !module.Has(vtable)) {
				return {};
			}
			std::uintptr_t locator = 0;
			if (!SafeRead(reinterpret_cast<const void*>(vtable - 8), &locator, 8) || !module.Has(locator)) {
				return {};
			}
			std::uint32_t signature = 0;
			std::int32_t  typeRVA = 0;
			if (!ReadU32(locator, signature) || signature != 1 || !ReadI32(locator + 12, typeRVA)) {
				return {};
			}
			return ReadName(REL::Module::get().base() + static_cast<std::uintptr_t>(typeRVA));
		}

		// The event type T of the BSTEventSink<T> base a sink pointer points at, or "".
		std::string SinkEventType(std::uintptr_t a_sink)
		{
			const auto&    module = ModuleRange();
			const auto     base = REL::Module::get().base();
			std::uintptr_t vtable = 0;
			if (a_sink % 8 != 0 || !SafeRead(reinterpret_cast<const void*>(a_sink), &vtable, 8) || !module.Has(vtable)) {
				return {};
			}
			std::uintptr_t locator = 0;
			if (!SafeRead(reinterpret_cast<const void*>(vtable - 8), &locator, 8) || !module.Has(locator)) {
				return {};
			}
			std::uint32_t signature = 0;
			std::uint32_t subobjectOffset = 0;
			std::int32_t  classRVA = 0;
			if (!ReadU32(locator, signature) || signature != 1 || !ReadU32(locator + 4, subobjectOffset) ||
				!ReadI32(locator + 16, classRVA)) {
				return {};
			}
			const auto    hierarchy = base + static_cast<std::uintptr_t>(classRVA);
			std::uint32_t baseCount = 0;
			std::int32_t  arrayRVA = 0;
			if (!ReadU32(hierarchy + 8, baseCount) || !ReadI32(hierarchy + 12, arrayRVA) || baseCount > 256) {
				return {};
			}
			const auto array = base + static_cast<std::uintptr_t>(arrayRVA);
			for (std::uint32_t i = 0; i < baseCount; ++i) {
				std::int32_t descriptorRVA = 0;
				if (!ReadI32(array + i * 4, descriptorRVA)) {
					break;
				}
				const auto   descriptor = base + static_cast<std::uintptr_t>(descriptorRVA);
				std::int32_t typeRVA = 0;
				std::int32_t mdisp = 0;
				std::int32_t pdisp = 0;
				if (!ReadI32(descriptor, typeRVA) || !ReadI32(descriptor + 8, mdisp) || !ReadI32(descriptor + 12, pdisp)) {
					break;
				}
				if (pdisp != -1 || static_cast<std::uint32_t>(mdisp) != subobjectOffset) {
					continue;
				}
				const auto name = ReadName(base + static_cast<std::uintptr_t>(typeRVA));
				const auto at = name.find("BSTEventSink@");
				if (at == std::string::npos) {
					continue;
				}
				// "...BSTEventSink@UTESEquipEvent@@@@" -> between "@U"/"@V" and "@@"
				const auto start = at + 13;
				if (start + 1 >= name.size()) {
					continue;
				}
				const auto end = name.find("@@", start + 1);
				if (end == std::string::npos) {
					continue;
				}
				return name.substr(start + 1, end - start - 1);
			}
			return {};
		}

		// A BSTEventSource<T>: a spin lock, three BSTArrays of sinks (0x18 each), a counter.
		struct SourceView
		{
			std::uintptr_t              address{ 0 };
			std::vector<std::uintptr_t> sinks;
		};

		bool ReadSource(std::uintptr_t a_address, SourceView& a_out)
		{
			std::byte raw[0x58];
			if (!SafeRead(reinterpret_cast<const void*>(a_address), raw, sizeof(raw))) {
				return false;
			}
			const auto u64 = [&](std::size_t o) { std::uint64_t v = 0; std::memcpy(&v, raw + o, 8); return v; };
			const auto u32 = [&](std::size_t o) { std::uint32_t v = 0; std::memcpy(&v, raw + o, 4); return v; };
			for (const std::size_t base : { std::size_t{ 0x08 }, std::size_t{ 0x20 }, std::size_t{ 0x38 } }) {
				const auto data = u64(base);
				const auto capacity = u32(base + 8);
				const auto size = u32(base + 0x10);
				if ((data == 0) != (capacity == 0) || size > capacity || capacity > 4096) {
					return false;
				}
				if (data && ModuleRange().Has(data)) {
					return false;  // sink arrays live on the heap
				}
			}
			if (u32(4) > 64) {
				return false;  // a lock count this high is not a lock
			}
			a_out.address = a_address;
			a_out.sinks.clear();
			const auto data = u64(0x08);
			const auto count = u32(0x18);
			for (std::uint32_t i = 0; i < count && i < 64; ++i) {
				std::uintptr_t sink = 0;
				if (!SafeRead(reinterpret_cast<const void*>(data + i * 8), &sink, 8)) {
					break;
				}
				a_out.sinks.push_back(sink);
			}
			return true;
		}

		std::uintptr_t g_anchor = 0;

		void ReadAnchor(void*)
		{
			g_anchor = reinterpret_cast<std::uintptr_t>(RE::TESDeathEvent::GetEventSource());
		}

		std::uintptr_t Anchor()
		{
			static bool tried = false;
			if (!tried) {
				tried = true;
				if (!Guarded(&ReadAnchor, nullptr)) {
					g_anchor = 0;
					logger::error("events: the death source getter faulted; the holder cannot be anchored");
				}
			}
			return g_anchor;
		}

		// Members sit 0x60 apart (measured on 1.10.163: combat 7A20, container 7A80, death 7BA0,
		// furniture 8080, load 83E0).
		constexpr std::uintptr_t kStride = 0x60;
		constexpr int            kMaxMembers = 96;

		std::vector<SourceView> WalkHolder()
		{
			std::vector<SourceView> out;
			const auto              anchor = Anchor();
			if (!anchor) {
				return out;
			}
			std::vector<SourceView> below;
			for (int i = 1; i <= kMaxMembers; ++i) {
				SourceView v;
				if (!ReadSource(anchor - static_cast<std::uintptr_t>(i) * kStride, v)) {
					break;
				}
				below.push_back(v);
			}
			for (auto it = below.rbegin(); it != below.rend(); ++it) {
				out.push_back(*it);
			}
			for (int i = 0; i <= kMaxMembers; ++i) {
				SourceView v;
				if (!ReadSource(anchor + static_cast<std::uintptr_t>(i) * kStride, v)) {
					break;
				}
				out.push_back(v);
			}
			return out;
		}

		bool Carries(const std::string& a_rtti, std::string_view a_wrapper, std::string_view a_type)
		{
			const auto u = std::format("@U{}@@", a_type);
			const auto v = std::format("@V{}@@", a_type);
			if (a_rtti.find(a_wrapper) != std::string::npos &&
				(a_rtti.find(u) != std::string::npos || a_rtti.find(v) != std::string::npos)) {
				return true;
			}
			return a_rtti == std::format(".?AU{}Source@@", a_type) || a_rtti == std::format(".?AV{}Source@@", a_type);
		}
	}

	bool Guarded(void (*a_fn)(void*), void* a_context)
	{
		__try {
			a_fn(a_context);
			return true;
		} __except (1) {
			return false;
		}
	}

	std::uint32_t SafeFormID(const void* a_object)
	{
		const auto address = reinterpret_cast<std::uintptr_t>(a_object);
		if (!address || TypeName(address).empty()) {
			return 0;
		}
		std::uint32_t id = 0;
		if (!SafeRead(reinterpret_cast<const void*>(address + 0x14), &id, 4) || id == 0xFFFFFFFF) {
			return 0;
		}
		return id;
	}

	std::uint8_t SafeFormType(const void* a_object)
	{
		const auto address = reinterpret_cast<std::uintptr_t>(a_object);
		if (!address || TypeName(address).empty()) {
			return 0;
		}
		std::uint8_t type = 0;
		return SafeRead(reinterpret_cast<const void*>(address + 0x1A), &type, 1) ? type : 0;
	}

	std::uintptr_t FindHolderSource(std::string_view a_type)
	{
		for (const auto& member : WalkHolder()) {
			for (const auto sink : member.sinks) {
				if (SinkEventType(sink) == a_type) {
					return member.address;
				}
			}
		}
		return 0;
	}

	std::uintptr_t FindGlobalSource(std::string_view a_type)
	{
		auto* global = RE::BSTGlobalEvent::GetSingleton();
		if (!global) {
			return 0;
		}
		// A global source registers itself as a sink of BSTGlobalEvent's SDM-killer source, so that
		// sink list is the registry of every global source so far; _sinks sits at +0x08, behind the
		// source's own lock at +0x00. A source built on another thread registers into that list, which
		// can move it: it is copied under the lock, and read after.
		using Sink = RE::BSTEventSink<RE::BSTGlobalEvent::KillSDMEvent>*;
		const auto  killer = reinterpret_cast<std::uintptr_t>(&global->eventSourceSDMKiller);
		const auto* sinks = reinterpret_cast<const RE::BSTArray<Sink>*>(killer + 0x08);
		std::vector<std::uintptr_t> registered;
		{
			const RE::BSAutoLock locker{ *reinterpret_cast<RE::BSSpinLock*>(killer) };
			registered.reserve(sinks->size());
			for (const auto sink : *sinks) {
				registered.push_back(reinterpret_cast<std::uintptr_t>(sink));
			}
		}
		for (const auto address : registered) {
			const auto rtti = TypeName(address);
			if (rtti.empty() || !Carries(rtti, "?$EventSource@", a_type)) {
				continue;
			}
			// the value-request twin of the same event is a different source
			if (rtti.find("BSTValueRequestEvent") != std::string::npos) {
				continue;
			}
			return address;
		}
		return 0;
	}
}

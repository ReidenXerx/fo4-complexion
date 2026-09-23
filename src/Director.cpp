#include "Director.h"

namespace SH
{
	namespace
	{
		constexpr std::size_t kMaxEvents = 512;
		constexpr std::size_t kMaxLog = 512;

		bool Distributed(const Catalog& a_catalog, const ActorFacts& a_facts)
		{
			return std::ranges::any_of(a_catalog.races, [&](const std::string& r) { return IEquals(r, a_facts.race); });
		}

		// Every morph a set names, once, in the set's order.
		std::vector<std::string> MorphsOf(const RefitSet& a_set)
		{
			std::vector<std::string> out;
			for (const auto& e : a_set.entries) {
				if (std::ranges::find(out, e.morph) == out.end()) {
					out.push_back(e.morph);
				}
			}
			return out;
		}

		bool Generic(std::string_view a_set)
		{
			return IEquals(a_set, "Female-Refit") || IEquals(a_set, "Male-Refit") || a_set.starts_with("builtin:");
		}
	}

	// ------------------------------------------------------------------ lifecycle

	void Director::SetCatalog(std::shared_ptr<const Catalog> a_catalog)
	{
		std::scoped_lock l{ _lock };
		_catalog = std::move(a_catalog);
		if (_catalog) {
			std::size_t female = 0;
			for (const auto& p : _catalog->presets) {
				female += p.female ? 1 : 0;
			}
			_status = std::format("ready: build {} (stamp {}), {} female and {} male presets, {} rule(s) by name, {} by faction, {} refit set(s)",
				_catalog->build, _catalog->stamp, female, _catalog->presets.size() - female, _catalog->nameRules.size(),
				_catalog->factionRules.size(), _catalog->refitSets.size());
		}
	}

	void Director::Refuse(std::string a_why)
	{
		std::scoped_lock l{ _lock };
		_catalog.reset();
		_status = std::move(a_why);
	}

	bool Director::Ready() const
	{
		std::scoped_lock l{ _lock };
		return _catalog != nullptr;
	}

	std::string Director::Status() const
	{
		std::scoped_lock l{ _lock };
		return _status;
	}

	std::shared_ptr<const Catalog> Director::CatalogPtr() const
	{
		std::scoped_lock l{ _lock };
		return _catalog;
	}

	void Director::Configure(const Settings& a_settings)
	{
		std::scoped_lock l{ _lock };
		const bool refitChanged = a_settings.orefit != _settings.orefit;
		_settings = a_settings;
		if (!refitChanged) {
			return;
		}
		// Everyone seen this session follows at once; the rest follow when they are next seen, since
		// only then does anything say what they wear.
		for (const auto& [ref, session] : _sessions) {
			if (session.known) {
				ReconcileRefit(ref);
			}
		}
		Log(std::format("ORefit {} by the settings", _settings.orefit ? "on" : "off"));
	}

	Settings Director::Current() const
	{
		std::scoped_lock l{ _lock };
		return _settings;
	}

	void Director::ForgetWorld()
	{
		std::scoped_lock l{ _lock };
		_sessions.clear();
		_work.clear();
		_queue.clear();
		_inflight.clear();
		_busy.clear();
		_events.clear();
		_taken.clear();
		_picker = {};
	}

	void Director::RevertRecords()
	{
		std::scoped_lock l{ _lock };
		_registry.Clear();
	}

	// ------------------------------------------------------------------ what the game saw

	void Director::Admit(Session& a_session, const Sighting& a_sighting)
	{
		a_session.known = true;
		a_session.female = a_sighting.facts.female;
		a_session.base = a_sighting.base;
		if (a_session.clothed && a_sighting.clothed && a_session.outfitSet != a_sighting.outfitSet) {
			a_session.refitStale = true;  // another outfit, maybe another refit set
		}
		a_session.clothed = a_sighting.clothed;
		a_session.outfitSet = a_sighting.outfitSet;
		a_session.facts = a_sighting.facts;
		a_session.eligible = a_sighting.eligible && _catalog && Distributed(*_catalog, a_sighting.facts);
	}

	void Director::Seen(const Sighting& a_sighting)
	{
		std::scoped_lock l{ _lock };
		if (!_catalog) {
			return;
		}
		auto& session = _sessions[a_sighting.ref];
		Admit(session, a_sighting);
		if (!session.eligible) {
			return;
		}
		DecideBody(a_sighting.ref, session);
		ReconcileRefit(a_sighting.ref);
		if (!session.probed) {
			session.probed = true;
			const auto it = _work.find(a_sighting.ref);
			if (it == _work.end() || !it->second.body) {
				WorkFor(a_sighting.ref).probe = true;
			}
		}
	}

	void Director::Dressed(const Sighting& a_sighting, bool a_removedClothing)
	{
		std::scoped_lock l{ _lock };
		if (!_catalog) {
			return;
		}
		auto&      session = _sessions[a_sighting.ref];
		const bool knew = session.known;
		const bool was = session.clothed;
		Admit(session, a_sighting);
		if (!session.eligible) {
			return;
		}
		if (a_removedClothing) {
			Push(EventKind::kRemovingClothes, a_sighting.ref);
		}
		if (knew && was && !session.clothed) {
			Push(EventKind::kNaked, a_sighting.ref);
		}
		ReconcileRefit(a_sighting.ref);
	}

	// ------------------------------------------------------------------ deciding

	void Director::DecideBody(std::uint32_t a_ref, Session& a_session)
	{
		const auto& c = *_catalog;
		auto*       rec = _registry.Find(a_ref);
		if (rec && rec->base != 0 && a_session.base != 0 && rec->base != a_session.base) {
			// A created reference's id, handed to someone new: the record was about somebody else.
			Log(std::format("{:08X}: the record was for NPC {:08X}, this is {:08X} - forgotten", a_ref, rec->base, a_session.base));
			_registry.Erase(a_ref);
			rec = nullptr;
		}
		if (_picker.ref == a_ref) {
			return;  // the player is choosing
		}
		if (const auto it = _work.find(a_ref); it != _work.end() && it->second.body) {
			return;  // a change is already on its way
		}
		for (const auto& [id, order] : _inflight) {
			if (order.ref == a_ref && order.kind == OrderKind::kBody) {
				return;
			}
		}

		// A choice somebody made stays made; a new build gives it this build's values.
		if (rec && (rec->source == Source::kPicker || rec->source == Source::kAPI)) {
			if (rec->stamp != c.stamp) {
				if (c.Find(rec->preset, a_session.female)) {
					Log(std::format("{:08X}: {} ({}) again, with build {}'s values", a_ref, rec->preset, SourceName(rec->source), c.build));
					Queue(a_ref, BodyRequest{ .what = BodyRequest::What::kPreset, .preset = rec->preset, .source = rec->source });
				} else {
					Log(std::format("{:08X}: {} ({}) is not in build {}; their body stays as it is", a_ref, rec->preset, SourceName(rec->source), c.build));
					rec->stamp = c.stamp;  // said once, not on every sighting
				}
			}
			return;
		}

		const auto verdict = Decide(c, a_session.facts);
		switch (verdict.tier) {
		case Tier::kName:
		case Tier::kFaction:
			{
				const auto source = verdict.tier == Tier::kName ? Source::kNameRule : Source::kFactionRule;
				if (!(rec && rec->source == source && rec->preset == verdict.preset && rec->stamp == c.stamp)) {
					Log(std::format("{:08X} \"{}\": {}", a_ref, a_session.facts.baseName, verdict.why));
					Queue(a_ref, BodyRequest{ .what = BodyRequest::What::kPreset, .preset = verdict.preset, .source = source });
				}
				break;
			}
		case Tier::kNameBlacklist:
			if (!(rec && rec->source == Source::kNameBlacklist)) {
				Log(std::format("{:08X}: {}", a_ref, verdict.why));
				Queue(a_ref, BodyRequest{ .what = BodyRequest::What::kBlacklist });
			}
			break;
		case Tier::kNone:
			if (rec && (rec->source == Source::kNameRule || rec->source == Source::kFactionRule)) {
				// The rule is gone. Their body is a real one, so it stays; it is just no longer ours.
				Log(std::format("{:08X} \"{}\": no rule gives them {} any more; it stays, as BodyGen's", a_ref, a_session.facts.baseName, rec->preset));
				rec->source = Source::kNone;
				rec->preset.clear();
				_registry.Prune(a_ref);
			} else if (rec && rec->source == Source::kNameBlacklist) {
				Log(std::format("{:08X} \"{}\": no longer blacklisted - BodyGen rolls them", a_ref, a_session.facts.baseName));
				Queue(a_ref, BodyRequest{ .what = BodyRequest::What::kRegenerate });
			}
			break;
		}
	}

	bool Director::AnyRefitSet(bool a_female) const
	{
		return std::ranges::any_of(_catalog->refitSets, [&](const RefitSet& s) { return s.female == a_female; });
	}

	bool Director::PresetRefitSets(bool a_female) const
	{
		return std::ranges::any_of(_catalog->refitSets, [&](const RefitSet& s) {
			return s.female == a_female && !Generic(s.name) && s.name.ends_with("-Refit");
		});
	}

	bool Director::WantsRefit(const Session& a_session) const
	{
		return _catalog && _settings.orefit && _catalog->orefitEnabled && a_session.known && a_session.eligible &&
		       a_session.clothed && AnyRefitSet(a_session.female);
	}

	void Director::ReconcileRefit(std::uint32_t a_ref, bool a_front)
	{
		const auto it = _sessions.find(a_ref);
		if (it == _sessions.end() || !it->second.known) {
			return;
		}
		const bool  want = WantsRefit(it->second);
		const auto* rec = _registry.Find(a_ref);
		const bool  applied = rec && rec->refitApplied;
		if (want != applied || (want && it->second.refitStale)) {
			WorkFor(a_ref, a_front).refit = true;
		}
	}

	Director::Work& Director::WorkFor(std::uint32_t a_ref, bool a_front)
	{
		auto [it, inserted] = _work.try_emplace(a_ref);
		if (inserted) {
			if (a_front) {
				_queue.push_front(a_ref);
			} else {
				_queue.push_back(a_ref);
			}
		} else if (a_front) {
			if (const auto at = std::ranges::find(_queue, a_ref); at != _queue.end()) {
				_queue.erase(at);
			}
			_queue.push_front(a_ref);
		}
		return it->second;
	}

	void Director::Queue(std::uint32_t a_ref, BodyRequest a_body, bool a_front)
	{
		WorkFor(a_ref, a_front).body = std::move(a_body);  // the latest decision wins
	}

	// ------------------------------------------------------------------ requests

	bool Director::RequestPreset(std::uint32_t a_ref, bool a_female, std::uint32_t a_base, std::string_view a_preset, Source a_source, std::string& a_why)
	{
		std::scoped_lock l{ _lock };
		if (!_catalog) {
			a_why = _status;
			return false;
		}
		if (!_catalog->Find(a_preset, a_female)) {
			a_why = std::format("there is no preset \"{}\" for a {} body", a_preset, a_female ? "female" : "male");
			return false;
		}
		auto& session = _sessions[a_ref];
		if (!session.known) {
			session.female = a_female;
			session.base = a_base;
		}
		if (_picker.ref == a_ref) {
			ClosePicker();  // a decision made elsewhere ends the trying-on; it is what they get
		}
		Queue(a_ref, BodyRequest{ .what = BodyRequest::What::kPreset, .preset = std::string{ a_preset }, .source = a_source });
		return true;
	}

	bool Director::RequestRegenerate(std::uint32_t a_ref, bool a_female, std::uint32_t a_base)
	{
		std::scoped_lock l{ _lock };
		if (!_catalog) {
			return false;
		}
		auto& session = _sessions[a_ref];
		if (!session.known) {
			session.female = a_female;
			session.base = a_base;
		}
		if (_picker.ref == a_ref) {
			ClosePicker();
		}
		Queue(a_ref, BodyRequest{ .what = BodyRequest::What::kRegenerate });
		return true;
	}

	bool Director::RequestReset(std::uint32_t a_ref, bool a_female, std::uint32_t a_base)
	{
		std::scoped_lock l{ _lock };
		if (!_catalog) {
			return false;
		}
		auto& session = _sessions[a_ref];
		if (!session.known) {
			session.female = a_female;
			session.base = a_base;
		}
		if (_picker.ref == a_ref) {
			ClosePicker();
		}
		Queue(a_ref, BodyRequest{ .what = BodyRequest::What::kReset });
		return true;
	}

	bool Director::RequestReapply(std::uint32_t a_ref, bool a_female, std::uint32_t a_base, std::string_view a_markerPreset, std::string& a_why)
	{
		std::scoped_lock l{ _lock };
		if (!_catalog) {
			a_why = _status;
			return false;
		}
		const auto* rec = _registry.Find(a_ref);
		const bool  ours = rec && !rec->preset.empty() && rec->source != Source::kNone;
		std::string preset = ours ? rec->preset : std::string{ a_markerPreset };
		if (preset.empty()) {
			a_why = "they have no Silhouette body to give again";
			return false;
		}
		if (!_catalog->Find(preset, a_female)) {
			a_why = std::format("\"{}\" is not in this build", preset);
			return false;
		}
		auto& session = _sessions[a_ref];
		if (!session.known) {
			session.female = a_female;
			session.base = a_base;
		}
		Queue(a_ref, BodyRequest{ .what = BodyRequest::What::kPreset, .preset = preset, .source = ours ? rec->source : Source::kNone });
		return true;
	}

	// ------------------------------------------------------------------ the bridge

	std::uint32_t Director::NextOrder()
	{
		std::scoped_lock l{ _lock };
		if (!_catalog) {
			return 0;
		}
		for (std::size_t i = 0; i < _queue.size();) {
			const auto ref = _queue[i];
			const auto wit = _work.find(ref);
			if (wit == _work.end() || wit->second.Empty()) {
				_work.erase(ref);
				_queue.erase(_queue.begin() + static_cast<std::ptrdiff_t>(i));
				continue;
			}
			if (_busy.contains(ref)) {
				++i;  // one order per actor at a time: theirs come in the order they were decided
				continue;
			}
			auto&      w = wit->second;
			const auto sit = _sessions.find(ref);
			if (sit == _sessions.end()) {
				_work.erase(wit);
				_queue.erase(_queue.begin() + static_cast<std::ptrdiff_t>(i));
				continue;
			}
			auto& session = sit->second;

			Order o;
			o.ref = ref;
			o.female = session.female;
			bool made = false;
			if (w.snapshot) {
				w.snapshot = false;
				o.kind = OrderKind::kSnapshot;
				o.readAll = true;
				o.probe = true;
				made = true;
			} else if (w.body) {
				o.kind = OrderKind::kBody;
				o.body = std::move(*w.body);
				w.body.reset();
				if (o.body.what == BodyRequest::What::kRegenerate) {
					o.regenerate = true;
					o.probe = true;
				}
				made = true;
			} else if (w.refit) {
				w.refit = false;
				const bool  want = WantsRefit(session);
				const auto* rec = _registry.Find(ref);
				const bool  applied = rec && rec->refitApplied;
				if (applied && (!want || session.refitStale)) {
					o.kind = OrderKind::kRefit;
					o.refitOn = false;
					made = true;
				} else if (want && !applied) {
					o.kind = OrderKind::kRefit;
					o.refitOn = true;
					o.probe = PresetRefitSets(session.female);  // "<Preset>-Refit" needs to know the preset
					made = true;
				}
				session.refitStale = false;
			} else if (w.probe) {
				w.probe = false;
				o.kind = OrderKind::kProbe;
				o.probe = true;
				made = true;
			}
			if (w.Empty()) {
				_work.erase(wit);
				_queue.erase(_queue.begin() + static_cast<std::ptrdiff_t>(i));
			}
			if (!made) {
				continue;  // nothing left to do for them after all; the same slot holds the next actor
			}
			o.id = _nextOrder++;
			if (_nextOrder == 0) {
				_nextOrder = 1;
			}
			const auto id = o.id;
			_busy.insert(ref);
			_inflight.emplace(id, std::move(o));
			return id;
		}
		return 0;
	}

	std::optional<Order> Director::Peek(std::uint32_t a_order) const
	{
		std::scoped_lock l{ _lock };
		const auto       it = _inflight.find(a_order);
		if (it == _inflight.end()) {
			return std::nullopt;
		}
		return it->second;
	}

	Order* Director::Find(std::uint32_t a_order)
	{
		const auto it = _inflight.find(a_order);
		return it == _inflight.end() ? nullptr : &it->second;
	}

	void Director::NoteMarker(std::uint32_t a_order, std::string_view a_marker, float a_value)
	{
		std::scoped_lock l{ _lock };
		if (auto* o = Find(a_order)) {
			// A body carries one marker. If the layer somehow holds two, the one with a value that is
			// a real stamp wins; a leftover of 0 is what "removed" looks like (the name stays listed).
			if (a_value > 0.0F && (o->marker.empty() || o->markerValue <= 0.0F)) {
				o->marker = std::string{ a_marker };
				o->markerValue = a_value;
			}
		}
	}

	std::int32_t Director::ReadCount(std::uint32_t a_order)
	{
		std::scoped_lock l{ _lock };
		auto*            o = Find(a_order);
		if (!o || !_catalog) {
			return 0;
		}
		if (o->kind == OrderKind::kRefit && o->refitOn && !o->readsDecided) {
			// Decided now, after the probe: "<Preset>-Refit" can only be chosen once the preset is known.
			o->readsDecided = true;
			const auto  session = _sessions.find(o->ref);
			const auto  outfit = session == _sessions.end() ? std::string{} : session->second.outfitSet;
			const auto  preset = PresetNamedBy(o->marker, o->markerValue);
			const auto* set = _catalog->RefitFor(preset, o->female, outfit);
			if (set) {
				o->refitSet = set->name;
				o->reads = MorphsOf(*set);
				o->readValues.assign(o->reads.size(), std::numeric_limits<float>::quiet_NaN());
			}
		}
		return static_cast<std::int32_t>(o->reads.size());
	}

	std::string Director::ReadMorph(std::uint32_t a_order, std::int32_t a_index) const
	{
		std::scoped_lock l{ _lock };
		const auto       it = _inflight.find(a_order);
		if (it == _inflight.end() || a_index < 0 || static_cast<std::size_t>(a_index) >= it->second.reads.size()) {
			return {};
		}
		return it->second.reads[static_cast<std::size_t>(a_index)];
	}

	void Director::NoteRead(std::uint32_t a_order, std::int32_t a_index, float a_value)
	{
		std::scoped_lock l{ _lock };
		if (auto* o = Find(a_order); o && a_index >= 0 && static_cast<std::size_t>(a_index) < o->readValues.size()) {
			o->readValues[static_cast<std::size_t>(a_index)] = a_value;
		}
	}

	void Director::NoteLayer(std::uint32_t a_order, std::string_view a_morph, float a_value)
	{
		std::scoped_lock l{ _lock };
		if (auto* o = Find(a_order); o && o->readAll && !a_morph.empty() && a_value != 0.0F) {
			const auto it = std::ranges::find_if(o->layer, [&](const auto& p) { return p.first == a_morph; });
			if (it == o->layer.end()) {
				o->layer.emplace_back(std::string{ a_morph }, a_value);
			} else {
				it->second = a_value;
			}
		}
	}

	bool Director::Prepare(std::uint32_t a_order)
	{
		std::scoped_lock l{ _lock };
		auto*            o = Find(a_order);
		if (!o || !_catalog) {
			return false;
		}
		const auto& c = *_catalog;
		o->prepared = true;
		o->clear = false;
		o->writes.clear();
		o->update = false;

		switch (o->kind) {
		case OrderKind::kProbe:
		case OrderKind::kSnapshot:
			return true;
		case OrderKind::kBody:
			switch (o->body.what) {
			case BodyRequest::What::kPreset:
				{
					const auto* p = c.Find(o->body.preset, o->female);
					if (!p) {
						Log(std::format("{:08X}: no preset \"{}\" for a {} body in this build", o->ref, o->body.preset, o->female ? "female" : "male"));
						return false;
					}
					o->clear = true;
					o->writes = BodyFor(c, *p, o->ref, _settings.variety);
					o->update = true;
					return true;
				}
			case BodyRequest::What::kBlacklist:
				o->clear = true;
				o->writes = { { c.blacklistMarker, static_cast<float>(c.stamp) } };
				o->update = true;
				return true;
			case BodyRequest::What::kRestore:
				o->clear = true;
				for (const auto& [morph, value] : o->body.restore) {
					if (std::abs(value) >= 1e-6F) {
						o->writes.emplace_back(morph, value);
					}
				}
				o->update = true;
				return true;
			case BodyRequest::What::kRegenerate:
				o->update = true;  // after the bridge put the keyed morphs back
				return true;
			case BodyRequest::What::kReset:
				o->clear = true;
				o->update = true;
				return true;
			}
			return false;
		case OrderKind::kRefit:
			if (o->refitOn) {
				const auto* set = c.FindRefit(o->refitSet, o->female);
				if (!set) {
					return false;  // ReadCount found no set for them
				}
				std::unordered_map<std::string, float> now;
				for (std::size_t i = 0; i < o->reads.size(); ++i) {
					const float v = o->readValues[i];
					if (std::isnan(v)) {
						Log(std::format("{:08X}: the bridge did not read {} - no refit", o->ref, o->reads[i]));
						return false;
					}
					now[o->reads[i]] = v;
				}
				o->writes = ApplyRefit(*set, now);
				o->refitSnapshot.clear();
				for (const auto& m : o->reads) {
					o->refitSnapshot.emplace_back(m, now[m]);
				}
				o->update = true;
				return true;
			} else {
				const auto* rec = _registry.Find(o->ref);
				if (rec && rec->refitApplied) {
					o->writes = rec->snapshot;  // zeroes included: they erase the refit's values
				}
				o->update = !o->writes.empty();
				return true;
			}
		}
		return false;
	}

	bool Director::Clears(std::uint32_t a_order) const
	{
		std::scoped_lock l{ _lock };
		const auto       it = _inflight.find(a_order);
		return it != _inflight.end() && it->second.prepared && it->second.clear;
	}

	bool Director::Updates(std::uint32_t a_order) const
	{
		std::scoped_lock l{ _lock };
		const auto       it = _inflight.find(a_order);
		return it != _inflight.end() && it->second.prepared && it->second.update;
	}

	std::int32_t Director::WriteCount(std::uint32_t a_order) const
	{
		std::scoped_lock l{ _lock };
		const auto       it = _inflight.find(a_order);
		return it == _inflight.end() || !it->second.prepared ? 0 : static_cast<std::int32_t>(it->second.writes.size());
	}

	std::string Director::WriteMorph(std::uint32_t a_order, std::int32_t a_index) const
	{
		std::scoped_lock l{ _lock };
		const auto       it = _inflight.find(a_order);
		if (it == _inflight.end() || a_index < 0 || static_cast<std::size_t>(a_index) >= it->second.writes.size()) {
			return {};
		}
		return it->second.writes[static_cast<std::size_t>(a_index)].first;
	}

	float Director::WriteValue(std::uint32_t a_order, std::int32_t a_index) const
	{
		std::scoped_lock l{ _lock };
		const auto       it = _inflight.find(a_order);
		if (it == _inflight.end() || a_index < 0 || static_cast<std::size_t>(a_index) >= it->second.writes.size()) {
			return 0.0F;
		}
		return it->second.writes[static_cast<std::size_t>(a_index)].second;
	}

	void Director::Done(std::uint32_t a_order, bool a_ok)
	{
		std::scoped_lock l{ _lock };
		const auto       it = _inflight.find(a_order);
		if (it == _inflight.end()) {
			return;
		}
		Order o = std::move(it->second);
		_inflight.erase(it);
		_busy.erase(o.ref);
		if (!_catalog) {
			return;
		}
		if (!a_ok) {
			Log(std::format("{:08X}: order {} ({}) not completed by the bridge", o.ref, o.id, static_cast<int>(o.kind)));
			if (o.kind == OrderKind::kSnapshot && _picker.ref == o.ref) {
				ClosePicker();  // without the snapshot a Cancel could not put them back
			}
			return;
		}
		switch (o.kind) {
		case OrderKind::kProbe:
			Announce(o);
			break;
		case OrderKind::kSnapshot:
			if (_picker.ref == o.ref) {
				const auto* rec = _registry.Find(o.ref);
				_picker.snapshot = Unrefit(o.layer, rec && rec->refitApplied ? rec->snapshot : Morphs{});
				_picker.snapped = true;
				_picker.current = PresetNamedBy(o.marker, o.markerValue);
			}
			Announce(o);
			break;
		case OrderKind::kBody:
			FinishBody(o);
			break;
		case OrderKind::kRefit:
			FinishRefit(o);
			break;
		}
	}

	std::size_t Director::Pending() const
	{
		std::scoped_lock l{ _lock };
		return _queue.size() + _inflight.size();
	}

	void Director::Announce(const Order& a_order)
	{
		if (a_order.marker.empty() || a_order.marker == _catalog->blacklistMarker) {
			return;
		}
		const auto stamp = static_cast<std::uint32_t>(std::lround(a_order.markerValue));
		const auto hash = BodyHash(a_order.marker, stamp);
		if (const auto* rec = _registry.Find(a_order.ref); rec && rec->announced == hash) {
			return;
		}
		const auto preset = PresetNamedBy(a_order.marker, a_order.markerValue);
		if (preset.empty()) {
			Log(std::format("{:08X}: marker {} of build stamp {} names no preset this install knows", a_order.ref, a_order.marker, stamp));
			return;
		}
		auto& rec = _registry.Get(a_order.ref);
		if (rec.base == 0) {
			if (const auto s = _sessions.find(a_order.ref); s != _sessions.end()) {
				rec.base = s->second.base;
			}
		}
		rec.announced = hash;
		Push(EventKind::kGenerated, a_order.ref, preset);
	}

	std::string Director::PresetNamedBy(std::string_view a_marker, float a_value) const
	{
		if (a_marker.empty() || !(a_value > 0.0F) || a_value >= 16777216.0F) {
			return {};
		}
		return _catalog->PresetForMarker(a_marker, static_cast<std::uint32_t>(std::lround(a_value))).value_or(std::string{});
	}

	void Director::FinishBody(Order& a_order)
	{
		const auto& c = *_catalog;
		const auto  ref = a_order.ref;
		const auto  sit = _sessions.find(ref);
		Session*    session = sit == _sessions.end() ? nullptr : &sit->second;

		{
			auto& rec = _registry.Get(ref);
			if (session && session->base != 0) {
				rec.base = session->base;
			}
			// The unkeyed layer was replaced, and a refit's values with it.
			rec.refitApplied = false;
			rec.refitSet.clear();
			rec.snapshot.clear();

			switch (a_order.body.what) {
			case BodyRequest::What::kPreset:
				if (!a_order.body.preview) {
					rec.source = a_order.body.source;
					rec.preset = a_order.body.preset;
					rec.stamp = c.stamp;
					const auto* p = c.Find(a_order.body.preset, a_order.female);
					rec.announced = p ? BodyHash(p->marker, c.stamp) : 0;
					Push(EventKind::kGenerated, ref, a_order.body.preset);
					if (session && session->known && !session->clothed) {
						Push(EventKind::kNaked, ref);  // OBody raises it for a body generated naked
					}
				}
				break;
			case BodyRequest::What::kBlacklist:
				rec.source = Source::kNameBlacklist;
				rec.preset.clear();
				rec.stamp = c.stamp;
				rec.announced = 0;
				break;
			case BodyRequest::What::kRestore:
				{
					auto back = a_order.body.restoreRecord.value_or(Record{});
					back.refitApplied = false;
					back.refitSet.clear();
					back.snapshot.clear();
					if (back.base == 0) {
						back.base = rec.base;
					}
					rec = std::move(back);
					break;
				}
			case BodyRequest::What::kRegenerate:
			case BodyRequest::What::kReset:
				rec.source = Source::kNone;
				rec.preset.clear();
				rec.announced = 0;
				break;
			}
		}

		if (a_order.body.what == BodyRequest::What::kRegenerate) {
			Announce(a_order);  // the probe after the roll: BodyGen's new body
			if (session && session->known && session->eligible) {
				DecideBody(ref, *session);  // generated as if new, so the rules get their say again
			}
		}
		_registry.Prune(ref);
		ReconcileRefit(ref, true);  // clothed: the new body gets its refit next, before anyone else's work
	}

	void Director::FinishRefit(Order& a_order)
	{
		if (a_order.refitOn) {
			auto& rec = _registry.Get(a_order.ref);
			if (rec.base == 0) {
				if (const auto s = _sessions.find(a_order.ref); s != _sessions.end()) {
					rec.base = s->second.base;
				}
			}
			rec.refitApplied = true;
			rec.refitSet = a_order.refitSet;
			rec.snapshot = std::move(a_order.refitSnapshot);
			Push(EventKind::kORefitChanged, a_order.ref, {}, true);
		} else {
			if (auto* rec = _registry.Find(a_order.ref)) {
				rec->refitApplied = false;
				rec->refitSet.clear();
				rec->snapshot.clear();
				_registry.Prune(a_order.ref);
			}
			Push(EventKind::kORefitChanged, a_order.ref, {}, false);
		}
		ReconcileRefit(a_order.ref, true);  // they may have dressed or undressed while it ran
	}

	// ------------------------------------------------------------------ events

	void Director::Push(EventKind a_kind, std::uint32_t a_ref, std::string a_preset, bool a_flag)
	{
		if (_events.size() >= kMaxEvents) {
			_events.pop_front();
			if (!_eventsDropped) {
				Log("events: the bridge is not taking them; the oldest are dropped");
				_eventsDropped = true;
			}
		}
		_events.push_back(Event{ .id = _nextEvent++, .kind = a_kind, .ref = a_ref, .preset = std::move(a_preset), .flag = a_flag });
		if (_nextEvent == 0) {
			_nextEvent = 1;
		}
	}

	std::uint32_t Director::NextEvent()
	{
		std::scoped_lock l{ _lock };
		if (_events.empty()) {
			return 0;
		}
		_eventsDropped = false;
		_taken.push_back(std::move(_events.front()));
		_events.pop_front();
		if (_taken.size() > 64) {
			_taken.pop_front();
		}
		return _taken.back().id;
	}

	std::optional<Event> Director::EventAt(std::uint32_t a_event) const
	{
		std::scoped_lock l{ _lock };
		for (const auto& e : _taken) {
			if (e.id == a_event) {
				return e;
			}
		}
		return std::nullopt;
	}

	// ------------------------------------------------------------------ the picker

	void Director::ClosePicker()
	{
		_picker = {};
	}

	std::string Director::CancelPicking()
	{
		const auto name = _picker.name;
		if (_picker.index < 0) {
			ClosePicker();
			return std::format("{} keeps the body they had.", name);
		}
		Queue(_picker.ref, BodyRequest{ .what = BodyRequest::What::kRestore, .restore = _picker.snapshot, .restoreRecord = _picker.before }, true);
		const auto back = _picker.current.empty() ? std::string{ "the body they had" } : _picker.current;
		ClosePicker();
		return std::format("{} is back to {}.", name, back);
	}

	std::string Director::PickerStart(std::uint32_t a_ref, bool a_female, std::uint32_t a_base, std::string_view a_name)
	{
		std::scoped_lock l{ _lock };
		if (!_catalog) {
			return std::format("Silhouette is not ready: {}", _status);
		}
		std::string before;
		if (_picker.ref == a_ref) {
			return std::format("{} is already picked: Next / Previous try presets, Keep or Cancel ends it.", _picker.name);
		}
		if (_picker.ref != 0) {
			before = CancelPicking() + " ";
		}
		std::vector<std::string> presets;
		for (const auto* p : _catalog->MenuPresets(a_female)) {
			presets.push_back(p->name);
		}
		if (presets.empty()) {
			return before + std::format("There are no presets for a {} body in this build.", a_female ? "female" : "male");
		}
		auto& session = _sessions[a_ref];
		if (!session.known) {
			session.female = a_female;
			session.base = a_base;
		}
		_picker = {};
		_picker.ref = a_ref;
		_picker.female = a_female;
		_picker.base = a_base;
		_picker.name = a_name.empty() ? std::format("{:08X}", a_ref) : std::string{ a_name };
		_picker.presets = std::move(presets);
		if (const auto* rec = _registry.Find(a_ref)) {
			_picker.before = *rec;
		}
		WorkFor(a_ref, true).snapshot = true;
		return before + std::format("{} picked. Next / Previous try their {} presets; Keep or Cancel ends it.", _picker.name, _picker.presets.size());
	}

	std::string Director::PickerStep(std::int32_t a_step)
	{
		std::scoped_lock l{ _lock };
		if (_picker.ref == 0) {
			return "Pick an NPC first: aim at them and press Pick.";
		}
		if (!_picker.snapped) {
			return std::format("Still reading {}'s body - a moment.", _picker.name);
		}
		const auto n = static_cast<std::int32_t>(_picker.presets.size());
		if (a_step == 0) {
			a_step = 1;
		}
		if (_picker.index < 0) {
			// Nothing tried on yet: Next is the first preset, Previous the last.
			_picker.index = a_step > 0 ? (a_step - 1) % n : ((n + a_step % n) % n);
		} else {
			_picker.index = ((_picker.index + a_step) % n + n) % n;
		}
		const auto& preset = _picker.presets[static_cast<std::size_t>(_picker.index)];
		Queue(_picker.ref, BodyRequest{ .what = BodyRequest::What::kPreset, .preset = preset, .source = Source::kPicker, .preview = true }, true);
		return std::format("{}: {} ({}/{})", _picker.name, preset, _picker.index + 1, n);
	}

	std::string Director::PickerKeep()
	{
		std::scoped_lock l{ _lock };
		if (_picker.ref == 0) {
			return "Nobody is picked.";
		}
		if (_picker.index < 0) {
			const auto name = _picker.name;
			ClosePicker();
			return std::format("{} keeps the body they had.", name);
		}
		const auto& c = *_catalog;
		const auto  preset = _picker.presets[static_cast<std::size_t>(_picker.index)];
		auto&       rec = _registry.Get(_picker.ref);
		if (_picker.base != 0) {
			rec.base = _picker.base;
		}
		rec.source = Source::kPicker;
		rec.preset = preset;
		rec.stamp = c.stamp;
		const auto* p = c.Find(preset, _picker.female);
		rec.announced = p ? BodyHash(p->marker, c.stamp) : 0;
		Push(EventKind::kGenerated, _picker.ref, preset);
		const auto name = _picker.name;
		ClosePicker();
		return std::format("{} keeps {}.", name, preset);
	}

	std::string Director::PickerCancel()
	{
		std::scoped_lock l{ _lock };
		if (_picker.ref == 0) {
			return "Nobody is picked.";
		}
		return CancelPicking();
	}

	std::uint32_t Director::PickerTarget() const
	{
		std::scoped_lock l{ _lock };
		return _picker.ref;
	}

	bool Director::PickerReady() const
	{
		std::scoped_lock l{ _lock };
		return _picker.ref != 0 && _picker.snapped;
	}

	// ------------------------------------------------------------------ queries

	std::string Director::AssignedPreset(std::uint32_t a_ref) const
	{
		std::scoped_lock l{ _lock };
		if (const auto it = _work.find(a_ref); it != _work.end() && it->second.body &&
												it->second.body->what == BodyRequest::What::kPreset && !it->second.body->preview) {
			return it->second.body->preset;
		}
		for (const auto& [id, o] : _inflight) {
			if (o.ref == a_ref && o.kind == OrderKind::kBody && o.body.what == BodyRequest::What::kPreset && !o.body.preview) {
				return o.body.preset;
			}
		}
		if (_picker.ref == a_ref && _picker.before) {
			return _picker.before->preset;
		}
		const auto* rec = _registry.Find(a_ref);
		return rec ? rec->preset : std::string{};
	}

	bool Director::RefitApplied(std::uint32_t a_ref) const
	{
		std::scoped_lock l{ _lock };
		const auto*      rec = _registry.Find(a_ref);
		return rec && rec->refitApplied;
	}

	std::string Director::Describe(std::uint32_t a_ref) const
	{
		std::scoped_lock l{ _lock };
		const auto*      rec = _registry.Find(a_ref);
		std::string      out;
		if (!rec || rec->source == Source::kNone) {
			out = "their body is BodyGen's";
		} else if (rec->source == Source::kNameBlacklist) {
			out = "blacklisted by name: kept bare";
		} else {
			out = std::format("{} ({})", rec->preset, SourceName(rec->source));
		}
		if (rec && rec->refitApplied) {
			out += std::format("; clothed, refit by {}", rec->refitSet);
		}
		return out;
	}

	// ------------------------------------------------------------------ the co-save

	std::vector<std::byte> Director::SaveRecords(const std::function<bool(std::uint32_t)>& a_keep) const
	{
		std::scoped_lock l{ _lock };
		return _registry.Serialize(a_keep);
	}

	bool Director::LoadRecords(std::span<const std::byte> a_bytes, std::uint32_t a_version,
		const std::function<std::uint32_t(std::uint32_t)>& a_resolve, std::string& a_error)
	{
		std::scoped_lock l{ _lock };
		return _registry.Deserialize(a_bytes, a_version, a_resolve, a_error);
	}

	std::size_t Director::RecordCount() const
	{
		std::scoped_lock l{ _lock };
		return _registry.Size();
	}

	std::optional<Record> Director::RecordOf(std::uint32_t a_ref) const
	{
		std::scoped_lock l{ _lock };
		const auto*      rec = _registry.Find(a_ref);
		return rec ? std::optional<Record>{ *rec } : std::nullopt;
	}

	void Director::Log(std::string a_line)
	{
		if (_log.size() >= kMaxLog) {
			_log.erase(_log.begin());
		}
		_log.push_back(std::move(a_line));
	}

	std::vector<std::string> Director::TakeLog()
	{
		std::scoped_lock l{ _lock };
		return std::exchange(_log, {});
	}
}

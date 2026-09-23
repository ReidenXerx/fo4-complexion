#include "Director.h"

namespace SH
{
	namespace
	{
		constexpr std::size_t kMaxEvents = 512;
		constexpr std::size_t kMaxLog = 512;
		constexpr std::size_t kBodyReads = 5;  // own values read to tell a body from nothing (S-41)
		constexpr float       kRefitPending = 0.25F;  // the refit marker while a refit is being written
		constexpr int         kRefitUnfinished = 99;  // what a probe makes of a pending marker

		bool Distributed(const Catalog& a_catalog, const ActorFacts& a_facts)
		{
			return std::ranges::any_of(a_catalog.races, [&](const std::string& r) { return IEquals(r, a_facts.race); });
		}

		// Ids start somewhere new each launch: a script stack a save resumed may still hold an id from
		// the last launch, and it must not name one of this launch's orders (S-43).
		std::uint32_t RandomStart()
		{
			std::random_device rd;
			return 0x100000u + (rd() % 0x3F000000u);
		}

		std::uint32_t Next(std::uint32_t& a_counter)
		{
			const auto id = a_counter++;
			if (a_counter == 0 || a_counter >= 0x7FFFFFF0u) {
				a_counter = 0x100000u;  // stays a positive Papyrus Int, never 0
			}
			return id;
		}

		std::uint32_t Stamp(float a_value)
		{
			return a_value > 0.0F && a_value < 16777216.0F ? static_cast<std::uint32_t>(std::lround(a_value)) : 0;
		}
	}

	Director::Director() :
		_nextOrder(RandomStart()), _nextEvent(RandomStart())
	{}

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
		if (!refitChanged || !_catalog) {
			return;
		}
		// Everyone seen this session follows at once; the rest follow when they are next seen.
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

	Verdict Director::Admit(Session& a_session, const Sighting& a_sighting)
	{
		const auto ref = a_sighting.ref;
		// A created reference's id, handed to someone new: what we knew was about somebody else. Only a
		// created (0xFF) reference can be. A placed one is its NPC for good, and a leveled one's base is a
		// temporary record the engine replaces when it respawns, while LooksMenu keeps its morphs.
		const bool created = (ref >> 24) == 0xFF;
		if (created && a_session.known && a_session.base != 0 && a_sighting.base != 0 && a_session.base != a_sighting.base) {
			a_session = {};
			if (const auto w = _work.find(ref); w != _work.end()) {
				w->second = {};
			}
		}
		if (const auto* rec = _registry.Find(ref); created && rec && rec->base != 0 && a_sighting.base != 0 && rec->base != a_sighting.base) {
			Log(std::format("{:08X}: the record was for NPC {:08X}, this is {:08X} - forgotten", ref, rec->base, a_sighting.base));
			_registry.Erase(ref);
		}
		a_session.known = true;
		a_session.female = a_sighting.facts.female;
		a_session.base = a_sighting.base;
		a_session.clothed = a_sighting.clothed;
		a_session.heavy = a_sighting.heavy;
		a_session.outfitSet = a_sighting.outfitSet;
		a_session.facts = a_sighting.facts;
		a_session.eligible = a_sighting.eligible && Distributed(*_catalog, a_sighting.facts);
		const auto verdict = Decide(*_catalog, a_sighting.facts);
		a_session.blacklisted = verdict.blacklisted;
		return verdict;
	}

	void Director::Seen(const Sighting& a_sighting)
	{
		std::scoped_lock l{ _lock };
		if (!_catalog) {
			return;
		}
		const auto ref = a_sighting.ref;
		auto&      session = _sessions[ref];
		const auto verdict = Admit(session, a_sighting);
		if (!session.eligible) {
			LeaveAlone(ref, session);
			return;
		}
		// A picking a save cut short (S-47): put back what they had, before anything else.
		if (_registry.picker && _registry.picker->ref == ref && !session.restoring && _picker.ref != ref) {
			session.restoring = true;
			QueueBody(ref, BodyRequest{ .what = BodyRequest::What::kRestore, .restore = _registry.picker->snapshot }, kUrgent);
		}
		DecideBody(ref, session, verdict);
		if (!session.probed) {
			WorkFor(ref, kBackground).probe = true;
		} else {
			ReconcileRefit(ref);
		}
	}

	// The player, the character-creation dummies, creatures and every race Silhouette does not distribute
	// to: never shaped, never refit, so never probed either -- most actors in the world are one of these.
	// Only a refit this session already found (it cannot have been put there by this build) comes off.
	void Director::LeaveAlone(std::uint32_t a_ref, const Session& a_session)
	{
		if (a_session.refit > 0) {
			ReconcileRefit(a_ref);
		}
	}

	void Director::Dressed(const Sighting& a_sighting, bool a_removedClothing)
	{
		std::scoped_lock l{ _lock };
		if (!_catalog) {
			return;
		}
		const auto ref = a_sighting.ref;
		auto&      session = _sessions[ref];
		const bool knew = session.known;
		const bool was = session.clothed;
		Admit(session, a_sighting);
		if (!session.eligible) {
			LeaveAlone(ref, session);
			return;
		}
		if (a_removedClothing) {
			Push(EventKind::kRemovingClothes, ref);
		}
		if (knew && was && !session.clothed) {
			Push(EventKind::kNaked, ref);
		}
		if (!session.probed) {
			WorkFor(ref, kUrgent).probe = true;  // the refit follows the probe, promptly
		} else {
			ReconcileRefit(ref);
		}
	}

	// ------------------------------------------------------------------ deciding

	bool Director::BodyPending(std::uint32_t a_ref) const
	{
		if (const auto it = _work.find(a_ref); it != _work.end() && it->second.body) {
			return true;
		}
		return std::ranges::any_of(_inflight, [&](const auto& p) { return p.second.ref == a_ref && p.second.kind == OrderKind::kBody; });
	}

	void Director::Intend(std::uint32_t a_ref, const Session& a_session, Source a_source, std::string a_preset)
	{
		auto& rec = _registry.Get(a_ref);
		if (a_session.base != 0) {
			rec.base = a_session.base;
		}
		rec.source = a_source;
		rec.preset = std::move(a_preset);
		rec.stamp = _catalog->stamp;
		_registry.Prune(a_ref);
	}

	void Director::DecideBody(std::uint32_t a_ref, Session& a_session, const Verdict& a_verdict)
	{
		if (_picker.ref == a_ref || BodyPending(a_ref)) {
			return;  // the player is choosing, or a change is already on its way
		}
		const auto& c = *_catalog;
		auto*       rec = _registry.Find(a_ref);

		// A choice somebody made stays made; a new build gives it this build's values.
		if (rec && (rec->source == Source::kPicker || rec->source == Source::kAPI)) {
			if (rec->stamp != c.stamp) {
				if (c.Find(rec->preset, a_session.female)) {
					Log(std::format("{:08X}: {} ({}) again, with build {}'s values", a_ref, rec->preset, SourceName(rec->source), c.build));
					rec->stamp = c.stamp;
					QueueBody(a_ref, BodyRequest{ .what = BodyRequest::What::kPreset, .preset = rec->preset }, kNormal);
				} else {
					Log(std::format("{:08X}: {} ({}) is not in build {}; their body stays as it is", a_ref, rec->preset, SourceName(rec->source), c.build));
					rec->source = Source::kNone;
					rec->preset.clear();
					_registry.Prune(a_ref);
				}
			}
			return;
		}

		switch (a_verdict.tier) {
		case Tier::kName:
		case Tier::kFaction:
			{
				const auto source = a_verdict.tier == Tier::kName ? Source::kNameRule : Source::kFactionRule;
				if (!(rec && rec->source == source && rec->preset == a_verdict.preset && rec->stamp == c.stamp)) {
					Log(std::format("{:08X} \"{}\": {}", a_ref, a_session.facts.baseName, a_verdict.why));
					Intend(a_ref, a_session, source, a_verdict.preset);
					QueueBody(a_ref, BodyRequest{ .what = BodyRequest::What::kPreset, .preset = a_verdict.preset }, kNormal);
				}
				break;
			}
		case Tier::kNameBlacklist:
			if (!(rec && rec->source == Source::kNameBlacklist)) {
				Log(std::format("{:08X}: {}", a_ref, a_verdict.why));
				Intend(a_ref, a_session, Source::kNameBlacklist, {});
				QueueBody(a_ref, BodyRequest{ .what = BodyRequest::What::kBlacklist }, kNormal);
			}
			break;
		case Tier::kNone:
			if (rec && (rec->source == Source::kNameRule || rec->source == Source::kFactionRule)) {
				// The rule is gone. Their body is a real one, so it stays; it is just no longer ours.
				Log(std::format("{:08X} \"{}\": no rule gives them {} any more; it stays, as BodyGen's", a_ref, a_session.facts.baseName, rec->preset));
				Intend(a_ref, a_session, Source::kNone, {});
			} else if (rec && rec->source == Source::kNameBlacklist) {
				Log(std::format("{:08X} \"{}\": no longer blacklisted - BodyGen rolls them", a_ref, a_session.facts.baseName));
				Intend(a_ref, a_session, Source::kNone, {});
				QueueBody(a_ref, BodyRequest{ .what = BodyRequest::What::kRegenerate }, kNormal);
			}
			break;
		}
	}

	std::string Director::PresetNamedBy(std::string_view a_marker, std::uint32_t a_stamp) const
	{
		if (a_marker.empty() || a_stamp == 0 || IEquals(a_marker, kBlacklistMarker)) {
			return {};
		}
		return _catalog->PresetForMarker(a_marker, a_stamp).value_or(std::string{});
	}

	void Director::OnProbed(std::uint32_t a_ref, const Order& a_order)
	{
		auto& s = _sessions[a_ref];
		s.probed = true;
		s.marker = a_order.marker;
		s.stamp = Stamp(a_order.markerValue);
		s.refit = a_order.refitValue >= 0.9F ? static_cast<int>(std::lround(a_order.refitValue))
		        : a_order.refitValue > 0.0F  ? kRefitUnfinished
		                                     : 0;
		s.names = a_order.names;
		const bool bodyMarker = !s.marker.empty() && !IEquals(s.marker, kBlacklistMarker) && s.stamp != 0;
		const bool ownValues = std::ranges::any_of(a_order.readValues, [](float v) { return !std::isnan(v) && v != 0.0F; });
		s.hasBody = bodyMarker || ownValues;
	}

	void Director::Reconcile(std::uint32_t a_ref, Session& a_session)
	{
		if (_picker.ref == a_ref || BodyPending(a_ref) || a_session.regiven || a_session.restoring) {
			return;
		}
		const auto* rec = _registry.Find(a_ref);
		if (!rec) {
			return;
		}
		// What the intent says the layer holds (S-43), against what the probe found.
		if (rec->source == Source::kNameBlacklist) {
			if (!IEquals(a_session.marker, kBlacklistMarker)) {
				a_session.regiven = true;
				Log(std::format("{:08X}: blacklisted by name but LooksMenu holds a body - bare again", a_ref));
				QueueBody(a_ref, BodyRequest{ .what = BodyRequest::What::kBlacklist }, kNormal);
			}
			return;
		}
		if (rec->preset.empty()) {
			return;
		}
		const auto* p = _catalog->Find(rec->preset, a_session.female);
		if (!p) {
			return;
		}
		if (!IEquals(a_session.marker, p->marker) || a_session.stamp != rec->stamp) {
			a_session.regiven = true;
			Log(std::format("{:08X}: should have {} ({}), LooksMenu holds {} - given again", a_ref, rec->preset, SourceName(rec->source),
				a_session.marker.empty() ? std::string{ "no body marker" } : a_session.marker));
			if (rec->stamp != _catalog->stamp) {
				_registry.Get(a_ref).stamp = _catalog->stamp;
			}
			QueueBody(a_ref, BodyRequest{ .what = BodyRequest::What::kPreset, .preset = rec->preset }, kNormal);
		}
	}

	void Director::AnnounceBody(std::uint32_t a_ref, const Session& a_session)
	{
		const auto preset = PresetNamedBy(a_session.marker, a_session.stamp);
		if (preset.empty()) {
			return;
		}
		const auto hash = BodyHash(a_session.marker, a_session.stamp);
		if (const auto* rec = _registry.Find(a_ref); rec && rec->announced == hash) {
			return;
		}
		Push(EventKind::kGenerated, a_ref, preset, false, hash);
	}

	void Director::CheckTouch(std::uint32_t a_ref, const Session& a_session)
	{
		if (PresetNamedBy(a_session.marker, a_session.stamp).empty() || BodyPending(a_ref)) {
			return;  // only a body Silhouette can name is healed or topped up
		}
		const auto hash = BodyHash(a_session.marker, a_session.stamp);
		if (const auto* rec = _registry.Find(a_ref); rec && rec->touched == hash) {
			return;
		}
		const auto heal = _catalog->HealFor(a_session.marker, a_session.stamp);
		const bool healing = std::ranges::any_of(heal, [&](const std::string& m) {
			return std::ranges::any_of(a_session.names, [&](const std::string& n) { return IEquals(n, m); });
		});
		if (healing || !TopUp(*_catalog, a_session.female, a_ref, _settings.variety, a_session.names).empty()) {
			WorkFor(a_ref, kNormal).touch = true;
		}
	}

	Director::Want Director::WantRefit(const Session& a_session) const
	{
		if (!_settings.orefit || !a_session.known || !a_session.eligible || !a_session.clothed || a_session.blacklisted ||
			a_session.reset || !a_session.probed || !a_session.hasBody) {
			return {};
		}
		const auto  preset = PresetNamedBy(a_session.marker, a_session.stamp);
		const auto* set = _catalog->RefitFor(preset, a_session.female, a_session.outfitSet);
		return set ? Want{ set, a_session.heavy } : Want{};
	}

	// The refit marker's value names the set and whether it is the heavy one, so the next session's probe
	// knows exactly what is on: 1 + heavy + 2 * the set's index.
	float Director::RefitMarkerValue(const RefitSet& a_set, bool a_heavy) const
	{
		std::size_t index = 0;
		for (std::size_t i = 0; i < _catalog->refitSets.size(); ++i) {
			if (&_catalog->refitSets[i] == &a_set) {
				index = i;
			}
		}
		return static_cast<float>(1 + (a_heavy ? 1 : 0) + 2 * static_cast<int>(index));
	}

	void Director::ReconcileRefit(std::uint32_t a_ref)
	{
		const auto it = _sessions.find(a_ref);
		if (it == _sessions.end() || !it->second.known) {
			return;
		}
		const auto& s = it->second;
		if (s.refit < 0) {
			if (!s.probed) {
				WorkFor(a_ref, kBackground).probe = true;  // unknown until the probe says
			}
			return;
		}
		const auto want = WantRefit(s);
		if (!want.set) {
			if (s.refit > 0) {
				WorkFor(a_ref, kUrgent).refit = true;  // coming off: at once
			}
			return;
		}
		if (s.refit != static_cast<int>(RefitMarkerValue(*want.set, want.heavy))) {
			WorkFor(a_ref, kNormal).refit = true;
		}
	}

	Director::Work& Director::WorkFor(std::uint32_t a_ref, int a_lane)
	{
		auto [it, inserted] = _work.try_emplace(a_ref);
		if (inserted) {
			it->second.lane = a_lane;
			_queue.push_back(a_ref);
		} else {
			it->second.lane = std::min(it->second.lane, a_lane);
			if (std::ranges::find(_queue, a_ref) == _queue.end()) {
				_queue.push_back(a_ref);
			}
		}
		return it->second;
	}

	void Director::QueueBody(std::uint32_t a_ref, BodyRequest a_body, int a_lane)
	{
		WorkFor(a_ref, a_lane).body = std::move(a_body);  // the latest decision wins
	}

	// ------------------------------------------------------------------ requests

	namespace
	{
		template <class F>
		bool WithCatalog(const std::shared_ptr<const Catalog>& a_catalog, const std::string& a_status, std::string& a_why, F&& a_fn)
		{
			if (!a_catalog) {
				a_why = a_status;
				return false;
			}
			return a_fn();
		}
	}

	bool Director::RequestPreset(std::uint32_t a_ref, bool a_female, std::uint32_t a_base, std::string_view a_preset, Source a_source, std::string& a_why)
	{
		std::scoped_lock l{ _lock };
		return WithCatalog(_catalog, _status, a_why, [&] {
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
				_registry.picker.reset();
			}
			session.reset = false;
			Intend(a_ref, session, a_source, std::string{ a_preset });
			QueueBody(a_ref, BodyRequest{ .what = BodyRequest::What::kPreset, .preset = std::string{ a_preset } }, kUrgent);
			return true;
		});
	}

	bool Director::RequestRegenerate(std::uint32_t a_ref, bool a_female, std::uint32_t a_base, std::string& a_why)
	{
		std::scoped_lock l{ _lock };
		return WithCatalog(_catalog, _status, a_why, [&] {
			auto& session = _sessions[a_ref];
			if (!session.known) {
				session.female = a_female;
				session.base = a_base;
			}
			if (_picker.ref == a_ref) {
				ClosePicker();
				_registry.picker.reset();
			}
			session.reset = false;
			Intend(a_ref, session, Source::kNone, {});
			QueueBody(a_ref, BodyRequest{ .what = BodyRequest::What::kRegenerate }, kUrgent);
			return true;
		});
	}

	bool Director::RequestReset(std::uint32_t a_ref, bool a_female, std::uint32_t a_base, std::string& a_why)
	{
		std::scoped_lock l{ _lock };
		return WithCatalog(_catalog, _status, a_why, [&] {
			auto& session = _sessions[a_ref];
			if (!session.known) {
				session.female = a_female;
				session.base = a_base;
			}
			if (_picker.ref == a_ref) {
				ClosePicker();
				_registry.picker.reset();
			}
			Intend(a_ref, session, Source::kNone, {});
			QueueBody(a_ref, BodyRequest{ .what = BodyRequest::What::kReset }, kUrgent);
			return true;
		});
	}

	bool Director::RequestReapply(std::uint32_t a_ref, bool a_female, std::uint32_t a_base, std::string_view a_markerPreset, std::string& a_why)
	{
		std::scoped_lock l{ _lock };
		return WithCatalog(_catalog, _status, a_why, [&] {
			const auto* rec = _registry.Find(a_ref);
			const bool  ours = rec && !rec->preset.empty();
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
			if (_picker.ref == a_ref) {
				ClosePicker();
				_registry.picker.reset();
			}
			Intend(a_ref, session, ours ? rec->source : Source::kNone, preset);
			QueueBody(a_ref, BodyRequest{ .what = BodyRequest::What::kPreset, .preset = preset, .keepVariety = true }, kUrgent);
			return true;
		});
	}

	// ------------------------------------------------------------------ the bridge

	std::uint32_t Director::NextOrder()
	{
		std::scoped_lock l{ _lock };
		if (!_catalog) {
			return 0;
		}
		for (;;) {
			// The most urgent actor with work and nothing in flight; within a lane, the first to ask.
			std::ptrdiff_t best = -1;
			int            bestLane = kBackground + 1;
			for (std::size_t i = 0; i < _queue.size();) {
				const auto ref = _queue[i];
				const auto wit = _work.find(ref);
				if (wit == _work.end() || wit->second.Empty()) {
					_work.erase(ref);
					_queue.erase(_queue.begin() + static_cast<std::ptrdiff_t>(i));
					continue;
				}
				if (!_busy.contains(ref) && wit->second.lane < bestLane) {
					best = static_cast<std::ptrdiff_t>(i);
					bestLane = wit->second.lane;
					if (bestLane == kUrgent) {
						break;
					}
				}
				++i;
			}
			if (best < 0) {
				return 0;
			}
			const auto ref = _queue[static_cast<std::size_t>(best)];
			auto&      w = _work[ref];
			auto&      session = _sessions[ref];

			Order o;
			o.ref = ref;
			o.female = session.female;
			bool made = true;
			if (w.snapshot) {
				w.snapshot = false;
				o.kind = OrderKind::kSnapshot;
				o.probe = true;
				o.readAll = true;
			} else if (w.body) {
				o.kind = OrderKind::kBody;
				o.body = std::move(*w.body);
				w.body.reset();
				if (o.body.what == BodyRequest::What::kRegenerate) {
					o.regenerate = true;
					o.probe = true;
				} else if (o.body.keepVariety) {
					o.readAll = true;
				}
			} else if (w.touch) {
				w.touch = false;
				o.kind = OrderKind::kTouch;
			} else if (w.refit) {
				w.refit = false;
				const auto want = WantRefit(session);
				if (want.set) {
					o.kind = OrderKind::kRefit;
					o.refitOn = true;
					o.heavy = want.heavy;
					o.refitSet = want.set->name;
				} else if (session.refit != 0) {  // on, or unknown: coming off is safe to repeat
					o.kind = OrderKind::kRefit;
					o.refitOn = false;
				} else {
					made = false;
				}
			} else {
				w.probe = false;
				o.kind = OrderKind::kProbe;
				o.probe = true;
			}
			if (w.Empty()) {
				_work.erase(ref);
				_queue.erase(_queue.begin() + best);
			}
			if (!made) {
				continue;
			}
			o.id = Next(_nextOrder);
			const auto id = o.id;
			_busy.insert(ref);
			_inflight.emplace(id, std::move(o));
			return id;
		}
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

	std::uint32_t Director::OrderActor(std::uint32_t a_order) const
	{
		std::scoped_lock l{ _lock };
		const auto       it = _inflight.find(a_order);
		return it == _inflight.end() ? 0 : it->second.ref;
	}

	Order* Director::Find(std::uint32_t a_order)
	{
		const auto it = _inflight.find(a_order);
		return it == _inflight.end() ? nullptr : &it->second;
	}

	void Director::NoteName(std::uint32_t a_order, std::string_view a_morph)
	{
		std::scoped_lock l{ _lock };
		if (auto* o = Find(a_order); o && o->probe && !a_morph.empty() && o->names.size() < 1024) {
			o->names.emplace_back(a_morph);
		}
	}

	void Director::NoteMarker(std::uint32_t a_order, std::string_view a_marker, float a_value)
	{
		std::scoped_lock l{ _lock };
		auto*            o = Find(a_order);
		if (!o || !(a_value > 0.0F)) {
			return;  // 0 is what "removed" looks like: the name stays listed until a load
		}
		if (KindOf(a_marker) == MarkerKind::kRefit) {
			o->refitValue = a_value;
			return;
		}
		// A body carries one marker. Should a layer hold two, a Silhouette preset's wins over the
		// blacklist marker, and the first stays.
		if (o->marker.empty() || (IEquals(o->marker, kBlacklistMarker) && !IEquals(a_marker, kBlacklistMarker))) {
			o->marker = std::string{ a_marker };
			o->markerValue = a_value;
		}
	}

	std::int32_t Director::ReadCount(std::uint32_t a_order)
	{
		std::scoped_lock l{ _lock };
		auto*            o = Find(a_order);
		if (!o || !_catalog) {
			return 0;
		}
		if (!o->readsDecided) {
			o->readsDecided = true;
			// No Silhouette marker: is there a body at all? A few of their own values say (S-41).
			if (o->probe && o->marker.empty()) {
				for (const auto& n : o->names) {
					if (o->reads.size() >= kBodyReads) {
						break;
					}
					if (KindOf(n) == MarkerKind::kNone && !_catalog->NeverInBody(o->female, n)) {
						o->reads.push_back(n);
					}
				}
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
			const auto it = std::ranges::find_if(o->layer, [&](const auto& p) { return IEquals(p.first, a_morph); });
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
		o->clearUnkeyed = false;
		o->clearRefit = false;
		o->writes.clear();
		o->update = false;
		const auto unkeyed = [&](const Morphs& a_morphs) {
			for (const auto& [m, v] : a_morphs) {
				o->writes.push_back(Write{ m, v, Layer::kUnkeyed });
			}
		};

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
					std::unordered_map<std::string, float> keep;
					for (const auto& [m, v] : o->layer) {
						keep.emplace(m, v);
					}
					o->clearUnkeyed = true;
					unkeyed(BodyFor(c, *p, o->ref, _settings.variety, o->body.keepVariety ? &keep : nullptr));
					o->update = true;
					return true;
				}
			case BodyRequest::What::kBlacklist:
				o->clearUnkeyed = true;
				o->clearRefit = true;
				o->writes.push_back(Write{ std::string{ kBlacklistMarker }, static_cast<float>(c.stamp), Layer::kUnkeyed });
				o->update = true;
				return true;
			case BodyRequest::What::kRestore:
				o->clearUnkeyed = true;
				for (const auto& [m, v] : o->body.restore) {
					if (std::abs(v) >= 1e-6F) {
						o->writes.push_back(Write{ m, v, Layer::kUnkeyed });
					}
				}
				o->update = true;
				return true;
			case BodyRequest::What::kRegenerate:
				o->update = true;  // after the bridge put the keyed morphs back
				return true;
			case BodyRequest::What::kReset:
				o->clearUnkeyed = true;
				o->clearRefit = true;
				o->update = true;
				return true;
			}
			return false;
		case OrderKind::kTouch:
			{
				const auto& s = _sessions[o->ref];
				o->touchHash = BodyHash(s.marker, s.stamp);
				for (const auto& m : c.HealFor(s.marker, s.stamp)) {
					if (std::ranges::any_of(s.names, [&](const std::string& n) { return IEquals(n, m); })) {
						o->writes.push_back(Write{ m, 0.0F, Layer::kUnkeyed });  // SetMorph(0) erases it
					}
				}
				unkeyed(TopUp(c, s.female, o->ref, _settings.variety, s.names));
				o->update = !o->writes.empty();
				return true;
			}
		case OrderKind::kRefit:
			o->clearRefit = true;
			o->update = true;
			if (o->refitOn) {
				const auto* set = c.FindRefit(o->refitSet, o->female);
				if (!set) {
					return false;
				}
				// The marker goes first as "pending" and last with its value: a refit a save cut short
				// reads back as unfinished, and the next probe finishes it or takes it off (S-43).
				for (auto [m, v] : RefitFloors(*set, o->heavy)) {
					if (KindOf(m) == MarkerKind::kRefit) {
						v = kRefitPending;
					}
					o->writes.push_back(Write{ std::move(m), v, Layer::kRefit });
				}
				o->writes.push_back(Write{ std::string{ kRefitMarker }, RefitMarkerValue(*set, o->heavy), Layer::kRefit });
			}
			return true;
		}
		return false;
	}

	bool Director::ClearsUnkeyed(std::uint32_t a_order) const
	{
		std::scoped_lock l{ _lock };
		const auto       it = _inflight.find(a_order);
		return it != _inflight.end() && it->second.prepared && it->second.clearUnkeyed;
	}

	bool Director::ClearsRefit(std::uint32_t a_order) const
	{
		std::scoped_lock l{ _lock };
		const auto       it = _inflight.find(a_order);
		return it != _inflight.end() && it->second.prepared && it->second.clearRefit;
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
		return it->second.writes[static_cast<std::size_t>(a_index)].morph;
	}

	float Director::WriteValue(std::uint32_t a_order, std::int32_t a_index) const
	{
		std::scoped_lock l{ _lock };
		const auto       it = _inflight.find(a_order);
		if (it == _inflight.end() || a_index < 0 || static_cast<std::size_t>(a_index) >= it->second.writes.size()) {
			return 0.0F;
		}
		return it->second.writes[static_cast<std::size_t>(a_index)].value;
	}

	Layer Director::WriteLayer(std::uint32_t a_order, std::int32_t a_index) const
	{
		std::scoped_lock l{ _lock };
		const auto       it = _inflight.find(a_order);
		if (it == _inflight.end() || a_index < 0 || static_cast<std::size_t>(a_index) >= it->second.writes.size()) {
			return Layer::kUnkeyed;
		}
		return it->second.writes[static_cast<std::size_t>(a_index)].layer;
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
			Log(std::format("{:08X}: order {} (kind {}) not completed by the bridge", o.ref, o.id, static_cast<int>(o.kind)));
			if (o.kind == OrderKind::kSnapshot && _picker.ref == o.ref) {
				ClosePicker();  // without the snapshot a Cancel could not put them back
			}
			if (o.kind == OrderKind::kBody && o.body.what == BodyRequest::What::kRestore) {
				if (auto s = _sessions.find(o.ref); s != _sessions.end()) {
					s->second.restoring = false;  // the saved picking is kept: the next sighting tries again
				}
			}
			return;
		}
		auto& session = _sessions[o.ref];
		switch (o.kind) {
		case OrderKind::kProbe:
			OnProbed(o.ref, o);
			Reconcile(o.ref, session);
			AnnounceBody(o.ref, session);
			CheckTouch(o.ref, session);
			ReconcileRefit(o.ref);
			break;
		case OrderKind::kSnapshot:
			OnProbed(o.ref, o);
			if (_picker.ref == o.ref) {
				_picker.snapped = true;
				_picker.current = PresetNamedBy(session.marker, session.stamp);
				_picker.index = -1;
				for (std::size_t i = 0; i < _picker.presets.size(); ++i) {
					if (_picker.presets[i] == _picker.current) {
						_picker.index = static_cast<std::int32_t>(i);
					}
				}
				PickerSave save;
				save.ref = o.ref;
				save.base = _picker.base;
				save.female = _picker.female;
				save.snapshot = o.layer;
				if (const auto* rec = _registry.Find(o.ref)) {
					save.before = *rec;
				}
				_registry.picker = std::move(save);
			}
			ReconcileRefit(o.ref);
			break;
		case OrderKind::kBody:
			FinishBody(o);
			break;
		case OrderKind::kTouch:
			{
				auto& rec = _registry.Get(o.ref);
				if (rec.base == 0) {
					rec.base = session.base;
				}
				rec.touched = o.touchHash;
				if (!o.writes.empty()) {
					Log(std::format("{:08X}: {} slider(s) healed or topped up on {}", o.ref, o.writes.size(), PresetNamedBy(session.marker, session.stamp)));
				}
				break;
			}
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

	void Director::FinishBody(Order& a_order)
	{
		const auto& c = *_catalog;
		const auto  ref = a_order.ref;
		auto&       s = _sessions[ref];
		s.probed = s.probed || a_order.probe;
		switch (a_order.body.what) {
		case BodyRequest::What::kPreset:
			{
				const auto* p = c.Find(a_order.body.preset, a_order.female);
				s.marker = p ? p->marker : std::string{};
				s.stamp = c.stamp;
				s.hasBody = true;
				s.reset = false;
				s.names.clear();
				if (p) {
					for (const auto& [m, v] : p->values) {
						s.names.push_back(m);
					}
					for (const auto& r : c.variety[a_order.female ? 1 : 0]) {
						s.names.push_back(r.morph);
					}
				}
				if (!a_order.body.preview && p) {
					const auto hash = BodyHash(p->marker, c.stamp);
					const auto* rec = _registry.Find(ref);
					if (!rec || rec->announced != hash) {
						Push(EventKind::kGenerated, ref, a_order.body.preset, false, hash);
					}
				}
				break;
			}
		case BodyRequest::What::kBlacklist:
			s.marker = std::string{ kBlacklistMarker };
			s.stamp = c.stamp;
			s.hasBody = false;
			s.refit = 0;
			break;
		case BodyRequest::What::kRestore:
			{
				s.marker.clear();
				s.stamp = 0;
				s.hasBody = false;
				s.names.clear();
				for (const auto& [m, v] : a_order.body.restore) {
					s.names.push_back(m);
					if (KindOf(m) == MarkerKind::kBody && v > 0.0F) {
						s.marker = m;
						s.stamp = Stamp(v);
					}
					s.hasBody = s.hasBody || v != 0.0F;
				}
				s.restoring = false;
				if (_registry.picker && _registry.picker->ref == ref) {
					_registry.picker.reset();  // the picking is over
				}
				break;
			}
		case BodyRequest::What::kRegenerate:
			OnProbed(ref, a_order);
			s.reset = false;
			AnnounceBody(ref, s);
			DecideBody(ref, s, Decide(c, s.facts));  // generated as if new: the rules get their say again
			break;
		case BodyRequest::What::kReset:
			s.marker.clear();
			s.stamp = 0;
			s.hasBody = false;
			s.refit = 0;
			s.reset = true;
			s.names.clear();
			break;
		}
		ReconcileRefit(ref);
	}

	void Director::FinishRefit(Order& a_order)
	{
		auto& s = _sessions[a_order.ref];
		if (a_order.refitOn) {
			const auto* set = _catalog->FindRefit(a_order.refitSet, a_order.female);
			s.refit = set ? static_cast<int>(RefitMarkerValue(*set, a_order.heavy)) : 1;
		} else {
			s.refit = 0;
		}
		Push(EventKind::kORefitChanged, a_order.ref, {}, a_order.refitOn);
		ReconcileRefit(a_order.ref);  // they may have dressed or undressed while it ran
	}

	// ------------------------------------------------------------------ events

	void Director::Push(EventKind a_kind, std::uint32_t a_ref, std::string a_preset, bool a_flag, std::uint32_t a_announce)
	{
		if (a_kind == EventKind::kGenerated && a_announce != 0 &&
			std::ranges::any_of(_events, [&](const Event& e) { return e.kind == a_kind && e.ref == a_ref && e.announce == a_announce; })) {
			return;  // already on its way
		}
		if (_events.size() >= kMaxEvents) {
			_events.pop_front();
			if (!_eventsDropped) {
				Log("events: the bridge is not taking them; the oldest are dropped");
				_eventsDropped = true;
			}
		}
		_events.push_back(Event{ .id = Next(_nextEvent), .kind = a_kind, .ref = a_ref, .preset = std::move(a_preset), .flag = a_flag, .announce = a_announce });
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
		const auto& e = _taken.back();
		// Announced when it leaves, not when it was queued: a save in between announces it again.
		if (e.kind == EventKind::kGenerated && e.announce != 0) {
			auto& rec = _registry.Get(e.ref);
			if (rec.base == 0) {
				if (const auto s = _sessions.find(e.ref); s != _sessions.end()) {
					rec.base = s->second.base;
				}
			}
			rec.announced = e.announce;
		}
		return e.id;
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
		const auto ref = _picker.ref;
		if (_picker.index < 0 || !_picker.snapped) {
			const bool tried = _picker.snapped && _picker.index >= 0;
			ClosePicker();
			if (!tried) {
				_registry.picker.reset();
				return std::format("{} keeps the body they had.", name);
			}
		}
		if (!_registry.picker || _registry.picker->ref != ref) {
			ClosePicker();
			return std::format("{} keeps the body they had.", name);
		}
		// The choice behind the body goes back at once; the body follows with the restore, and the saved
		// picking stays until that restore is done (S-47).
		if (_registry.picker->before) {
			_registry.Get(ref) = *_registry.picker->before;
		} else {
			_registry.Erase(ref);
		}
		QueueBody(ref, BodyRequest{ .what = BodyRequest::What::kRestore, .restore = _registry.picker->snapshot }, kUrgent);
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
		const auto name = a_name.empty() ? std::format("{:08X}", a_ref) : std::string{ a_name };
		if (_picker.ref == a_ref) {
			return std::format("{} is already picked: Next / Previous try presets, Keep or Cancel ends it.", _picker.name);
		}
		if (BodyPending(a_ref)) {
			return std::format("{}'s body is still changing - pick them again in a moment.", name);
		}
		std::string before;
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
		_picker.name = name;
		_picker.presets = std::move(presets);
		WorkFor(a_ref, kUrgent).snapshot = true;
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
			// Nothing tried on and their body is none of these: Next is the first preset, Previous the last.
			_picker.index = a_step > 0 ? (a_step - 1) % n : ((n + a_step % n) % n);
		} else {
			_picker.index = ((_picker.index + a_step) % n + n) % n;
		}
		const auto& preset = _picker.presets[static_cast<std::size_t>(_picker.index)];
		QueueBody(_picker.ref, BodyRequest{ .what = BodyRequest::What::kPreset, .preset = preset, .preview = true }, kUrgent);
		return std::format("{}: {} ({}/{})", _picker.name, preset, _picker.index + 1, n);
	}

	std::string Director::PickerKeep()
	{
		std::scoped_lock l{ _lock };
		if (_picker.ref == 0) {
			return "Nobody is picked.";
		}
		const auto name = _picker.name;
		const auto ref = _picker.ref;
		const bool changed = _picker.snapped && _picker.index >= 0 &&
		                     _picker.presets[static_cast<std::size_t>(_picker.index)] != _picker.current;
		if (!changed) {
			ClosePicker();
			_registry.picker.reset();
			return std::format("{} keeps the body they had.", name);
		}
		const auto preset = _picker.presets[static_cast<std::size_t>(_picker.index)];
		Intend(ref, _sessions[ref], Source::kPicker, preset);
		// The preview is on them already, or on its way: it is the body now, and announced as one.
		const auto* p = _catalog->Find(preset, _picker.female);
		if (p) {
			Push(EventKind::kGenerated, ref, preset, false, BodyHash(p->marker, _catalog->stamp));
		}
		ClosePicker();
		_registry.picker.reset();
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
		const auto*      rec = _registry.Find(a_ref);
		return rec && rec->source != Source::kNameBlacklist ? rec->preset : std::string{};
	}

	bool Director::RefitApplied(std::uint32_t a_ref) const
	{
		std::scoped_lock l{ _lock };
		const auto       it = _sessions.find(a_ref);
		return it != _sessions.end() && it->second.refit > 0;
	}

	std::string Director::Describe(std::uint32_t a_ref) const
	{
		std::scoped_lock l{ _lock };
		const auto*      rec = _registry.Find(a_ref);
		std::string      out;
		if (rec && rec->source == Source::kNameBlacklist) {
			out = "blacklisted by name: kept bare";
		} else if (rec && !rec->preset.empty()) {
			out = std::format("chosen: {} ({})", rec->preset, SourceName(rec->source));
		} else {
			out = "nobody chose their body: it is BodyGen's";
		}
		if (const auto it = _sessions.find(a_ref); it != _sessions.end()) {
			if (it->second.refit > 0) {
				out += it->second.refit % 2 == 0 ? "; dressed heavily, refit on" : "; dressed, refit on";
			} else if (it->second.refit == 0 && it->second.clothed) {
				out += "; dressed, not refit";
			}
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

Scriptname Complexion:Bridge extends Quest
{The hands of Complexion.dll: it decides every NPC's overlays, this script puts them on through LooksMenu.
 One poll timer, and only while the game runs; no waits, no per-NPC faction scans, no cloak (ROF's costs,
 docs/complexion-research.md). An order is a whole look: every entry added, then ONE Update, then a check with
 GetAll that each landed (C-6).

 Ours are told from every other mod's by their priority: Complexion's are negative, everyone else's (AAF counts
 from 0) are not. A rebuild keeps every entry that is not ours, with all its data.}

Int Property Protocol = 1 AutoReadOnly
Int Property kPollTimer = 1 AutoReadOnly
Float Property PollSeconds = 4.0 AutoReadOnly
Float Property BusyPollSeconds = 0.5 AutoReadOnly
Int Property OrdersPerPoll = 6 AutoReadOnly
Int Property SettingsEvery = 15 AutoReadOnly
String Property ModName = "Complexion" AutoReadOnly

; AAF's own keywords for an actor in a scene, or locked by another mod (AAF.esm).
Int Property AAFActorBusy = 0x00915A AutoReadOnly
Int Property AAFActorLocked = 0x017CEA AutoReadOnly
; Raiders' captives are put in these on the reference at run time (Fallout4.esm), where the plugin, reading the
; NPC record, cannot see them.
Int Property CaptiveFactionID = 0x03E0C8 AutoReadOnly
Int Property BoundCaptiveFactionID = 0x058610 AutoReadOnly

Float _drainStarted = -1.0
Int _polls = 0
Bool _plugin = False
Bool _mcm = False
Keyword _aafBusy
Keyword _aafLocked
Faction _captive
Faction _boundCaptive

Event OnQuestInit()
	RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")
	Connect()
EndEvent

Event Actor.OnPlayerLoadGame(Actor akSender)
	Connect()
EndEvent

Function Connect()
	_drainStarted = -1.0
	_polls = 0
	_plugin = False
	CancelTimer(kPollTimer)
	_aafBusy = None
	_aafLocked = None
	If Game.IsPluginInstalled("AAF.esm")
		_aafBusy = Game.GetFormFromFile(AAFActorBusy, "AAF.esm") as Keyword
		_aafLocked = Game.GetFormFromFile(AAFActorLocked, "AAF.esm") as Keyword
	EndIf
	_captive = Game.GetFormFromFile(CaptiveFactionID, "Fallout4.esm") as Faction
	_boundCaptive = Game.GetFormFromFile(BoundCaptiveFactionID, "Fallout4.esm") as Faction
	; By the names plugins register with F4SE, not their file names: MCM is "F4MCM"; LooksMenu "F4EE", or
	; "Fallout 4 Engine Extender" on AE.
	_mcm = F4SE.GetPluginVersion("F4MCM") > 0 || F4SE.GetPluginVersion("MCM") > 0
	If F4SE.GetPluginVersion("F4EE") <= 0 && F4SE.GetPluginVersion("Fallout 4 Engine Extender") <= 0
		Debug.Trace("Complexion bridge: LooksMenu is not loaded - no overlay can be put on anyone", 0)
		Debug.Notification("Complexion: LooksMenu is not loaded, so nobody gets overlays.")
		Return
	EndIf
	If F4SE.GetPluginVersion("Complexion") <= 0
		Debug.Trace("Complexion bridge: Complexion.dll is not loaded", 0)
		Debug.Notification("Complexion: Complexion.dll is not loaded (F4SE and Runtime Database needed).")
		Return
	EndIf
	Int theirs = Complexion:DLL.ProtocolVersion()
	If theirs != Protocol
		Debug.Trace("Complexion bridge: the scripts speak protocol " + Protocol + " but Complexion.dll speaks " + theirs, 0)
		Debug.Notification("Complexion: Complexion.dll and its scripts are from different releases - install one release's files together.")
		Return
	EndIf
	_plugin = True
	String warning = Complexion:DLL.Warning()
	If warning != ""
		Debug.MessageBox("Complexion: " + warning)
	EndIf
	PushSettings()
	StartTimer(PollSeconds, kPollTimer)
EndFunction

Function PushSettings()
	Bool enabled = True
	Bool adult = True
	If _mcm
		enabled = MCM.GetModSettingBool(ModName, "bEnabled:General")
		adult = MCM.GetModSettingBool(ModName, "bAdult:General")
	EndIf
	Complexion:DLL.Configure(enabled, adult)
EndFunction

Event OnTimer(Int aiTimerID)
	If aiTimerID != kPollTimer || !_plugin
		Return
	EndIf
	; The next poll is scheduled before this one does anything, so nothing below can stop the clock.
	If Complexion:DLL.Pending() > 0
		StartTimer(BusyPollSeconds, kPollTimer)
	Else
		StartTimer(PollSeconds, kPollTimer)
	EndIf
	_polls += 1
	If _polls % SettingsEvery == 0
		PushSettings()
	EndIf
	Complexion:DLL.Pump()
	; A line for the player, once: some are only known after the first poll (Random Overlay Framework switched off).
	; A box only for a real problem: a modal box holds every script mod still until it is clicked.
	String said = Complexion:DLL.Warning()
	If said != ""
		Debug.MessageBox("Complexion: " + said)
	EndIf
	String news = Complexion:DLL.Notice()
	If news != ""
		Debug.Notification(news)
	EndIf
	; One drain at a time, on a stack of its own: LooksMenu's natives return at once, and the plugin hands an
	; actor to one order at a time either way.
	Float now = Utility.GetCurrentRealTime()
	If _drainStarted >= 0.0 && now >= _drainStarted && now - _drainStarted < 120.0
		Return
	EndIf
	_drainStarted = now
	CallFunctionNoWait("PollDrain", new Var[0])
EndEvent

Function PollDrain()
	Int done = 0
	While done < OrdersPerPoll
		Int id = Complexion:DLL.NextOrder()
		If id == 0
			done = OrdersPerPoll
		Else
			RunOrder(id)
			done += 1
		EndIf
	EndWhile
	_drainStarted = -1.0
EndFunction

; In an AAF scene, or flagged for other mods to leave alone: AAF holds uids on them (C-6).
Bool Function Busy(Actor a)
	If _aafBusy && a.HasKeyword(_aafBusy)
		Return True
	EndIf
	If _aafLocked && a.HasKeyword(_aafLocked)
		Return True
	EndIf
	Return False
EndFunction

Bool Function Captive(Actor a)
	Return (_captive && a.IsInFaction(_captive)) || (_boundCaptive && a.IsInFaction(_boundCaptive))
EndFunction

Function RunOrder(Int aiOrder)
	Actor a = Game.GetForm(Complexion:DLL.OrderActor(aiOrder)) as Actor
	; A form still resolves after its actor is gone: Is3DLoaded is the check that holds.
	If !a || !a.Is3DLoaded() || a.IsDead() || a.IsChild() || Busy(a)
		Complexion:DLL.OrderGone(aiOrder)
		Return
	EndIf
	If Captive(a) && Complexion:DLL.OrderGroup(aiOrder) != "captives"
		Complexion:DLL.OrderRegroup(aiOrder, "captives")
	EndIf
	Bool female = Complexion:DLL.OrderFemale(aiOrder)
	Int count = Complexion:DLL.OrderCount(aiOrder)
	If count <= 0
		Complexion:DLL.OrderDone(aiOrder, True)
		Return
	EndIf
	Bool rebuilt = HasOurs(a, female)
	If rebuilt
		Rebuild(a, female)
	EndIf
	AddOurs(a, female, aiOrder, count)
	Overlays.Update(a)
	Bool landed = Landed(a, female, aiOrder, count)
	If !landed && !rebuilt
		; An Add can be handed a uid that is still live after another mod's single Remove (LooksMenu's
		; RemoveOverlay never frees it), and that entry is lost. Once, from clean.
		Rebuild(a, female)
		AddOurs(a, female, aiOrder, count)
		Overlays.Update(a)
		landed = Landed(a, female, aiOrder, count)
	EndIf
	Complexion:DLL.OrderDone(aiOrder, landed)
EndFunction

Bool Function HasOurs(Actor a, Bool female)
	Overlays:Entry[] all = Overlays.GetAll(a, female)
	Int i = 0
	While all && i < all.Length
		If all[i] && all[i].priority < 0
			Return True
		EndIf
		i += 1
	EndWhile
	Return False
EndFunction

; Every entry removed, then every one that is not ours put back exactly as it was (template, priority, tint,
; offset, scale): RemoveAll frees LooksMenu's uids properly, a single Remove does not.
Function Rebuild(Actor a, Bool female)
	Overlays:Entry[] all = Overlays.GetAll(a, female)
	Overlays.RemoveAll(a, female)
	Int i = 0
	While all && i < all.Length
		Overlays:Entry e = all[i]
		If e && e.priority >= 0
			Overlays:Entry keep = new Overlays:Entry
			keep.priority = e.priority
			keep.template = e.template
			keep.red = e.red
			keep.green = e.green
			keep.blue = e.blue
			keep.alpha = e.alpha
			keep.offset_u = e.offset_u
			keep.offset_v = e.offset_v
			keep.scale_u = e.scale_u
			keep.scale_v = e.scale_v
			Overlays.Add(a, female, keep)
		EndIf
		i += 1
	EndWhile
EndFunction

Function AddOurs(Actor a, Bool female, Int aiOrder, Int count)
	Int i = 0
	While i < count
		Overlays.AddEntry(a, female, Complexion:DLL.OrderPriority(aiOrder, i), Complexion:DLL.OrderTemplate(aiOrder, i))
		i += 1
	EndWhile
EndFunction

Bool Function Landed(Actor a, Bool female, Int aiOrder, Int count)
	Overlays:Entry[] all = Overlays.GetAll(a, female)
	Int i = 0
	While i < count
		String t = Complexion:DLL.OrderTemplate(aiOrder, i)
		Int p = Complexion:DLL.OrderPriority(aiOrder, i)
		Bool found = False
		Int k = 0
		While all && k < all.Length && !found
			; Papyrus strings compare case-insensitively, as LooksMenu's template names may come back in any case.
			found = all[k] && all[k].priority == p && all[k].template == t
			k += 1
		EndWhile
		If !found
			Return False
		EndIf
		i += 1
	EndWhile
	Return True
EndFunction

;---------------------------------------------------------------------------
; MCM buttons
;---------------------------------------------------------------------------

; Every entry LooksMenu holds on each human around the player (about 20 m), Complexion's marked by their negative
; priority, into Complexion.log -- tells Complexion's overlays from other mods' and from leftovers without guessing.
Function MenuDescribe()
	Keyword human = Game.GetFormFromFile(0x02CB72, "Fallout4.esm") as Keyword
	ObjectReference[] near = None
	If human
		near = Game.GetPlayer().FindAllReferencesWithKeyword(human, 1400.0)
	EndIf
	Int people = 0
	Int k = 0
	While near && k < near.Length
		Actor a = near[k] as Actor
		If a && a != Game.GetPlayer() && a.Is3DLoaded()
			people += 1
			Describe(a)
		EndIf
		k += 1
	EndWhile
	Debug.MessageBox("Complexion: " + people + " people around you; what each wears is in Complexion.log.")
EndFunction

Function Describe(Actor a)
	Bool female = a.GetLeveledActorBase().GetSex() == 1
	Overlays:Entry[] all = Overlays.GetAll(a, female)
	Int n = 0
	If all
		n = all.Length
	EndIf
	String decided = Complexion:DLL.Decided(a.GetFormID())
	If decided == ""
		decided = "nothing yet"
	EndIf
	Complexion:DLL.Log(Complexion:DLL.NameOf(a.GetFormID()) + ": LooksMenu holds " + n + " overlay(s); Complexion decided " + decided)
	Int i = 0
	While i < n
		If all[i]
			String mark = "another mod or a leftover"
			If all[i].priority < 0
				mark = "Complexion"
			EndIf
			Complexion:DLL.Log("    " + all[i].template + " @" + all[i].priority + " - " + mark)
		EndIf
		i += 1
	EndWhile
EndFunction

; Everyone is decided anew as they are seen; their old Complexion overlays are replaced (a rebuild keeps others').
Function MenuRollAgain()
	If !_plugin
		Debug.MessageBox("Complexion: Complexion.dll is not connected.")
		Return
	EndIf
	Complexion:DLL.ResetAll()
	Debug.MessageBox("Complexion: everyone gets a new look - the people around you within a few seconds of closing the menu, everyone else as you meet them.")
EndFunction

; Random Overlay Framework's leftovers, and everything else: LooksMenu forgets every overlay on everyone. Complexion
; puts its own looks back as people are seen.
Function MenuClearAll()
	If !_plugin
		Debug.MessageBox("Complexion: Complexion.dll is not connected.")
		Return
	EndIf
	Overlays.ClearAll()
	Complexion:DLL.Unapply()
	Debug.MessageBox("Complexion: every overlay on everyone is cleared, Random Overlay Framework's included. Save and load to see it everywhere; Complexion puts its own looks back as you meet people.")
EndFunction

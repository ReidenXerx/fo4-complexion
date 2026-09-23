Scriptname Silhouette:Bridge extends Quest
{Silhouette's hands (decisions S-18, S-22, S-24). Silhouette.dll decides every
 body; this script carries each decision out through LooksMenu's BodyGen -- the only
 door to the morph store -- and raises the events other mods listen for. It polls;
 the plugin never calls in.

 On Silhouette.esp's second quest (0x802). The regeneration window
 (Silhouette:Adopter, 0x800) needs none of this, and nothing here needs it.

 What an order does is decided in the plugin and tested there, against a fake
 bridge that does exactly what RunOrder below does. Change one, change the other.

 Every argument is passed explicitly: the base sources are decompiled and carry no
 default values.}

; For other mods (S-24). Register on this quest:
;   RegisterForCustomEvent(Silhouette:API.Bridge(), "OnActorGenerated")
;   Event Silhouette:Bridge.OnActorGenerated(Silhouette:Bridge akSender, Var[] akArgs)
CustomEvent OnActorGenerated        ; akArgs: [0] Actor, [1] String preset
CustomEvent OnActorNaked            ; akArgs: [0] Actor
CustomEvent OnActorRemovingClothes  ; akArgs: [0] Actor
CustomEvent OnORefitChanged         ; akArgs: [0] Actor, [1] Bool applied

; ONE timer id. Rapport's poll died for good at the exact call that started a
; timer with a second id; a single id is the only kind this engine has kept.
Int Property kPollTimer = 1 AutoReadOnly
Float Property PollSeconds = 1.0 AutoReadOnly
; An order is up to ~120 BodyGen calls, each waiting for a frame on the main thread.
Int Property OrdersPerPoll = 6 AutoReadOnly
; MCM settings are read again every this many polls (no F4SE external events needed).
Int Property SettingsEvery = 10 AutoReadOnly
; The menu acts on the last NPC aimed at within this long: opening it takes the crosshair off them.
Float Property RecentAimSeconds = 30.0 AutoReadOnly
String Property ModName = "Silhouette" AutoReadOnly
Int Property SourcePicker = 3 AutoReadOnly

; Real time the poll's drain began, -1 when none runs. Not a "busy" flag that could
; outlive a crash: Connect() clears it on every load, and after two minutes it is
; treated as a drain that is not coming back.
Float _drainStarted = -1.0
Int _polls = 0
Bool _plugin = false

;---------------------------------------------------------------------------
; Startup: on quest start and on every load. This script's variables live in the
; save; the plugin starts from nothing on every launch.
;---------------------------------------------------------------------------

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
	; Cancel first: Papyrus cannot say whether a timer runs, and two polls at once
	; is how Rapport's bridge first went wrong.
	CancelTimer(kPollTimer)
	_plugin = F4SE.GetPluginVersion("Silhouette") > 0
	If !_plugin
		; No DLL: nothing below may call a native, or every poll logs an error.
		; BodyGen still gives every NPC a body (Phase 1 needs none of this).
		Debug.Trace("Silhouette bridge: Silhouette.dll is not loaded - rules by name and faction, ORefit, the NPC picker and the API are off", 0)
		Return
	EndIf
	PushSettings()
	Silhouette:Plugin.Log("bridge connected - " + Silhouette:Plugin.Status())
	String menu = Silhouette:Player.Build()
	If Silhouette:Plugin.IsReady() && menu != Silhouette:Plugin.Build()
		Silhouette:Plugin.Log("the scripts are build " + menu + " but the catalog is build " + Silhouette:Plugin.Build() + ": install one generator run's files together")
	EndIf
	StartTimer(PollSeconds, kPollTimer)
EndFunction

Function PushSettings()
	Bool orefit = True
	Bool nipples = True
	Bool genitals = True
	If MCM.IsInstalled()
		orefit = MCM.GetModSettingBool(ModName, "bORefit:General")
		nipples = MCM.GetModSettingBool(ModName, "bNippleRand:General")
		genitals = MCM.GetModSettingBool(ModName, "bGenitalRand:General")
	EndIf
	Silhouette:Plugin.Configure(orefit, nipples, genitals)
EndFunction

;---------------------------------------------------------------------------
; The poll
;---------------------------------------------------------------------------

Event OnTimer(Int aiTimerID)
	If aiTimerID != kPollTimer
		Return
	EndIf
	; The next poll is scheduled BEFORE this one does anything, so nothing below
	; can stop the clock.
	StartTimer(PollSeconds, kPollTimer)
	If !_plugin
		Return
	EndIf
	_polls += 1
	If _polls % SettingsEvery == 0
		PushSettings()
	EndIf
	Silhouette:Plugin.Pump()
	; A drain waits on the main thread once per BodyGen call, so a long one outlasts
	; the poll. This poll then only raises events; the plugin hands an actor to one
	; drain at a time either way, so two could not collide -- this keeps them few.
	Float now = Utility.GetCurrentRealTime()
	If _drainStarted >= 0.0 && now >= _drainStarted && now - _drainStarted < 120.0
		RaiseEvents()
		Return
	EndIf
	_drainStarted = now
	Drain(OrdersPerPoll)
	_drainStarted = -1.0
	RaiseEvents()
EndEvent

Function Drain(Int aiBudget)
	Int done = 0
	While done < aiBudget
		Int id = Silhouette:Plugin.NextOrder()
		If id == 0
			Return
		EndIf
		RunOrder(id)
		done += 1
	EndWhile
EndFunction

; One order, exactly as the plugin's tests run it.
Function RunOrder(Int aiOrder)
	Actor a = Game.GetForm(Silhouette:Plugin.OrderActor(aiOrder)) as Actor
	If !a
		Silhouette:Plugin.OrderDone(aiOrder, False)
		Return
	EndIf
	Bool female = Silhouette:Plugin.OrderFemale(aiOrder)

	If Silhouette:Plugin.OrderRegenerates(aiOrder)
		Regenerate(a, female)
	EndIf

	Bool probe = Silhouette:Plugin.OrderProbes(aiOrder)
	Bool all = Silhouette:Plugin.OrderReadsAll(aiOrder)
	If probe || all
		String[] morphs = BodyGen.GetMorphs(a, female)
		Int count = 0
		If morphs
			count = morphs.Length
		EndIf
		Int i = 0
		While i < count
			Bool marker = probe && Silhouette:Plugin.IsMarker(morphs[i])
			If marker || all
				Float v = BodyGen.GetMorph(a, female, morphs[i], None)
				If marker
					Silhouette:Plugin.NoteMarker(aiOrder, morphs[i], v)
				EndIf
				If all && v != 0.0
					Silhouette:Plugin.NoteLayer(aiOrder, morphs[i], v)
				EndIf
			EndIf
			i += 1
		EndWhile
	EndIf

	; After the probe: which refit set applies can depend on the preset it found.
	Int reads = Silhouette:Plugin.OrderReadCount(aiOrder)
	Int r = 0
	While r < reads
		Silhouette:Plugin.NoteRead(aiOrder, r, BodyGen.GetMorph(a, female, Silhouette:Plugin.OrderReadMorph(aiOrder, r), None))
		r += 1
	EndWhile

	If !Silhouette:Plugin.Prepare(aiOrder)
		Silhouette:Plugin.OrderDone(aiOrder, False)
		Return
	EndIf
	; The unkeyed layer only: other mods' keyed morphs (AAF's, a pregnancy belly) stay.
	If Silhouette:Plugin.OrderClears(aiOrder)
		BodyGen.RemoveMorphsByKeyword(a, female, None)
	EndIf
	Int writes = Silhouette:Plugin.OrderWriteCount(aiOrder)
	Int w = 0
	While w < writes
		BodyGen.SetMorph(a, female, Silhouette:Plugin.OrderWriteMorph(aiOrder, w), None, Silhouette:Plugin.OrderWriteValue(aiOrder, w))
		w += 1
	EndWhile
	If Silhouette:Plugin.OrderUpdates(aiOrder)
		BodyGen.UpdateMorphs(a)
	EndIf
	Silhouette:Plugin.OrderDone(aiOrder, True)
EndFunction

; BodyGen rolls them again. RegenerateMorphs clears EVERY key, so other mods' keyed
; values are remembered first and put back after (the regeneration window's way).
Function Regenerate(Actor a, Bool female)
	String[] morphs = BodyGen.GetMorphs(a, female)
	String[] names = new String[0]
	Keyword[] keys = new Keyword[0]
	Float[] values = new Float[0]
	Int count = 0
	If morphs
		count = morphs.Length
	EndIf
	Int i = 0
	While i < count
		Keyword[] kws = BodyGen.GetKeywords(a, female, morphs[i])
		If kws
			Int k = 0
			While k < kws.Length
				If kws[k] && names.Length < 128
					Float v = BodyGen.GetMorph(a, female, morphs[i], kws[k])
					If v != 0.0
						names.Add(morphs[i], 1)
						keys.Add(kws[k], 1)
						values.Add(v, 1)
					EndIf
				EndIf
				k += 1
			EndWhile
		EndIf
		i += 1
	EndWhile
	BodyGen.RegenerateMorphs(a, False)
	Int j = 0
	While j < names.Length
		BodyGen.SetMorph(a, female, names[j], keys[j], values[j])
		j += 1
	EndWhile
EndFunction

Function RaiseEvents()
	Int e = Silhouette:Plugin.NextEvent()
	Int raised = 0
	While e != 0 && raised < 64
		Int kind = Silhouette:Plugin.EventKind(e)
		Actor a = Game.GetForm(Silhouette:Plugin.EventActor(e)) as Actor
		If a
			Var[] args
			If kind == 1
				args = new Var[2]
				args[0] = a
				args[1] = Silhouette:Plugin.EventPreset(e)
				SendCustomEvent("OnActorGenerated", args)
			ElseIf kind == 2
				args = new Var[1]
				args[0] = a
				SendCustomEvent("OnActorNaked", args)
			ElseIf kind == 3
				args = new Var[1]
				args[0] = a
				SendCustomEvent("OnActorRemovingClothes", args)
			ElseIf kind == 4
				args = new Var[2]
				args[0] = a
				args[1] = Silhouette:Plugin.EventFlag(e)
				SendCustomEvent("OnORefitChanged", args)
			EndIf
		EndIf
		raised += 1
		e = Silhouette:Plugin.NextEvent()
	EndWhile
EndFunction

;---------------------------------------------------------------------------
; The NPC picker (S-22): MCM hotkeys call these on this quest.
;---------------------------------------------------------------------------

Bool Function Ready()
	If !_plugin
		Debug.Notification("Silhouette: Silhouette.dll is not loaded.")
		Return False
	EndIf
	If !Silhouette:Plugin.IsReady()
		Debug.Notification("Silhouette: " + Silhouette:Plugin.Status())
		Return False
	EndIf
	Return True
EndFunction

; The picker's own orders go to the front of the queue, so the work below starts
; with them; the rest of the budget is ordinary work that was waiting anyway.
Function Act()
	Drain(2)
	RaiseEvents()
EndFunction

Function PickerPick()
	If !Ready()
		Return
	EndIf
	Int target = Silhouette:Plugin.CrosshairActor(0.0)
	If target == 0
		Debug.Notification("Silhouette: aim at an NPC, then Pick.")
		Return
	EndIf
	Debug.Notification(Silhouette:Plugin.PickerStart(target))
	Act()
EndFunction

Function PickerNext()
	If Ready()
		Debug.Notification(Silhouette:Plugin.PickerStep(1))
		Act()
	EndIf
EndFunction

Function PickerPrevious()
	If Ready()
		Debug.Notification(Silhouette:Plugin.PickerStep(-1))
		Act()
	EndIf
EndFunction

Function PickerKeep()
	If Ready()
		Debug.Notification(Silhouette:Plugin.PickerKeep())
		Act()
	EndIf
EndFunction

Function PickerCancel()
	If Ready()
		Debug.Notification(Silhouette:Plugin.PickerCancel())
		Act()
	EndIf
EndFunction

;---------------------------------------------------------------------------
; The MCM page "The NPC in your sights" calls these on this quest.
;---------------------------------------------------------------------------

; The NPC the menu acts on: the one picked with the hotkey, or the last one aimed at.
Int Function MenuTarget()
	Int target = Silhouette:Plugin.PickerTarget()
	If target == 0
		target = Silhouette:Plugin.CrosshairActor(RecentAimSeconds)
	EndIf
	Return target
EndFunction

Bool Function MenuReady()
	If !_plugin
		Debug.MessageBox("Silhouette: Silhouette.dll is not loaded, so NPCs cannot be shaped one by one. BodyGen still gives everyone a body.")
		Return False
	EndIf
	If !Silhouette:Plugin.IsReady()
		Debug.MessageBox("Silhouette: " + Silhouette:Plugin.Status())
		Return False
	EndIf
	Return True
EndFunction

Function MenuApply()
	If !MenuReady()
		Return
	EndIf
	Int target = MenuTarget()
	Actor a = Game.GetForm(target) as Actor
	If !a
		Debug.MessageBox("Silhouette: aim at an NPC before opening the menu, or Pick one with the hotkey.")
		Return
	EndIf
	Bool female = a.GetLeveledActorBase().GetSex() == 1
	String preset = Silhouette:Player.NpcChoice(female)
	If preset == ""
		Debug.MessageBox("Silhouette: that choice is not in this build of the menu. Nothing was changed.")
		Return
	EndIf
	If !Silhouette:Plugin.RequestPreset(target, preset, SourcePicker)
		Debug.MessageBox("Silhouette: " + Silhouette:Plugin.LastError())
		Return
	EndIf
	Act()
	Debug.MessageBox(Silhouette:Plugin.NameOf(target) + " now has " + preset + ". Close the menu to see it.")
EndFunction

Function MenuRandom()
	If !MenuReady()
		Return
	EndIf
	Int target = MenuTarget()
	If target == 0
		Debug.MessageBox("Silhouette: aim at an NPC before opening the menu, or Pick one with the hotkey.")
		Return
	EndIf
	If !Silhouette:Plugin.RequestRegenerate(target)
		Debug.MessageBox("Silhouette: " + Silhouette:Plugin.LastError())
		Return
	EndIf
	Act()
	Debug.MessageBox(Silhouette:Plugin.NameOf(target) + " rolled a new body, as if met for the first time. Other mods' body morphs were kept.")
EndFunction

Function MenuWhich()
	If !MenuReady()
		Return
	EndIf
	Int target = MenuTarget()
	Actor a = Game.GetForm(target) as Actor
	If !a
		Debug.MessageBox("Silhouette: aim at an NPC before opening the menu, or Pick one with the hotkey.")
		Return
	EndIf
	Debug.MessageBox(Silhouette:Plugin.NameOf(target) + ": " + BodyOf(a) + ". " + Silhouette:Plugin.Describe(target) + ".")
EndFunction

; The preset their marker names, read from LooksMenu now.
String Function BodyOf(Actor a)
	Bool female = a.GetLeveledActorBase().GetSex() == 1
	String[] morphs = BodyGen.GetMorphs(a, female)
	Int count = 0
	If morphs
		count = morphs.Length
	EndIf
	Int i = 0
	While i < count
		If Silhouette:Plugin.IsMarker(morphs[i])
			Float v = BodyGen.GetMorph(a, female, morphs[i], None)
			If v > 0.0
				String preset = Silhouette:Plugin.PresetForMarker(morphs[i], v)
				If preset != ""
					Return preset
				EndIf
				Return "a marker this install cannot name (" + morphs[i] + ")"
			EndIf
		EndIf
		i += 1
	EndWhile
	If count == 0
		Return "no body sliders at all"
	EndIf
	Return "body sliders Silhouette did not set"
EndFunction

Function MenuStatus()
	If !_plugin
		Debug.MessageBox("Silhouette: Silhouette.dll is not loaded.")
		Return
	EndIf
	Debug.MessageBox("Silhouette " + Silhouette:Plugin.Version() + ": " + Silhouette:Plugin.Status())
EndFunction

; For uninstalling: ORefit off in the menu first, then this. Everyone the save
; remembers with a refit on -- loaded or not -- gets their naked values back.
Function MenuRefitOffEverywhere()
	If !MenuReady()
		Return
	EndIf
	PushSettings()
	If Silhouette:Plugin.IsORefitEnabled()
		Debug.MessageBox("Silhouette: turn ORefit off above first, or everyone dressed would be refit again.")
		Return
	EndIf
	Int n = Silhouette:Plugin.RefitOffEverywhere()
	Act()
	Debug.MessageBox("Silhouette: " + n + " people get their naked values back over the next minute. Save after that before removing Silhouette.")
EndFunction

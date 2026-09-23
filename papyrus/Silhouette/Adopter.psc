Scriptname Silhouette:Adopter extends Quest
{The regeneration window (owner, 2026-09-23; decision S-15).

 LooksMenu's BodyGen shapes an actor only while it holds NO body morphs at all, so
 an NPC another mod has already marked -- an AAF morph left behind by a scene, a
 pregnancy mod's belly -- never gets a Silhouette body on its own. For 24 in-game
 hours after Silhouette first loads in a save, and after MCM opens a new window,
 people around the player who hold ONLY other mods' keyed morphs are rolled by
 BodyGen -- the same rules, blacklists and player lines as everyone else -- and
 those keyed morphs are put back afterwards.

 Left alone: anyone with an unkeyed value (a Silhouette body, or sliders set by
 hand in LooksMenu), anyone AAF has busy or locked, and anyone already processed.
 After 24 in-game hours the window closes itself.

 With Silhouette.dll ready, a person is handed to it (Silhouette:API.GenActor): the
 plugin rolls them the same way and knows it did. Without it this script rolls them
 itself, and also heals Silhouette bodies an older build gave with a runtime state
 or a shaft value in them (decisions S-16, S-29) -- the plugin's touch-up does that
 for everyone it sees.}

; Every argument is passed explicitly: the decompiled base sources carry no defaults.

Float Property WindowDays = 1.0 AutoReadOnly
Float Property ScanSeconds = 10.0 AutoReadOnly
Int Property ScanTimer = 1 AutoReadOnly
; AAF.esm: AAF_ActorBusy (set for the length of a scene) and AAF_ActorLocked (the
; flag AAF asks other mods to respect). Read by editor id from AAF.esm itself.
Int Property AAFActorBusy = 0x00915A AutoReadOnly
Int Property AAFActorLocked = 0x017CEA AutoReadOnly

Float openedAt = -1.0      ; GetCurrentGameTime() when the window opened; -1 = closed
Int adopted = 0
Int healed = 0
Keyword busyKeyword
Keyword lockedKeyword

Event OnQuestInit()
	RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")
	LookUpAAF()
	OpenWindow()
EndEvent

; A load is a new lifetime for timers; an open window must survive it.
Event Actor.OnPlayerLoadGame(Actor akSender)
	LookUpAAF()
	If IsOpen()
		StartTimer(ScanSeconds, ScanTimer)
	EndIf
EndEvent

Function LookUpAAF()
	busyKeyword = None
	lockedKeyword = None
	If Game.IsPluginInstalled("AAF.esm")
		busyKeyword = Game.GetFormFromFile(AAFActorBusy, "AAF.esm") as Keyword
		lockedKeyword = Game.GetFormFromFile(AAFActorLocked, "AAF.esm") as Keyword
	EndIf
EndFunction

Function OpenWindow()
	openedAt = Utility.GetCurrentGameTime()
	Debug.Trace("Silhouette adopter: window opened at game day " + openedAt, 0)
	StartTimer(ScanSeconds, ScanTimer)
EndFunction

Bool Function IsOpen()
	Return openedAt >= 0.0 && Utility.GetCurrentGameTime() - openedAt < WindowDays
EndFunction

Float Function HoursLeft()
	If !IsOpen()
		Return 0.0
	EndIf
	Return (WindowDays - (Utility.GetCurrentGameTime() - openedAt)) * 24.0
EndFunction

Int Function Adopted()
	Return adopted
EndFunction

Int Function Healed()
	Return healed
EndFunction

Event OnTimer(Int aiTimerID)
	If aiTimerID != ScanTimer
		Return
	EndIf
	If !IsOpen()
		If openedAt >= 0.0
			Debug.Trace("Silhouette adopter: window closed after " + adopted + " actor(s)", 0)
		EndIf
		openedAt = -1.0
		Return
	EndIf
	; The next scan is scheduled BEFORE this one runs, so nothing below can stop
	; the window by failing.
	StartTimer(ScanSeconds, ScanTimer)
	Scan()
EndEvent

Function Scan()
	FormList seen = Game.GetFormFromFile(0x801, "Silhouette.esp") as FormList
	Actor[] people = Silhouette:Player.Nearby()
	Bool plugin = Silhouette:API.IsReady()
	String[] states = new String[0]
	If !plugin
		states = Silhouette:Player.StateMorphs()
	EndIf
	Int i = 0
	While i < people.Length
		Actor a = people[i]
		If a && !Busy(a)
			If !plugin
				Heal(a, states)
			EndIf
			If !(seen && seen.HasForm(a)) && Eligible(a)
				Adopt(a, seen, plugin)
			EndIf
		EndIf
		i += 1
	EndWhile
EndFunction

; In an AAF scene, or flagged for other mods to leave alone.
Bool Function Busy(Actor a)
	If busyKeyword && a.HasKeyword(busyKeyword)
		Return True
	EndIf
	If lockedKeyword && a.HasKeyword(lockedKeyword)
		Return True
	EndIf
	Return False
EndFunction

; A Silhouette body never holds a runtime state or a shaft value (decisions S-16,
; S-29), but bodies an older build gave can: Sirius_Male_preset once carried Erection
; at 100%, so two men kept one for good. Only the unkeyed value goes -- SetMorph with 0 erases exactly that
; key -- and only on a body Silhouette gave: a state another mod keeps under its own
; keyword, or one set by hand on a body that is not ours, stays where it is.
Function Heal(Actor a, String[] states)
	Bool female = Silhouette:Player.IsFemale(a)
	String[] found = new String[0]
	Int i = 0
	While i < states.Length
		If BodyGen.GetMorph(a, female, states[i], None) != 0.0
			found.Add(states[i], 1)
		EndIf
		i += 1
	EndWhile
	If found.Length == 0
		Return
	EndIf
	String preset = ""
	If female
		preset = Silhouette:Player.PresetOf(a, True, Silhouette:Player.FemaleMarkers(), Silhouette:Player.FemaleNames())
	Else
		preset = Silhouette:Player.PresetOf(a, False, Silhouette:Player.MaleMarkers(), Silhouette:Player.MaleNames())
	EndIf
	If preset == "" || preset == "*"
		Return
	EndIf
	Int j = 0
	While j < found.Length
		BodyGen.SetMorph(a, female, found[j], None, 0.0)
		j += 1
	EndWhile
	BodyGen.UpdateMorphs(a)
	healed += 1
	Debug.Trace("Silhouette adopter: " + a.GetFormID() + " (" + preset + ") lost " + found.Length + " runtime state(s) an older build baked in", 0)
EndFunction

; Holds body morphs, and every one of them under another mod's keyword.
Bool Function Eligible(Actor a)
	Bool female = Silhouette:Player.IsFemale(a)
	String[] morphs = BodyGen.GetMorphs(a, female)
	If !morphs || morphs.Length == 0
		Return False    ; nothing stored: LooksMenu's own BodyGen takes care of them
	EndIf
	Int i = 0
	While i < morphs.Length
		If BodyGen.GetMorph(a, female, morphs[i], None) != 0.0
			Return False    ; an unkeyed value: a Silhouette body, or sliders set by hand
		EndIf
		i += 1
	EndWhile
	Return True
EndFunction

; Remember every keyed value, let BodyGen roll the actor, put the values back. With
; the plugin ready, it does exactly that through its bridge, and the rules by name
; and faction get their say.
Function Adopt(Actor a, FormList seen, Bool abPlugin)
	If abPlugin
		If Silhouette:API.GenActor(a)
			If seen
				seen.AddForm(a)
			EndIf
			adopted += 1
			Debug.Trace("Silhouette adopter: " + a.GetFormID() + " handed to Silhouette.dll to be rolled", 0)
		EndIf
		Return
	EndIf
	Bool female = Silhouette:Player.IsFemale(a)
	String[] morphs = BodyGen.GetMorphs(a, female)
	String[] names = new String[0]
	Keyword[] keys = new Keyword[0]
	Float[] values = new Float[0]
	Int i = 0
	While i < morphs.Length
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
	BodyGen.UpdateMorphs(a)
	If seen
		seen.AddForm(a)
	EndIf
	adopted += 1
	Debug.Trace("Silhouette adopter: " + a.GetFormID() + " rolled by BodyGen, kept " + names.Length + " keyed morph(s)", 0)
EndFunction

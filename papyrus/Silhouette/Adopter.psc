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
 After 24 in-game hours the window closes itself.}

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
	Int i = 0
	While i < people.Length
		Actor a = people[i]
		If a && Candidate(a, seen) && Eligible(a)
			Adopt(a, seen)
		EndIf
		i += 1
	EndWhile
EndFunction

Bool Function Candidate(Actor a, FormList seen)
	If seen && seen.HasForm(a)
		Return False
	EndIf
	If busyKeyword && a.HasKeyword(busyKeyword)
		Return False
	EndIf
	If lockedKeyword && a.HasKeyword(lockedKeyword)
		Return False
	EndIf
	Return True
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

; Remember every keyed value, let BodyGen roll the actor, put the values back.
Function Adopt(Actor a, FormList seen)
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

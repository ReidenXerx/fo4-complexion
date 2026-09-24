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
 hand in LooksMenu; looked at once), anyone AAF has busy or locked, and anyone
 already processed. After 24 in-game hours the window closes itself.

 With Silhouette.dll ready, a person is handed to it (Silhouette:DLL.RequestAdopt):
 the plugin rolls them the same way, records that it owes the roll (a save before
 it lands does not lose it, S-59), and says no for anyone whose body is somebody's
 choice, who was reset (S-53), or who is being picked -- those are asked again at
 the next scan, until they have a body. Without it this script rolls them itself,
 and also heals Silhouette bodies an older build gave with a runtime state or a
 shaft value in them (decisions S-16, S-29) -- the plugin's touch-up does that for
 everyone it sees.}

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
Bool looksMenu = False     ; LooksMenu's F4SE plugin ("F4EE"): without it no BodyGen call is made
; Real time the running scan began, -1 when none runs. A scan waits a frame for every
; LooksMenu call, and the next timer can fire while one is still going.
Float scanStarted = -1.0

Event OnQuestInit()
	RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")
	LookUpAAF()
	OpenWindow()
EndEvent

; A load is a new lifetime for timers; an open window must survive it.
Event Actor.OnPlayerLoadGame(Actor akSender)
	scanStarted = -1.0
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
	looksMenu = F4SE.GetPluginVersion("F4EE") > 0
EndFunction

Function OpenWindow()
	openedAt = Utility.GetCurrentGameTime()
	; A new window looks at everyone again: an id the game has since handed to someone
	; new would otherwise keep the old person's place on the list.
	FormList seen = Game.GetFormFromFile(0x801, "Silhouette.esp") as FormList
	If seen
		seen.Revert()
	EndIf
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
	Float now = Utility.GetCurrentRealTime()
	If scanStarted >= 0.0 && now >= scanStarted && now - scanStarted < 120.0
		Return    ; the last scan is still going
	EndIf
	scanStarted = now
	Scan()
	scanStarted = -1.0
EndEvent

Function Scan()
	If !looksMenu
		Return    ; every BodyGen call would fail and fill the log
	EndIf
	FormList seen = Game.GetFormFromFile(0x801, "Silhouette.esp") as FormList
	FormList looked = Game.GetFormFromFile(0x804, "Silhouette.esp") as FormList
	Actor[] people = Silhouette:Player.Nearby()
	Bool plugin = Silhouette:API.IsReady()
	String[] states = new String[0]
	String[] femaleMarkers = new String[0]
	String[] maleMarkers = new String[0]
	If !plugin
		states = Silhouette:Player.StateMorphs()
		femaleMarkers = Silhouette:Player.FemaleMarkers()
		maleMarkers = Silhouette:Player.MaleMarkers()
	EndIf
	Int i = 0
	While i < people.Length
		Actor a = people[i]
		If a && !Busy(a)
			Bool isSeen = seen && seen.HasForm(a)
			Bool isLooked = looked && looked.HasForm(a)
			If !isSeen || (!plugin && !isLooked)
				Bool female = Silhouette:Player.IsFemale(a)
				String[] morphs = BodyGen.GetMorphs(a, female)
				If !plugin && !isLooked
					If female
						Heal(a, female, morphs, states, femaleMarkers, looked)
					Else
						Heal(a, female, morphs, states, maleMarkers, looked)
					EndIf
				EndIf
				If !isSeen
					Int kind = Kind(a, female, morphs)
					If kind == 1
						Adopt(a, female, seen, plugin)
					ElseIf kind == 2 && seen
						seen.AddForm(a)    ; a body of their own: never the window's, not read again
					EndIf
				EndIf
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
; at 100%, so two men kept one for good. Only the unkeyed value goes -- SetMorph with
; 0 erases exactly that key -- and only on a body Silhouette gave: a state another mod
; keeps under its own keyword, or one set by hand on a body that is not ours, stays.
; Names first (one call, compared as strings): most bodies hold none of these at all.
; Each person is looked at once, so a value set by hand afterwards stays.
Function Heal(Actor a, Bool female, String[] morphs, String[] states, String[] markers, FormList looked)
	If looked
		looked.AddForm(a)
	EndIf
	If !morphs
		Return
	EndIf
	String[] found = new String[0]
	String marker = ""
	Int i = 0
	While i < morphs.Length
		If states.Find(morphs[i], 0) >= 0
			found.Add(morphs[i], 1)
		ElseIf marker == "" && markers.Find(morphs[i], 0) >= 0
			marker = morphs[i]
		EndIf
		i += 1
	EndWhile
	If found.Length == 0 || marker == ""
		Return
	EndIf
	; A marker counts only while it holds a value: an emptied name is listed until a load.
	If BodyGen.GetMorph(a, female, marker, None) <= 0.0
		Return
	EndIf
	Int zeroed = 0
	Int j = 0
	While j < found.Length
		If BodyGen.GetMorph(a, female, found[j], None) != 0.0
			BodyGen.SetMorph(a, female, found[j], None, 0.0)
			zeroed += 1
		EndIf
		j += 1
	EndWhile
	If zeroed > 0
		BodyGen.UpdateMorphs(a)
		healed += 1
		Debug.Trace("Silhouette adopter: " + a.GetFormID() + " (" + marker + ") lost " + zeroed + " runtime state(s) an older build baked in", 0)
	EndIf
EndFunction

; 1: holds body morphs, every one of them under another mod's keyword, and at least
; one of those with a value -- the window's to roll. 2: an unkeyed value, a body of
; their own (a Silhouette body, or sliders set by hand). 0: nothing to go on yet: an
; emptied name is listed until the next load, and someone with nothing stored at all
; is LooksMenu's own BodyGen's to give a body.
Int Function Kind(Actor a, Bool female, String[] morphs)
	If !morphs || morphs.Length == 0
		Return 0
	EndIf
	Bool keyed = False
	Int i = 0
	While i < morphs.Length
		If BodyGen.GetMorph(a, female, morphs[i], None) != 0.0
			Return 2
		EndIf
		If !keyed
			Keyword[] kws = BodyGen.GetKeywords(a, female, morphs[i])
			If kws
				Int k = 0
				While !keyed && k < kws.Length
					If kws[k] && BodyGen.GetMorph(a, female, morphs[i], kws[k]) != 0.0
						keyed = True
					EndIf
					k += 1
				EndWhile
			EndIf
		EndIf
		i += 1
	EndWhile
	If keyed
		Return 1
	EndIf
	Return 0
EndFunction

; Remember every keyed value, let BodyGen roll the actor, put the values back. With
; the plugin ready, it does exactly that through its bridge, the rules by name and
; faction get their say, and it says no for anyone it has a reason to leave alone.
; Only an accepted hand-off is not asked about again: the plugin owes that roll and
; keeps it across a save (S-59); a refusal (a change on its way, a picking) is asked
; again at the next scan -- once they have a body of their own, Kind says so.
Function Adopt(Actor a, Bool female, FormList seen, Bool abPlugin)
	If abPlugin
		If !Silhouette:DLL.CanShape(a.GetFormID())
			; Never Silhouette's (a race it does not shape): a refusal that will not change, so
			; they are not asked about again for the rest of the window.
			If seen
				seen.AddForm(a)
			EndIf
			Return
		EndIf
		String why = Silhouette:DLL.RequestAdopt(a.GetFormID())
		If why == ""
			If seen
				seen.AddForm(a)
			EndIf
			adopted += 1
			Debug.Trace("Silhouette adopter: " + a.GetFormID() + " handed to Silhouette.dll to be rolled", 0)
		Else
			Debug.Trace("Silhouette adopter: " + a.GetFormID() + " left to Silhouette.dll for now: " + why, 0)
		EndIf
		Return
	EndIf
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
	BodyGen.UpdateMorphs(a)
	If seen
		seen.AddForm(a)
	EndIf
	adopted += 1
	Debug.Trace("Silhouette adopter: " + a.GetFormID() + " rolled by BodyGen, kept " + names.Length + " keyed morph(s)", 0)
EndFunction

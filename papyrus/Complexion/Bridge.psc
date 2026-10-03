Scriptname Complexion:Bridge extends Quest
{The hands of Complexion.dll: it decides every NPC's overlays, this script puts them on through LooksMenu.
 One poll timer, and only while the game runs; no waits, no per-NPC faction scans, no cloak (ROF's costs,
 docs/complexion-research.md). An order is a whole look: every entry added, then ONE Update, then a check with
 GetAll that each landed (C-6).

 Ours are told from every other mod's by their priority: Complexion's are negative, everyone else's (AAF counts
 from 0) are not. A rebuild keeps every entry that is not ours, with all its data.}

Int Property Protocol = 2 AutoReadOnly  ; 2: the overlay window (C-19)
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
Bool _rapport = False
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
	WindowForget()
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
	_rapport = Game.IsPluginInstalled("Rapport.esp")
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
	If _rapport
		; Rapport's persona, through the script that holds Rapport's types (Complexion:Persona); without Rapport
		; that script did not load and CastAs gives None.
		ScriptObject persona = Self.CastAs("Complexion:Persona")
		If persona
			Var[] args = new Var[1]
			args[0] = a
			String p = persona.CallFunction("Of", args) as String
			If p != ""
				Complexion:DLL.OrderPersona(aiOrder, p)
			EndIf
		EndIf
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

;---------------------------------------------------------------------------
; C-19: the overlay window, ported from Silhouette's picker window (S-79). F4SE opens
; Interface\ComplexionMenu.swf as a custom menu -- F4SE's own menu, none of CommonLibF4's menu code.
; Whose skin: the NPC the player aimed at in the last seconds ("them"), or the player ("me").
; They are held still, undressed and framed by the camera while it is open. A click puts an
; overlay on them or takes it off, live; Apply keeps the look (their decision from now on, C-4);
; anything else that closes the window puts back what they had -- the one place that happens is
; the menu's close event. Neither the menu nor the event registrations survive a load: opening
; registers again. The hotkey opens it at once; MCM's buttons open it when the pause menu closes.
;
; Every call into LooksMenu or the plugin can hand this script to another thread, so the window's
; work runs in SESSIONS (Silhouette's lesson): opening, closing and the Them / Me switch each start a
; new one, and work of an older session stops at its next step and takes back what it did. Previews
; run one at a time, the latest asked for last.
;---------------------------------------------------------------------------
String Property WindowMenu = "ComplexionMenu" AutoReadOnly
Float Property WindowAimSeconds = 10.0 AutoReadOnly  ; an NPC aimed at this recently still counts
Int Property WindowPer = 15 AutoReadOnly             ; cards on a page: the panel's grid
Int Property PipBoyID = 0x021B3B AutoReadOnly         ; the Pip-Boy (Fallout4.esm): never taken off

Int _winThem = 0            ; the NPC aimed at when the window opened, 0 for none
Bool _winMe = False         ; the window is on the player
Bool _winApplied = False    ; Apply was pressed: the close keeps what is on
Bool _winAfterMenu = False  ; an MCM button asked for the window: it opens when the pause menu closes
Int _winAfterTarget = 0     ; ... on this NPC, 0 for the player
Int _winSession = 0         ; bumped by every open, close and switch: older work stops
Bool _winOpen = False
Bool _winClosing = False    ; the close is putting things back: no new window until it is done
Int _winLoaded = 0          ; the session whose contents were sent: the window's two "ready"s load it once
Int _winTarget = 0          ; whose overlays the session edits
Bool _winTouched = False    ; a preview was put on them: the close puts back what they had unless applied
Bool _winPreviewing = False ; a preview is being put on
Bool _winWantPreview = False
InputEnableLayer _winInput
; The NPC held in place (SetRestrained), and the clothes taken off and from whom: kept in the save, so a save
; made while the window was open still lets them go and dresses them at the next load (Connect).
Int _winHeld = 0
Form[] _winClothes
Int _winClothesOn = 0

; The hotkey: the NPC in the player's sights (or aimed at in the last seconds), else the player. Pressed while
; the window is open, it closes it (as Cancel): a way out whatever the window's own input does.
Function OpenWindow()
	If UI.IsMenuOpen(WindowMenu)
		CloseWindow()
		Return
	EndIf
	Int target = 0
	If _plugin
		target = Complexion:DLL.CrosshairActor(WindowAimSeconds)
	EndIf
	OpenWindowOn(target)
EndFunction

; MCM's button: whoever was aimed at in the half minute before the menu opened.
Function MenuOpenWindow()
	Int target = 0
	If _plugin
		target = Complexion:DLL.CrosshairActor(30.0)
	EndIf
	If target == 0
		Debug.Notification("Complexion: nobody was in your sights before the menu opened - the window opens on you.")
	EndIf
	OpenWindowAfterMenu(target)
EndFunction

; MCM's other button: the player.
Function MenuOpenWindowMe()
	OpenWindowAfterMenu(0)
EndFunction

Function OpenWindowAfterMenu(Int aiTarget)
	_winAfterMenu = True
	_winAfterTarget = aiTarget
	RegisterForMenuOpenCloseEvent("PauseMenu")
	Debug.Notification("Complexion: the overlay window opens when you close the menu.")
EndFunction

Function OpenWindowOn(Int aiTarget)
	If UI.IsMenuOpen(WindowMenu) || _winOpen
		Return
	EndIf
	If _winClosing
		Debug.Notification("Complexion: the window is still putting things back - a moment.")
		Return
	EndIf
	If !_plugin
		Debug.MessageBox("Complexion: Complexion.dll is not connected, so the overlay window has nothing to show.")
		Return
	EndIf
	If Game.GetPlayer().IsInCombat()
		Debug.Notification("Complexion: not in combat.")
		Return
	EndIf
	If !UI.IsMenuRegistered(WindowMenu)
		UI:MenuData data = new UI:MenuData
		; ScreenArcherMenu's flags (cursor, modal, the game running behind it), as Silhouette's window: the menu
		; input context (0x8) once left a player unable to click anything, not even Esc (Silhouette 0.3.1).
		data.menuFlags = 0x8018496
		; Keep the cursor even with a gamepad plugged in: F4SE's "check for gamepad" (2) takes it away.
		data.extendedFlags = 1
		If !UI.RegisterCustomMenu(WindowMenu, "ComplexionMenu", "root1.Menu_mc", data)
			Debug.MessageBox("Complexion: the overlay window could not be registered. Is Interface/ComplexionMenu.swf installed?")
			Return
		EndIf
	EndIf
	RegisterForExternalEvent("Complexion_WindowReady", "OnWindowReady")
	RegisterForExternalEvent("Complexion_WindowPage", "OnWindowPage")
	RegisterForExternalEvent("Complexion_WindowToggle", "OnWindowToggle")
	RegisterForExternalEvent("Complexion_WindowClear", "OnWindowClear")
	RegisterForExternalEvent("Complexion_WindowRoll", "OnWindowRoll")
	RegisterForExternalEvent("Complexion_WindowApply", "OnWindowApply")
	RegisterForExternalEvent("Complexion_WindowCancel", "OnWindowCancel")
	RegisterForExternalEvent("Complexion_WindowTarget", "OnWindowTarget")
	RegisterForExternalEvent("Complexion_WindowNote", "OnWindowNote")
	RegisterForMenuOpenCloseEvent(WindowMenu)
	_winSession += 1
	_winOpen = True
	_winThem = aiTarget
	_winMe = _winThem == 0
	_winApplied = False
	_winTouched = False
	_winWantPreview = False
	WindowLockControls()
	UI.OpenMenu(WindowMenu)
	; F4SE keeps the window's movie between openings: once it is open it is told to start again (Panel.Begin),
	; and asks for its contents. A first opening also says so by itself; that one is loaded once (_winLoaded).
	Int session = _winSession
	Int i = 0
	While !UI.IsMenuOpen(WindowMenu) && i < 40
		Utility.WaitMenuMode(0.05)
		i += 1
	EndWhile
	If WindowLive(session)
		UI.Invoke(WindowMenu, "root1.Menu_mc.Begin")
	EndIf
EndFunction

; Movement, fighting, looking, the camera switch, sneaking, activating, the journal, VATS, favourites, running and
; jumping: off while the window is open (a custom menu does not take them by itself -- Silhouette 0.3.1).
Function WindowLockControls()
	If _winInput
		Return
	EndIf
	_winInput = InputEnableLayer.Create()
	_winInput.DisablePlayerControls(True, True, True, True, True, False, True, True, True, True, True)
	_winInput.EnableJumping(False)
EndFunction

Function WindowUnlockControls()
	If _winInput
		InputEnableLayer layer = _winInput
		_winInput = None
		layer.Delete()
	EndIf
EndFunction

Bool Function WindowLive(Int aiSession)
	Return _winOpen && aiSession == _winSession
EndFunction

; What the window received, into Complexion.log: the evidence for an input problem.
Function OnWindowNote(String asNote)
	If _plugin
		Complexion:DLL.Log("window: " + asNote)
	EndIf
EndFunction

Function OnWindowReady()
	If !_winOpen || _winLoaded == _winSession
		Return
	EndIf
	_winLoaded = _winSession
	WindowLoad(_winSession)
EndFunction

Function WindowLoad(Int aiSession)
	Actor a
	String mode = "them"
	If _winMe
		a = Game.GetPlayer()
		mode = "me"
	Else
		a = Game.GetForm(_winThem) as Actor
	EndIf
	If !a
		WindowTarget("Nobody", mode, False)
		WindowStatus("They are gone.")
		Return
	EndIf
	Bool female = a.GetLeveledActorBase().GetSex() == 1
	String name = "You"
	If !_winMe
		name = Complexion:DLL.NameOf(a.GetFormID())
	EndIf
	If a.IsDead() || a.IsChild() || Busy(a)
		WindowTarget(name, mode, female)
		If a.IsDead()
			WindowStatus("Complexion leaves the dead alone.")
		ElseIf a.IsChild()
			WindowStatus("Complexion leaves children alone.")
		Else
			WindowStatus("They are in an AAF scene: AAF holds their overlays until it ends.")
		EndIf
		Return
	EndIf
	String said = Complexion:DLL.WindowBegin(a.GetFormID(), female)
	If !WindowLive(aiSession)
		Complexion:DLL.WindowEnd()
		Return
	EndIf
	_winTarget = a.GetFormID()
	WindowTarget(name, mode, female)
	If said != ""
		WindowStatus(said)
		Return
	EndIf
	WindowStatus(WindowSays())
	If !_winMe
		WindowHold(a, aiSession)
	Else
		Game.ForceThirdPerson()  ; the free camera shows the body the third-person view has
	EndIf
	WindowUndress(a, aiSession)
	WindowFrame(a, aiSession)
EndFunction

String Function WindowSays()
	Int n = Complexion:DLL.WindowCount()
	If n == 0
		Return "No overlay of Complexion's on them. Click one to put it on; Random rolls a look."
	EndIf
	Return n + " overlay(s) of Complexion's on them. Click to put one on or take it off."
EndFunction

; A page the panel asks for: the category, the search, the page. Sent back with what was asked, so the panel
; drops an answer it no longer wants.
Function OnWindowPage(String asCategory, String asSearch, Int aiPage)
	If !_winOpen || _winTarget == 0
		Return
	EndIf
	Var[] args = new Var[4]
	args[0] = Complexion:DLL.WindowPage(asCategory, asSearch, aiPage, WindowPer)
	args[1] = asCategory
	args[2] = asSearch
	args[3] = aiPage
	UI.Invoke(WindowMenu, "root1.Menu_mc.SetPage", args)
EndFunction

Function OnWindowToggle(String asKey)
	If !_winOpen || _winTarget == 0 || _winClosing
		Return
	EndIf
	Bool on = Complexion:DLL.WindowToggle(asKey)
	Var[] args = new Var[3]
	args[0] = asKey
	args[1] = on
	args[2] = Complexion:DLL.WindowCount()
	UI.Invoke(WindowMenu, "root1.Menu_mc.SetOn", args)
	WindowStatus(WindowSays())
	WindowPreviewSoon()
EndFunction

Function OnWindowClear()
	If !_winOpen || _winTarget == 0 || _winClosing
		Return
	EndIf
	Complexion:DLL.WindowClear()
	WindowRefresh()
	WindowPreviewSoon()
EndFunction

Function OnWindowRoll()
	If !_winOpen || _winTarget == 0 || _winClosing
		Return
	EndIf
	Complexion:DLL.WindowRoll()
	WindowRefresh()
	WindowPreviewSoon()
EndFunction

; The panel asks again for the page it shows: the marks on its cards follow the draft.
Function WindowRefresh()
	Var[] args = new Var[1]
	args[0] = Complexion:DLL.WindowCount()
	UI.Invoke(WindowMenu, "root1.Menu_mc.Refresh", args)
	WindowStatus(WindowSays())
EndFunction

; One preview at a time, the latest asked for last: fast clicks ask for many, and only the last matters.
Function WindowPreviewSoon()
	_winWantPreview = True
	If _winPreviewing
		Return
	EndIf
	_winPreviewing = True
	Int session = _winSession
	While _winWantPreview && WindowLive(session)
		_winWantPreview = False
		_winTouched = True
		WindowRun(Complexion:DLL.WindowPreview())
	EndWhile
	_winWantPreview = False
	_winPreviewing = False
EndFunction

; A window order: ours on them replaced by the order's, even when it holds none -- every other mod's kept.
Function WindowRun(Int aiOrder)
	If aiOrder == 0
		Return
	EndIf
	Actor a = Game.GetForm(Complexion:DLL.OrderActor(aiOrder)) as Actor
	If !a || !a.Is3DLoaded()
		Complexion:DLL.OrderGone(aiOrder)
		Return
	EndIf
	Bool female = Complexion:DLL.OrderFemale(aiOrder)
	Int count = Complexion:DLL.OrderCount(aiOrder)
	If HasOurs(a, female)
		Rebuild(a, female)
	EndIf
	AddOurs(a, female, aiOrder, count)
	Overlays.Update(a)
	Bool landed = Landed(a, female, aiOrder, count)
	If !landed
		Rebuild(a, female)
		AddOurs(a, female, aiOrder, count)
		Overlays.Update(a)
		landed = Landed(a, female, aiOrder, count)
	EndIf
	Complexion:DLL.OrderDone(aiOrder, landed)
EndFunction

Function OnWindowApply()
	If !_winOpen || _winApplied
		Return
	EndIf
	_winApplied = True
	WindowSettle()
	If _winTarget != 0
		Complexion:DLL.WindowApply()
		Debug.Notification("Complexion: kept - " + Complexion:DLL.WindowCount() + " overlay(s).")
	EndIf
	UI.CloseMenu(WindowMenu)
EndFunction

Function OnWindowCancel()
	UI.CloseMenu(WindowMenu)
EndFunction

; Closes the window as Cancel does: the hotkey again, or the console -- cgf "Complexion:Bridge.CloseWindow" is not
; a global, so the hotkey is the way.
Function CloseWindow()
	If UI.IsMenuOpen(WindowMenu)
		UI.CloseMenu(WindowMenu)
	EndIf
EndFunction

; The Them / Me switch: a new session; what was tried on the one being left is put back first.
Function OnWindowTarget(String asMode)
	If !_winOpen
		Return
	EndIf
	_winSession += 1
	Int session = _winSession
	WindowSettle()
	WindowRelease()
	WindowUnframe()
	WindowUndo()
	WindowRedress()
	Complexion:DLL.WindowEnd()
	_winTarget = 0
	If !WindowLive(session)
		Return
	EndIf
	_winMe = asMode == "me" || _winThem == 0
	_winLoaded = session
	WindowLoad(session)
EndFunction

Event OnMenuOpenCloseEvent(string asMenuName, bool abOpening)
	If asMenuName == "PauseMenu"
		If !abOpening && _winAfterMenu
			_winAfterMenu = False
			UnregisterForMenuOpenCloseEvent("PauseMenu")
			OpenWindowOn(_winAfterTarget)
		EndIf
		Return
	EndIf
	If asMenuName != WindowMenu || abOpening || !_winOpen
		Return
	EndIf
	; Everything the window started is put back: the camera and the hold first (the player sees them at once),
	; then the overlays -- once any preview still being put on has landed -- then the clothes.
	_winOpen = False
	_winSession += 1
	_winClosing = True
	WindowUnlockControls()
	WindowRelease()
	WindowUnframe()
	WindowSettle()
	If !_winApplied
		WindowUndo()
	EndIf
	WindowRedress()
	Complexion:DLL.WindowEnd()
	_winTarget = 0
	_winApplied = False
	_winClosing = False
EndEvent

; Waits for a preview still being put on (at most 5 seconds): what is put back must come after it.
Function WindowSettle()
	Int i = 0
	While _winPreviewing && i < 100
		Utility.WaitMenuMode(0.05)
		i += 1
	EndWhile
EndFunction

; What they had before the window: put back when the window put anything on them.
Function WindowUndo()
	If _winTouched && _winTarget != 0
		WindowRun(Complexion:DLL.WindowRestore())
	EndIf
	_winTouched = False
EndFunction

; Held in place while their skin is chosen: SetRestrained, the game's own "cannot move" -- their AI keeps
; running, and they carry on once let go. Nobody is held whose movement the game or another mod may hold.
Function WindowHold(Actor akActor, Int aiSession)
	WindowRelease()
	If !WindowLive(aiSession) || !akActor || akActor.IsDead() || akActor.IsInCombat() || akActor.IsInScene() || Busy(akActor)
		Return
	EndIf
	akActor.SetRestrained(True)
	_winHeld = akActor.GetFormID()
	If !WindowLive(aiSession)
		WindowRelease()
	EndIf
EndFunction

Function WindowRelease()
	If _winHeld == 0
		Return
	EndIf
	Actor held = Game.GetForm(_winHeld) as Actor
	_winHeld = 0
	If held
		held.SetRestrained(False)
	EndIf
EndFunction

; Undressed while the window shows their skin (the owner, 2026-10-04): every piece of armor and clothing they
; wear, by F4SE's worn slots, is taken off -- the Pip-Boy stays -- and written down, so the close (or the next
; load, for a save made in between) puts the same things back on. NPCs are kept from dressing again by
; themselves meanwhile (UnequipItem's "prevent equip").
Function WindowUndress(Actor akActor, Int aiSession)
	WindowRedress()
	If !WindowLive(aiSession) || !akActor
		Return
	EndIf
	Form pipboy = Game.GetFormFromFile(PipBoyID, "Fallout4.esm")
	Form[] worn = new Form[0]
	Int slot = 0
	While slot < 44
		Actor:WornItem w = akActor.GetWornItem(slot)
		If w && w.item && (w.item as Armor) && w.item != pipboy && worn.Find(w.item) < 0
			worn.Add(w.item)
		EndIf
		slot += 1
	EndWhile
	_winClothes = worn
	_winClothesOn = akActor.GetFormID()
	Bool npc = akActor != Game.GetPlayer()
	Int i = 0
	While i < worn.Length
		akActor.UnequipItem(worn[i], npc, True)
		i += 1
	EndWhile
EndFunction

Function WindowRedress()
	If _winClothesOn == 0
		Return
	EndIf
	Actor a = Game.GetForm(_winClothesOn) as Actor
	Form[] worn = _winClothes
	_winClothesOn = 0
	_winClothes = None
	If !a || !worn
		Return
	EndIf
	Int i = 0
	While i < worn.Length
		If worn[i] && a.GetItemCount(worn[i]) > 0
			a.EquipItem(worn[i], False, True)
		EndIf
		i += 1
	EndWhile
EndFunction

; The camera in front of them, the window beside them (the game's free camera, switched off again when the
; window closes). Where the camera cannot be moved, the window works as it is and the log says why.
Function WindowFrame(Actor akActor, Int aiSession)
	If !_plugin || !akActor || !WindowLive(aiSession)
		Return
	EndIf
	WindowCameraWait(Complexion:DLL.CameraFrame(akActor.GetPositionX(), akActor.GetPositionY(), akActor.GetPositionZ(), akActor.GetAngleZ(), akActor.GetHeight()))
	If !WindowLive(aiSession)
		WindowUnframe()
	EndIf
EndFunction

Function WindowUnframe()
	If _plugin
		WindowCameraWait(Complexion:DLL.CameraRestore())
	EndIf
EndFunction

; The game carries out "tfc" a frame or more after it is typed: the plugin answers "wait" until it has, and gives
; up by itself after 3 seconds.
Function WindowCameraWait(String asSaid)
	Int i = 0
	While asSaid == "wait" && i < 80
		Utility.WaitMenuMode(0.05)
		asSaid = Complexion:DLL.CameraStep()
		i += 1
	EndWhile
	If asSaid != "" && asSaid != "wait"
		Complexion:DLL.Log("window: camera: " + asSaid)
	EndIf
EndFunction

; A load forgets the window: the menu is gone, and nothing of it may carry into the save just loaded -- but
; whoever it held or undressed in a save made while it was open is let go and dressed.
Function WindowForget()
	WindowUnlockControls()
	WindowRelease()
	WindowRedress()
	_winSession += 1
	_winOpen = False
	_winClosing = False
	_winPreviewing = False
	_winWantPreview = False
	_winApplied = False
	_winTouched = False
	_winTarget = 0
	If _winAfterMenu
		_winAfterMenu = False
		UnregisterForMenuOpenCloseEvent("PauseMenu")
	EndIf
EndFunction

; Whose skin, for the panel: a name, whether an NPC was aimed at ("Them" works), "them" or "me", their sex, and
; the build of the picture atlases (an atlas of another build is not mounted: no picture rather than the wrong one).
Function WindowTarget(String asName, String asMode, Bool abFemale)
	Var[] args = new Var[5]
	args[0] = asName
	args[1] = _winThem != 0
	args[2] = asMode
	args[3] = abFemale
	args[4] = Complexion:DLL.WindowBuild()
	UI.Invoke(WindowMenu, "root1.Menu_mc.SetTarget", args)
EndFunction

Function WindowStatus(String asStatus)
	Var[] args = new Var[1]
	args[0] = asStatus
	UI.Invoke(WindowMenu, "root1.Menu_mc.SetStatus", args)
EndFunction

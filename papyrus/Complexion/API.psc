Scriptname Complexion:API Hidden
{Global ways in, for MCM's hotkey and buttons and the console: cgf "Complexion:API.OpenWindow".
 Complexion's quest carries two scripts (the bridge, and Persona for Rapport, C-14), and MCM's keybind call on the
 quest never reached the bridge's OpenWindow (the owner's test, 2026-10-04): a global function finds the bridge
 itself.}

Complexion:Bridge Function Bridge() Global
	Return Game.GetFormFromFile(0x800, "Complexion.esp") as Complexion:Bridge
EndFunction

; The overlay window (C-19) on the NPC in the player's sights, else on the player. Pressed while it is open: closes it.
Function OpenWindow() Global
	Complexion:Bridge b = Bridge()
	If b
		b.OpenWindow()
	Else
		Debug.Notification("Complexion: its quest is not running - is Complexion.esp enabled?")
	EndIf
EndFunction

; From MCM's buttons: opened when the pause menu closes.
Function MenuOpenWindow() Global
	Complexion:Bridge b = Bridge()
	If b
		b.MenuOpenWindow()
	EndIf
EndFunction

Function MenuOpenWindowMe() Global
	Complexion:Bridge b = Bridge()
	If b
		b.MenuOpenWindowMe()
	EndIf
EndFunction

Function CloseWindow() Global
	Complexion:Bridge b = Bridge()
	If b
		b.CloseWindow()
	EndIf
EndFunction

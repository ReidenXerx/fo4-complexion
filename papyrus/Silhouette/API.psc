Scriptname Silhouette:API Hidden
{Silhouette for other mods (decision S-24): OBody NG's functions, by OBody's names,
 as global functions. Every one is safe to call whatever is installed: without
 Silhouette.dll they do nothing and say so through their return value.

 Events: register on the bridge quest --
     RegisterForCustomEvent(Silhouette:API.Bridge(), "OnActorGenerated")
     Event Silhouette:Bridge.OnActorGenerated(Silhouette:Bridge akSender, Var[] akArgs)
         Actor who = akArgs[0] as Actor
         String preset = akArgs[1] as String
     EndEvent
 OnActorGenerated [Actor, String preset], OnActorNaked [Actor],
 OnActorRemovingClothes [Actor], OnORefitChanged [Actor, Bool applied].

 A body change asked for here is carried out by the bridge a moment later, not
 inside the call: LooksMenu is reached through Papyrus, one frame per value.
 GetPresetAssignedToActor already answers with the decision.

 Every argument is passed explicitly: the base sources carry no default values.}

; The order protocol these scripts were built for (Silhouette:Bridge.Protocol).
Int Function Protocol() Global
	Return 2
EndFunction

; Silhouette.esp's bridge quest, for RegisterForCustomEvent. None without the plugin.
Silhouette:Bridge Function Bridge() Global
	If !Game.IsPluginInstalled("Silhouette.esp")
		Return None
	EndIf
	Return Game.GetFormFromFile(0x802, "Silhouette.esp") as Silhouette:Bridge
EndFunction

; Silhouette.dll is loaded and from the same release as these scripts. Nothing
; below calls it otherwise: a missing or mismatched native only fills the log.
Bool Function Loaded() Global
	If F4SE.GetPluginVersion("Silhouette") <= 0
		Return False
	EndIf
	Return Silhouette:DLL.ProtocolVersion() == Protocol()
EndFunction

; The plugin is loaded, its catalog matches the BodyGen files, and the bridge exists.
Bool Function IsReady() Global
	Return Loaded() && Silhouette:DLL.IsReady() && Bridge() != None
EndFunction

; Why the last call here said no.
String Function LastError() Global
	If F4SE.GetPluginVersion("Silhouette") <= 0
		Return "Silhouette.dll is not loaded"
	EndIf
	If !Loaded()
		Return "Silhouette.dll is from another release than its scripts"
	EndIf
	Return Silhouette:DLL.LastError()
EndFunction

; One message: what is loaded, what it listens to, how much work waits. For the MCM,
; and for anyone asking why nothing happens -- it works without Silhouette.esp.
Function ShowStatus() Global
	String esp = " Silhouette.esp is enabled."
	If !Game.IsPluginInstalled("Silhouette.esp")
		esp = " Silhouette.esp is NOT enabled: without it nothing carries the plugin's decisions out."
	EndIf
	If F4SE.GetPluginVersion("Silhouette") <= 0
		Debug.MessageBox("Silhouette: Silhouette.dll is not loaded. BodyGen still gives everyone a body; the rules by name and faction, ORefit, the NPC picker and the API are off." + esp)
		Return
	EndIf
	If !Loaded()
		Debug.MessageBox("Silhouette: Silhouette.dll and its scripts are from different releases. Install one release's files together." + esp)
		Return
	EndIf
	Debug.MessageBox("Silhouette " + Silhouette:DLL.Version() + ": " + Silhouette:DLL.Status() + "." + esp)
EndFunction

Bool Function IsFemale(Actor akActor) Global
	If !akActor
		Return False
	EndIf
	Return akActor.GetLeveledActorBase().GetSex() == 1
EndFunction

; The preset the actor has: the one Silhouette decided (even if the bridge has not
; made it yet), else the one their body's marker names. "" for none, or for a body
; Silhouette did not give.
String Function GetPresetAssignedToActor(Actor akActor) Global
	If !akActor || !Loaded()
		Return ""
	EndIf
	String decided = Silhouette:DLL.AssignedPreset(akActor.GetFormID())
	If decided != ""
		Return decided
	EndIf
	Return MarkerPreset(akActor)
EndFunction

; What their marker names, read from LooksMenu now.
String Function MarkerPreset(Actor akActor) Global
	If !akActor || !Loaded()
		Return ""
	EndIf
	Bool female = IsFemale(akActor)
	String[] morphs = BodyGen.GetMorphs(akActor, female)
	Int count = 0
	If morphs
		count = morphs.Length
	EndIf
	Int i = 0
	While i < count
		If Silhouette:DLL.MarkerKind(morphs[i]) == 1
			Float v = BodyGen.GetMorph(akActor, female, morphs[i], None)
			If v > 0.0
				Return Silhouette:DLL.PresetForMarker(morphs[i], v)
			EndIf
		EndIf
		i += 1
	EndWhile
	Return ""
EndFunction

; Every preset that fits this actor's body, as the pickers offer them.
String[] Function GetAllPossiblePresets(Actor akActor) Global
	String[] out = new String[0]
	If !akActor || !Loaded()
		Return out
	EndIf
	Bool female = IsFemale(akActor)
	Int n = Silhouette:DLL.PresetCount(female)
	Int i = 0
	While i < n && i < 128
		out.Add(Silhouette:DLL.PresetName(female, i), 1)
		i += 1
	EndWhile
	Return out
EndFunction

; Gives the actor this preset, kept like a choice made in the picker: rules do not
; override it. False (and LastError says why) for a preset that does not fit them.
Bool Function AssignPresetToActor(Actor akActor, String asPreset) Global
	If !akActor || !Loaded()
		Return False
	EndIf
	Return Silhouette:DLL.RequestPreset(akActor.GetFormID(), asPreset, 4)
EndFunction

Bool Function ApplyPresetByName(Actor akActor, String asPreset) Global
	Return AssignPresetToActor(akActor, asPreset)
EndFunction

; A new body, as if met for the first time: BodyGen rolls, the rules get their say,
; other mods' keyed morphs stay.
Bool Function GenActor(Actor akActor) Global
	If !akActor || !Loaded()
		Return False
	EndIf
	Return Silhouette:DLL.RequestRegenerate(akActor.GetFormID())
EndFunction

; Takes Silhouette's body off: they are bare now. LooksMenu forgets an emptied body
; when a save is loaded, and BodyGen then gives them one again.
Bool Function ResetActorMorphs(Actor akActor) Global
	If !akActor || !Loaded()
		Return False
	EndIf
	Return Silhouette:DLL.RequestReset(akActor.GetFormID())
EndFunction

Bool Function ResetActorOBodyMorphs(Actor akActor) Global
	Return ResetActorMorphs(akActor)
EndFunction

; The body they have, again, with this build's values and their own variety.
Bool Function ReapplyActorMorphs(Actor akActor) Global
	If !akActor || !Loaded()
		Return False
	EndIf
	Return Silhouette:DLL.RequestReapply(akActor.GetFormID(), MarkerPreset(akActor))
EndFunction

Bool Function ReapplyActorOBodyMorphs(Actor akActor) Global
	Return ReapplyActorMorphs(akActor)
EndFunction

; ORefit on or off, and remembered: the same setting as MCM > Silhouette.
Function SetORefit(Bool abEnabled) Global
	If !Loaded()
		Return
	EndIf
	If MCM.IsInstalled()
		MCM.SetModSettingBool("Silhouette", "bORefit:General", abEnabled)
	EndIf
	Silhouette:DLL.SetORefit(abEnabled)
EndFunction

Bool Function IsORefitEnabled() Global
	Return Loaded() && Silhouette:DLL.IsORefitEnabled()
EndFunction

Bool Function IsORefitApplied(Actor akActor) Global
	Return akActor && Loaded() && Silhouette:DLL.IsORefitApplied(akActor.GetFormID())
EndFunction

; Nipple variety in the bodies Silhouette gives from now on. BodyGen's own rolls
; come from the generated files and always carry it.
Function SetNippleRand(Bool abEnabled) Global
	If !Loaded()
		Return
	EndIf
	If MCM.IsInstalled()
		MCM.SetModSettingBool("Silhouette", "bNippleRand:General", abEnabled)
	EndIf
	Silhouette:DLL.SetNippleRand(abEnabled)
EndFunction

; Genital shape variety (women) and ball size (men), as SetNippleRand. Never the shaft.
Function SetGenitalRand(Bool abEnabled) Global
	If !Loaded()
		Return
	EndIf
	If MCM.IsInstalled()
		MCM.SetModSettingBool("Silhouette", "bGenitalRand:General", abEnabled)
	EndIf
	Silhouette:DLL.SetGenitalRand(abEnabled)
EndFunction

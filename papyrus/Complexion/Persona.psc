Scriptname Complexion:Persona extends Quest
{An actor's Rapport persona, for Complexion's lewd marks (C-14). A script of its own on the bridge's quest: without
 Rapport only this one fails to load, and the bridge (which reaches it by CastAs) carries on without personas
 (shared note papyrus-optional-types-own-script).}

String Function Of(Actor akActor)
	If !akActor || Rapport:Core.ApiVersion() < 201
		Return ""
	EndIf
	Return Rapport:Core.PersonaOf(akActor.GetFormID())
EndFunction

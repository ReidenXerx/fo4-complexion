Scriptname Rapport:Core Native Hidden
{IMPORT ONLY - never compiled into the release. The two natives Complexion's persona script calls on Rapport.dll
 (fo4-rapport papyrus/Rapport/Core.psc, ApiVersion 201+).}

Int Function ApiVersion() Global Native
; "romantic", "reticent", "vulgar" or "mercantile"; "" without persona data.
String Function PersonaOf(Int aiFormID) Global Native

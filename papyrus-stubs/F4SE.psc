Scriptname F4SE Native Hidden
{IMPORT ONLY - never compiled into the release. The one F4SE native Silhouette
 calls, declared exactly as F4SE 0.6.23's own Scripts/Source/F4SE.psc declares it
 (the reconstructed base sources do not carry F4SE's scripts).}

; A plugin's version number, -1 if that plugin is not loaded.
Int Function GetPluginVersion(String name) Global Native

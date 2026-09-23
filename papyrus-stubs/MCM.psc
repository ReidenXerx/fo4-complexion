Scriptname MCM Native Hidden
{IMPORT ONLY - never compiled into the release. The natives Silhouette calls on Mod
 Configuration Menu (F4SE Menu Framework ships the real MCM.pex). Same declarations
 as fo4-chemistry's stub, which compiles and runs against the real one.}

Bool Function IsInstalled() Native Global
Int Function GetModSettingInt(String asModName, String asSetting) Native Global
Bool Function GetModSettingBool(String asModName, String asSetting) Native Global
String Function GetModSettingString(String asModName, String asSetting) Native Global
Function SetModSettingBool(String asModName, String asSettingName, Bool abValue) Native Global

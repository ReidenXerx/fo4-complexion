Scriptname Complexion:DLL Native Hidden
{Complexion.dll's natives (src/Papyrus.cpp). The bridge asks for orders and reports back; the plugin never calls
 into Papyrus. Protocol 1.}

Int Function ProtocolVersion() Native Global
String Function Version() Native Global
String Function Status() Native Global
Int Function Pending() Native Global

; MCM's switches: hand out overlays at all, and the adult and degrading pieces (C-7).
Function Configure(Bool abEnabled, Bool abAdult) Native Global

; A line for the player's screen, once a launch: Random Overlay Framework is loaded, or Complexion's files are
; missing. "" when there is nothing to say.
String Function Warning() Native Global

; MCM "Roll everyone again": every decision forgotten; whoever is seen next is decided anew.
Function ResetAll() Native Global
; MCM "Clear every overlay", after Overlays.ClearAll(): every decision kept, put back on people as they are seen.
Function Unapply() Native Global

; Main thread: reads who loaded since the last poll.
Function Pump() Native Global

; The next order (a whole look for one actor), 0 when none.
Int Function NextOrder() Native Global
Int Function OrderActor(Int aiOrder) Native Global
Bool Function OrderFemale(Int aiOrder) Native Global
Int Function OrderCount(Int aiOrder) Native Global
String Function OrderTemplate(Int aiOrder, Int aiIndex) Native Global
Int Function OrderPriority(Int aiOrder, Int aiIndex) Native Global
; Every entry landed (abLanded), or not even after a clean rebuild.
Function OrderDone(Int aiOrder, Bool abLanded) Native Global
; Not loaded, dead, a child, or busy in another mod's scene: tried again when they are next seen.
Function OrderGone(Int aiOrder) Native Global

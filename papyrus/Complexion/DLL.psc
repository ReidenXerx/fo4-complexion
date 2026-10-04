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
; A line for the corner of the screen, once: news, not a problem ("" when none).
String Function Notice() Native Global

; A line into Complexion.log.
Function Log(String asLine) Native Global
; What Complexion decided for an actor: "group: id, id", "" when nothing yet.
String Function Decided(Int aiActor) Native Global
; "Name (form id)" of an actor, for the log.
String Function NameOf(Int aiActor) Native Global

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
; The profile group the look was composed for ("raiders", "settlers", ...).
String Function OrderGroup(Int aiOrder) Native Global
; A faction on the reference the plugin cannot see (a raider's captive): compose the look again for that group.
Bool Function OrderRegroup(Int aiOrder, String asGroup) Native Global
; Their Rapport persona (C-14): a look not yet on them is composed again with it. True when it changed.
Bool Function OrderPersona(Int aiOrder, String asPersona) Native Global

; ---- C-19: the overlay window (ported from Silhouette's picker, S-79) ----
; The NPC under the crosshair, or aimed at within the last afRecentSeconds; 0 for none.
Int Function CrosshairActor(Float afRecentSeconds) Native Global
; The game's free camera framing someone; "" when there, "wait" while it comes on (ask CameraStep again), else why not.
String Function CameraFrame(Float afX, Float afY, Float afZ, Float afAngle, Float afHeight) Native Global
String Function CameraRestore() Native Global
String Function CameraStep() Native Global
; The free camera close to where template asKey sits on someone (the window, after it is put on); "none" when it has no
; spot or spreads wide (a mark over the whole body: frame all of them instead), else as CameraFrame.
String Function CameraFocus(Float afX, Float afY, Float afZ, Float afAngle, Float afHeight, String asKey) Native Global
; A session on one actor: what Complexion put on them is the draft. "" or why not.
String Function WindowBegin(Int aiActor, Bool abFemale) Native Global
Function WindowEnd() Native Global
; The build of the picture atlases (tools/paint/thumbs.py), "" without pictures.
String Function WindowBuild() Native Global
; One page: "<total>|<entry>|...", an entry "key<TAB>label<TAB>kind<TAB>on<TAB>atlas<TAB>cell".
String Function WindowPage(String asCategory, String asSearch, Int aiPage, Int aiPer) Native Global
; On the draft or off it: whether it is on now.
Bool Function WindowToggle(String asKey) Native Global
Int Function WindowCount() Native Global
Function WindowClear() Native Global
Function WindowRoll() Native Global
; An order the bridge puts on at once: the draft (Preview), or what they had (Restore). Ours are replaced even
; when it holds none.
Int Function WindowPreview() Native Global
Int Function WindowRestore() Native Global
; The draft is their look from now on, until rolled again.
Function WindowApply() Native Global

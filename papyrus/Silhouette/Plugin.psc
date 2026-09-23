Scriptname Silhouette:Plugin Native Hidden
{What Papyrus can ask of Silhouette.dll (decision S-18). Native functions have to
 live in a script flagged Native, which a Quest script cannot be, so they sit here
 and Silhouette:Bridge and Silhouette:API call them by name.

 The direction is one way: Papyrus calls in, the plugin never calls out (dispatching
 into the VM from a plugin crashed Rapport twice in DispatchMethodCallImpl). The
 plugin decides every body; the bridge does what it decides through LooksMenu's
 BodyGen, which has no other door.

 Actors travel as form ids (Int). Another mod should call Silhouette:API, not these:
 this surface follows the bridge and may change with it.}

; ---- the plugin ------------------------------------------------------------
Bool Function IsReady() Global Native         ; a catalog that matches the BodyGen files is loaded
String Function Status() Global Native        ; one line: catalog, events, queue, records
String Function Version() Global Native
Int Function Stamp() Global Native            ; the build's marker stamp, 0 without a catalog
String Function Build() Global Native
Function Configure(Bool abORefit, Bool abNipples, Bool abGenitals) Global Native
Int Function Pending() Global Native          ; orders waiting or in flight
Function Log(String asLine) Global Native     ; into Silhouette.log

; Main thread: turns what the event sinks saw (actors loading, dressing) into
; decisions. The bridge calls it once per poll.
Function Pump() Global Native

; ---- orders: exactly this, in this order ----------------------------------
; NextOrder -> (Regenerates) -> (Probes: NoteMarker) -> (ReadsAll: NoteLayer)
; -> OrderReadCount / OrderReadMorph / NoteRead -> Prepare -> (OrderClears)
; -> OrderWriteCount / OrderWriteMorph / OrderWriteValue -> (OrderUpdates) -> OrderDone.
; OrderReadCount comes AFTER the probe: which refit set applies can depend on the preset.
Int Function NextOrder() Global Native        ; 0: nothing to do
Int Function OrderActor(Int aiOrder) Global Native
Int Function OrderKind(Int aiOrder) Global Native   ; 1 probe, 2 body, 3 refit, 4 snapshot
Bool Function OrderFemale(Int aiOrder) Global Native
Bool Function OrderRegenerates(Int aiOrder) Global Native
Bool Function OrderProbes(Int aiOrder) Global Native
Bool Function OrderReadsAll(Int aiOrder) Global Native
Int Function OrderReadCount(Int aiOrder) Global Native
String Function OrderReadMorph(Int aiOrder, Int aiIndex) Global Native
Function NoteRead(Int aiOrder, Int aiIndex, Float afValue) Global Native
Function NoteLayer(Int aiOrder, String asMorph, Float afValue) Global Native
Function NoteMarker(Int aiOrder, String asMarker, Float afValue) Global Native
Bool Function Prepare(Int aiOrder) Global Native
Bool Function OrderClears(Int aiOrder) Global Native
Int Function OrderWriteCount(Int aiOrder) Global Native
String Function OrderWriteMorph(Int aiOrder, Int aiIndex) Global Native
Float Function OrderWriteValue(Int aiOrder, Int aiIndex) Global Native
Bool Function OrderUpdates(Int aiOrder) Global Native
Function OrderDone(Int aiOrder, Bool abOk) Global Native
Bool Function IsMarker(String asMorph) Global Native

; ---- events for the bridge to raise (S-24) ---------------------------------
Int Function NextEvent() Global Native        ; 0: none
Int Function EventKind(Int aiEvent) Global Native   ; 1 generated, 2 naked, 3 removing clothes, 4 ORefit changed
Int Function EventActor(Int aiEvent) Global Native
String Function EventPreset(Int aiEvent) Global Native
Bool Function EventFlag(Int aiEvent) Global Native

; ---- the NPC picker (S-22) --------------------------------------------------
Int Function CrosshairActor(Float afRecentSeconds) Global Native  ; main thread
String Function PickerStart(Int aiActor) Global Native            ; main thread
String Function PickerStep(Int aiStep) Global Native
String Function PickerKeep() Global Native
String Function PickerCancel() Global Native
Int Function PickerTarget() Global Native
Bool Function PickerReady() Global Native

; ---- what Silhouette:API offers ---------------------------------------------
Bool Function CanShape(Int aiActor) Global Native                 ; main thread
String Function NameOf(Int aiActor) Global Native                 ; main thread
String Function AssignedPreset(Int aiActor) Global Native
String Function PresetForMarker(String asMarker, Float afStamp) Global Native
Int Function PresetCount(Bool abFemale) Global Native
String Function PresetName(Bool abFemale, Int aiIndex) Global Native
Bool Function RequestPreset(Int aiActor, String asPreset, Int aiSource) Global Native  ; 3 picker, 4 another mod
Bool Function RequestRegenerate(Int aiActor) Global Native
Bool Function RequestReset(Int aiActor) Global Native
Bool Function RequestReapply(Int aiActor, String asMarkerPreset) Global Native
Bool Function IsORefitEnabled() Global Native
Bool Function IsORefitApplied(Int aiActor) Global Native
Function SetORefit(Bool abOn) Global Native
Function SetNippleRand(Bool abOn) Global Native
Function SetGenitalRand(Bool abOn) Global Native
String Function Describe(Int aiActor) Global Native
Int Function RefitOffEverywhere() Global Native                  ; main thread; ORefit must be off
String Function LastError() Global Native

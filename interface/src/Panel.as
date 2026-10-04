package {
	import flash.display.Loader;
	import flash.display.LoaderInfo;
	import flash.display.MovieClip;
	import flash.display.Shape;
	import flash.display.Sprite;
	import flash.events.Event;
	import flash.events.IOErrorEvent;
	import flash.events.KeyboardEvent;
	import flash.events.MouseEvent;
	import flash.net.URLRequest;
	import flash.text.TextField;
	import flash.text.TextFieldAutoSize;
	import flash.text.TextFieldType;
	import flash.text.TextFormat;
	import flash.utils.getTimer;

	// C-19: the overlay window's panel, ported from Silhouette's picker (S-79). Whose skin (an NPC the player aimed
	// at, or the player), the overlays by category -- each with its picture when it is one of Complexion's own --
	// a search, and which are on them. A click puts an overlay on or takes it off, live; Random rolls a look,
	// Clear takes every one of Complexion's off; Apply keeps it; Cancel, Esc or closing puts back what they had.
	// The bridge script does the work: it fills the panel through UI.Invoke ("root1.Menu_mc.<function>") and
	// hears every choice as an external event. The plugin pages and searches (the lists run to thousands), so the
	// panel asks for one page at a time.
	//
	// Pictures: tools/paint/thumbs.py draws Complexion's own templates into atlases per sex,
	// Data/Textures/Complexion/Thumbs<Sex>_<build>_<n>.dds, each cell a close-up of the mark; the plugin says
	// which atlas and cell. F4SE's MountImage gives an atlas to Scaleform as img://<name>; a card shows its cell
	// through a mask. Other packs' overlays have no picture (C-8: their art is not ours to render and ship).
	public dynamic class Panel extends MovieClip {
		private static const MENU:String = "ComplexionMenu";
		private static const X:Number = 760;
		private static const Y:Number = 10;
		private static const W:Number = 504;
		private static const COLS:int = 5;
		private static const ROWS:int = 3;
		private static const PER:int = COLS * ROWS;   // the bridge's WindowPer
		private static const CELL:Number = 128;       // one cell of an atlas, in pixels (square)
		private static const ATLAS_COLS:int = 32;     // 4096 / 128: one atlas a sex (tools/paint/thumbs.py)
		private static const PIC:Number = 0.66;       // cells drawn at this scale
		private static const CARD_W:Number = 94;
		private static const CARD_H:Number = 122;
		private static const GRID_Y:Number = Y + 218;
		private static const GAME_FONT:String = "$MAIN_Font";
		private static const CATS:Array = ["on", "all", "skin", "hair", "scars", "tattoos", "rough", "paint", "nails"];
		private static const CAT_NAMES:Array = ["On them", "All", "Skin", "Hair", "Scars", "Tattoos", "Rough", "Paint", "Nails"];

		private var _f4se:Object;
		private var _ready:Boolean = false;
		private var _cat:int = 0;
		private var _page:int = 0;
		private var _total:int = 0;
		private var _count:int = 0;            // how many of Complexion's are on them
		private var _items:Array = [];          // the page shown: {key, label, kind, on, atlas, cell}
		private var _focus:int = -1;            // the card the keys and the gamepad are on
		private var _canThem:Boolean = false;
		private var _mode:String = "";
		private var _sex:String = "";
		private var _build:String = "";
		private var _mounted:Object = {};       // atlas number -> img:// name, "" when it could not be mounted
		private var _busy:Boolean = false;      // a Them / Me switch is loading
		private var _closing:Boolean = false;
		private var _closingAt:int = 0;
		private var _readyAt:int = 0;
		private var _ask:int = 0;               // the number of the page question asked last: older answers drop
		private var _wheelAt:int = -1000;       // the last wheel notch heard, and the last one that turned a page
		private var _wheelTurnAt:int = -1000;
		private var _clickables:Array = [];
		private var _actAt:int = -1000;         // the last click acted on: the same click arrives more than one way
		private var _searchLeftAt:int = -1000;  // Esc / Enter that left the search: not also Cancel / Accept

		private var _title:TextField;
		private var _status:TextField;
		private var _countText:TextField;
		private var _pageText:TextField;
		private var _search:TextField;
		private var _cards:Array = [];
		private var _chips:Array = [];
		private var _them:Sprite;
		private var _me:Sprite;

		public function Panel() {
			var h:Number = GRID_Y - Y + ROWS * (CARD_H + 6) + 92;
			graphics.lineStyle(2, 0xFFFFFF, 0.6);
			graphics.beginFill(0x000000, 0.85);
			graphics.drawRect(X, Y, W, h);
			graphics.endFill();

			_title = Text(this, 26, X + 16, Y + 6, W - 32);
			_title.text = "Complexion";
			_status = Text(this, 15, X + 16, Y + 42, W - 32);
			_status.multiline = _status.wordWrap = true;
			_status.height = 40;

			_them = Button("Them", X + 16, Y + 86, 100, function ():void { Target("them"); });
			_me = Button("Me", X + 122, Y + 86, 100, function ():void { Target("me"); });
			_countText = Text(this, 15, X + 236, Y + 94, W - 252);

			for (var c:int = 0; c < CATS.length; c++) {
				var row:int = c < 5 ? 0 : 1;
				var col:int = c < 5 ? c : c - 5;
				_chips.push(Button(CAT_NAMES[c], X + 16 + col * 94, Y + 128 + row * 36, 88, Category(c), 14));
			}
			// The search: typed into, Enter searches.
			var box:Shape = new Shape();
			box.graphics.lineStyle(1, 0xFFFFFF, 0.6);
			box.graphics.beginFill(0xFFFFFF, 0.08);
			box.graphics.drawRect(X + 16 + 4 * 94 - 0, Y + 164, 88 + 0, 32);
			box.graphics.endFill();
			_search = new TextField();
			_search.defaultTextFormat = new TextFormat(GAME_FONT, 15, 0xFFFFFF);
			_search.embedFonts = true;
			_search.type = TextFieldType.INPUT;
			_search.selectable = true;
			_search.maxChars = 24;
			_search.x = X + 16 + 4 * 94 + 4;
			_search.y = Y + 170;
			_search.width = 80;
			_search.height = 24;
			var hint:TextField = Text(this, 12, X + 16 + 4 * 94 + 4, Y + 150, 84);
			hint.text = "Search:";
			addChild(box);
			addChild(_search);

			for (var i:int = 0; i < PER; i++) {
				var card:Sprite = new Sprite();
				card.x = X + 16 + (i % COLS) * (CARD_W + 2);
				card.y = GRID_Y + int(i / COLS) * (CARD_H + 6);
				card.buttonMode = true;
				card.mouseChildren = false;
				var pic:Sprite = new Sprite();
				pic.x = (CARD_W - CELL * PIC) / 2;
				pic.y = 3;
				var loader:Loader = new Loader();
				loader.scaleX = loader.scaleY = PIC;
				loader.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR, OnPictureError);
				pic.addChild(loader);
				var mask:Shape = new Shape();
				mask.graphics.beginFill(0xFFFFFF);
				mask.graphics.drawRect(0, 0, CELL * PIC, CELL * PIC);
				mask.graphics.endFill();
				pic.addChild(mask);
				pic.mask = mask;
				card.addChild(pic);
				var none:TextField = Text(card, 12, 4, 20, CARD_W - 8);  // an overlay with no picture: its kind
				none.multiline = none.wordWrap = true;
				none.height = 50;
				var label:TextField = Text(card, 11, 2, CELL * PIC + 6, CARD_W - 4);
				label.multiline = label.wordWrap = true;
				label.height = 30;
				var tick:TextField = Text(card, 16, CARD_W - 20, 2, 18);  // on them
				card.addEventListener(MouseEvent.CLICK, OnCardClick);
				_clickables.push({ s: card, f: CardAction(card) });
				card.addEventListener(MouseEvent.ROLL_OVER, OnCardOver);
				card.addEventListener(MouseEvent.ROLL_OUT, OnCardOut);
				addChild(card);
				_cards.push({ card: card, loader: loader, none: none, label: label, tick: tick, shown: "" });
			}
			var under:Number = GRID_Y + ROWS * (CARD_H + 6) + 4;
			Button("< Prev", X + 16, under, 90, function ():void { Turn(-1); }, 15);
			_pageText = Text(this, 15, X + 116, under + 6, 160);
			Button("Next >", X + W - 106, under, 90, function ():void { Turn(1); }, 15);
			var bottom:Number = under + 44;
			Button("Random", X + 16, bottom, 82, Roll, 15);
			Button("Clear", X + 102, bottom, 70, Clear, 15);
			Button("Whole body", X + 176, bottom, 96, Whole, 14);
			Button("Apply", X + W - 226, bottom, 100, Apply);
			Button("Cancel", X + W - 120, bottom, 104, Cancel);

			addEventListener(MouseEvent.MOUSE_WHEEL, function (e:MouseEvent):void { Wheel(e.delta > 0 ? -1 : 1); });
			addEventListener(Event.ADDED_TO_STAGE, OnStage);
			addEventListener(Event.ENTER_FRAME, OnFrame);
			addEventListener(Event.ENTER_FRAME, OnWatch);
			Paint();
		}

		// ---- called by the root and by the bridge (UI.Invoke "root1.Menu_mc.<name>")

		public function Connect(a_f4se:Object):void {
			_f4se = a_f4se;
			Ready();
		}

		// Whose skin: a name, whether an NPC was aimed at ("Them" works), "them" or "me", their sex and the build of
		// the picture atlases (an atlas drawn for another build is not mounted: no picture rather than the wrong one).
		public function SetTarget(a_name:String, a_canThem:Boolean, a_mode:String, a_female:Boolean, a_build:String):void {
			_title.text = a_name;
			_canThem = a_canThem;
			_mode = a_mode;
			_sex = a_female ? "Female" : "Male";
			_build = a_build;
			_mounted = {};
			_busy = false;
			alpha = 1.0;
			_page = 0;
			_focus = -1;
			Unload();
			Paint();
			Ask();
		}

		// The page asked for: "<total>|key<TAB>label<TAB>kind<TAB>on<TAB>atlas<TAB>cell|..." and the question's
		// number. An answer to a question no longer open is dropped. (The first window echoed the category and the
		// search back and compared them: Papyrus returned them in another case, every answer was dropped, and the
		// categories never changed the page -- the owner, 10-04.)
		public function SetPage(a_joined:String, a_ask:int):void {
			if (a_ask != _ask) {
				return;
			}
			var parts:Array = a_joined.split("|");
			_total = int(parts[0]);
			if (_total > 0 && _page >= Pages()) {
				_page = Pages() - 1;  // the list shrank under the page shown (Clear, a card taken off "On them")
				Ask();
				return;
			}
			_items = [];
			for (var i:int = 1; i < parts.length; i++) {
				var f:Array = String(parts[i]).split("\t");
				if (f.length >= 6) {
					_items.push({ key: f[0], label: f[1], kind: f[2], on: f[3] == "1", atlas: int(f[4]), cell: int(f[5]) });
				}
			}
			if (_focus >= _items.length) {
				_focus = _items.length - 1;
			}
			Redraw();
		}

		// A toggle's answer: whether a_key is on them now, and how many of Complexion's are.
		public function SetOn(a_key:String, a_on:Boolean, a_count:int):void {
			_count = a_count;
			for (var i:int = 0; i < _items.length; i++) {
				if (String(_items[i].key).toLowerCase() == a_key.toLowerCase()) {
					_items[i].on = a_on;
				}
			}
			Redraw();
			Ask();  // a page answered before the toggle may be on its way: this answer supersedes it
		}

		// The draft changed as a whole (Random, Clear): the page is asked for again.
		public function Refresh(a_count:int):void {
			_count = a_count;
			Ask();
		}

		// A new opening. F4SE keeps the movie between openings and unmounts the pictures when it closes, so each
		// opening starts from nothing and asks the bridge for its contents again (Silhouette's lesson).
		public function Begin():void {
			_closing = false;
			_busy = false;
			alpha = 1.0;
			_items = [];
			_total = 0;
			_count = 0;
			_page = 0;
			_focus = -1;
			_mounted = {};
			_ask++;
			_mode = "";
			_canThem = false;
			_sex = "";
			_build = "";
			_search.text = "";
			Unload();
			_title.text = "Complexion";
			_status.text = "";
			_ready = true;
			_readyAt = getTimer();
			Paint();
			Send("Complexion_WindowReady");
		}

		public function SetStatus(a_status:String):void {
			_status.text = a_status;
		}

		// The game's menu controls: the gamepad's (and keyboard's) Accept, Cancel and directions; bumpers turn pages,
		// triggers change the category. They only ADD to the mouse and the raw keys.
		public function ProcessUserEvent(a_control:String, a_pressed:Boolean):Boolean {
			// With the free camera on, the game turns the left mouse button into "WorldZUp" and never delivers the
			// click (Silhouette, measured): the panel clicks whatever is under the cursor itself.
			if (a_control == "WorldZUp") {
				if (a_pressed) {
					ClickAtCursor();
				}
				return true;
			}
			if (a_control == "WorldZDown") {
				return true;
			}
			// And the wheel arrives as "CameraZUp" / "CameraZDown", one per frame while it rolls (measured 10-04:
			// a dozen for one flick), never as a MOUSE_WHEEL: a flick turns one page.
			if (a_control == "CameraZUp" || a_control == "CameraZDown") {
				if (a_pressed) {
					Wheel(a_control == "CameraZUp" ? -1 : 1);
				}
				return true;
			}
			// Typing in the search: its keys are the search's (Esc and Enter leave it -- not Cancel, not Accept).
			if (stage && (stage.focus == _search || getTimer() - _searchLeftAt < 300)) {
				return a_control != "LShoulder" && a_control != "RShoulder" && a_control != "LTrigger" && a_control != "RTrigger"
					? true : ProcessPad(a_control, a_pressed);
			}
			return ProcessPad(a_control, a_pressed);
		}

		private function ProcessPad(a_control:String, a_pressed:Boolean):Boolean {
			var early:Boolean = !_ready || getTimer() - _readyAt < 400;
			if (early && (a_control == "Cancel" || a_control == "Accept")) {
				return true;  // the key that opened the window, not an answer
			}
			var ours:Boolean = true;
			switch (a_control) {
				case "Cancel":    if (a_pressed) { Cancel(); } break;
				case "Accept":    if (a_pressed) { ToggleFocus(); } break;
				case "XButton":   if (a_pressed) { Apply(); } break;
				case "YButton":   if (a_pressed) { Roll(); } break;
				case "Up":        if (a_pressed) { Move(-COLS); } break;
				case "Down":      if (a_pressed) { Move(COLS); } break;
				case "Left":      if (a_pressed) { Move(-1); } break;
				case "Right":     if (a_pressed) { Move(1); } break;
				case "LShoulder": if (a_pressed) { Turn(-1); } break;
				case "RShoulder": if (a_pressed) { Turn(1); } break;
				case "LTrigger":  if (a_pressed) { NextCategory(-1); } break;
				case "RTrigger":  if (a_pressed) { NextCategory(1); } break;
				default:          ours = false;
			}
			return ours;
		}

		// ---- inside

		private function OnStage(e:Event):void {
			stage.addEventListener(KeyboardEvent.KEY_DOWN, OnKey);
		}

		private function OnWatch(e:Event):void {
			if (_closing && getTimer() - _closingAt > 1500) {
				_closing = false;
				Note("the close asked for did not come: the window takes clicks again");
			}
		}

		// A click acts once: with the free camera on it can come as WorldZUp AND as a CLICK, in either order (the
		// first window's mouse-down guard trusted an order; microscope, 10-04).
		private function Once():Boolean {
			var now:int = getTimer();
			if (now - _actAt < 250) {
				return false;
			}
			_actAt = now;
			return true;
		}

		private function ClickAtCursor():void {
			if (!stage) {
				return;
			}
			var x:Number = stage.mouseX;
			var y:Number = stage.mouseY;
			if (_search.hitTestPoint(x, y, true)) {
				stage.focus = _search;
				return;
			}
			for (var i:int = 0; i < _clickables.length; i++) {
				var c:Object = _clickables[i];
				if (c.s.visible && c.s.alpha > 0.45 && c.s.hitTestPoint(x, y, true)) {
					if (Once()) {
						c.f();
					}
					return;
				}
			}
		}

		private function CardAction(a_card:Sprite):Function {
			return function ():void {
				var i:int = CardIndex(a_card);
				if (i >= 0) {
					_focus = i;
					Toggle(i);
				}
			};
		}

		private var _pictureErrors:int = 0;

		// Every card's picture forgotten: the next Redraw loads it again. F4SE unmounts the images when the window
		// closes, and a card that kept its loaded atlas showed nothing at the next opening (microscope, 10-04).
		private function Unload():void {
			for (var i:int = 0; i < _cards.length; i++) {
				_cards[i].shown = "";
				_cards[i].loader.name = "";
				_cards[i].loader.unload();
			}
		}

		private function OnPictureError(e:IOErrorEvent):void {
			if (_pictureErrors++ < 3) {
				Note("a picture did not load: " + e.text);
			}
			var info:LoaderInfo = e.target as LoaderInfo;
			if (info && info.loader) {
				info.loader.name = "";  // tried again when the card next changes
			}
		}

		private function Note(a_line:String):void {
			Send("Complexion_WindowNote", a_line);
		}

		private function OnFrame(e:Event):void {
			if (_ready) {
				removeEventListener(Event.ENTER_FRAME, OnFrame);
				return;
			}
			if (!_f4se && root && root["f4se"]) {
				_f4se = root["f4se"];
			}
			if (_f4se) {
				Ready();
			}
		}

		private function Ready():void {
			if (!_ready) {
				_ready = true;
				_readyAt = getTimer();
				Send("Complexion_WindowReady");
			}
		}

		// The img:// of atlas a_n of the target's sex, mounted the first time a card needs it; "" when it cannot
		// be. The path is relative to Data/Textures, as F4SE's own mods pass it; the Textures-rooted spelling too.
		private function Atlas(a_n:int):String {
			if (a_n < 0 || _sex == "" || _build == "") {
				return "";
			}
			var key:String = String(a_n);
			if (_mounted[key] != undefined) {
				return _mounted[key];
			}
			var name:String = "ComplexionThumbs" + _sex + _build + "_" + a_n;
			var file:String = "Complexion/Thumbs" + _sex + "_" + _build + "_" + a_n + ".dds";
			var got:String = "";
			if (_f4se && _f4se.MountImage != null) {
				if (_f4se.MountImage(MENU, file, name) || _f4se.MountImage(MENU, "Textures/" + file, name)) {
					got = "img://" + name;
				}
			}
			Note("atlas " + file + (got == "" ? " could not be mounted" : " mounted"));
			_mounted[key] = got;
			return got;
		}

		// Raw keys: Esc and Tab cancel, Enter applies (or searches, typing in the search), Space toggles the card
		// in focus, the arrows move it, Page Up / Down turn pages.
		private function OnKey(e:KeyboardEvent):void {
			if (stage && stage.focus == _search) {
				if (e.keyCode == 13) {
					stage.focus = null;
					_searchLeftAt = getTimer();
					_page = 0;
					_focus = -1;
					Ask();
				} else if (e.keyCode == 27) {
					stage.focus = null;
					_searchLeftAt = getTimer();
				}
				return;
			}
			switch (e.keyCode) {
				case 27:
				case 9:
					Cancel();
					break;
				case 13:
					Apply();
					break;
				case 32:
					ToggleFocus();
					break;
				case 37:
					Move(-1);
					break;
				case 39:
					Move(1);
					break;
				case 38:
					Move(-COLS);
					break;
				case 40:
					Move(COLS);
					break;
				case 33:
					Turn(-1);
					break;
				case 34:
					Turn(1);
					break;
			}
		}

		private function Apply():void {
			if (!_closing) {
				_closing = true;
				_closingAt = getTimer();
				Send("Complexion_WindowApply");
			}
		}

		private function Cancel():void {
			if (!_closing) {
				_closing = true;
				_closingAt = getTimer();
				Send("Complexion_WindowCancel");
			}
		}

		private function Roll():void {
			if (!_busy && !_closing) {
				Send("Complexion_WindowRoll");
			}
		}

		// The camera back to the whole of them (a pick moves it close to where the mark sits).
		private function Whole():void {
			if (!_busy && !_closing) {
				Send("Complexion_WindowWhole");
			}
		}

		// A wheel notch: a run of them close together turns one page, a long roll one more every 0.4 s.
		private function Wheel(a_by:int):void {
			var now:int = getTimer();
			var fresh:Boolean = now - _wheelAt > 150;
			_wheelAt = now;
			if (fresh || now - _wheelTurnAt > 400) {
				_wheelTurnAt = now;
				Turn(a_by);
			}
		}

		private function Clear():void {
			if (!_busy && !_closing) {
				Send("Complexion_WindowClear");
			}
		}

		private function Target(a_mode:String):void {
			if (_busy || _closing || a_mode == _mode || (a_mode == "them" && !_canThem)) {
				return;
			}
			_busy = true;
			_ask++;
			alpha = 0.6;
			Send("Complexion_WindowTarget", a_mode);
		}

		private function Category(a_index:int):Function {
			return function ():void {
				_cat = a_index;
				_page = 0;
				_focus = -1;
				Paint();
				Ask();
			};
		}

		private function NextCategory(a_by:int):void {
			_cat = (_cat + a_by + CATS.length) % CATS.length;
			_page = 0;
			_focus = -1;
			Paint();
			Ask();
		}

		private function Pages():int {
			return Math.max(1, Math.ceil(_total / PER));
		}

		private function Turn(a_by:int):void {
			var p:int = Math.max(0, Math.min(_page + a_by, Pages() - 1));
			if (p != _page) {
				_page = p;
				_focus = -1;
				Ask();
			}
		}

		// The page shown, asked for: the category, the search, the page.
		private function Ask():void {
			if (_mode == "" || _busy) {
				return;
			}
			_ask++;
			Send("Complexion_WindowPage", CATS[_cat], _search.text, _page, _ask);
		}

		private function Move(a_by:int):void {
			if (_items.length == 0) {
				return;
			}
			if (_focus < 0) {
				_focus = 0;
			} else {
				var at:int = _focus + a_by;
				if (at < 0 && _page > 0) {
					Turn(-1);
					return;
				}
				if (at >= _items.length && _page < Pages() - 1) {
					Turn(1);
					return;
				}
				_focus = Math.max(0, Math.min(at, _items.length - 1));
			}
			Redraw();
		}

		private function ToggleFocus():void {
			if (_focus >= 0 && _focus < _items.length) {
				Toggle(_focus);
			}
		}

		private function Toggle(a_i:int):void {
			if (_busy || _closing) {
				return;
			}
			Send("Complexion_WindowToggle", _items[a_i].key);
		}

		private function Paint():void {
			for (var c:int = 0; c < _chips.length; c++) {
				Mark(_chips[c], c == _cat, true);
			}
			Mark(_them, _mode == "them", _canThem);
			Mark(_me, _mode == "me", true);
			Redraw();
		}

		private function Redraw():void {
			for (var i:int = 0; i < _cards.length; i++) {
				var c:Object = _cards[i];
				var it:Object = i < _items.length ? _items[i] : null;
				c.card.visible = it != null;
				if (!it) {
					continue;
				}
				c.label.text = it.label;
				c.tick.text = it.on ? "+" : "";
				var url:String = it.cell >= 0 ? Atlas(it.atlas) : "";
				c.none.text = url == "" ? String(it.kind).replace("_", " ") : "";
				var shown:String = url == "" ? "" : url + "#" + it.cell;
				if (shown != c.shown) {
					c.shown = shown;
					c.loader.visible = url != "";
					if (url != "") {
						c.loader.x = -(it.cell % ATLAS_COLS) * CELL * PIC;
						c.loader.y = -int(it.cell / ATLAS_COLS) * CELL * PIC;
						if (c.loader.name != url) {
							c.loader.name = url;
							c.loader.load(new URLRequest(url));
						}
					}
				}
				Frame(c.card, it.on ? 2 : (i == _focus ? 1 : 0));
			}
			_countText.text = _count + " of Complexion's on them";
			_pageText.text = _total > 0 ? "page " + (_page + 1) + " of " + Pages() + " (" + _total + ")" : "nothing here";
		}

		private function CardIndex(a_card:Object):int {
			for (var i:int = 0; i < _cards.length; i++) {
				if (_cards[i].card == a_card) {
					return i < _items.length ? i : -1;
				}
			}
			return -1;
		}

		private function OnCardClick(e:MouseEvent):void {
			var i:int = CardIndex(e.currentTarget);
			if (i >= 0 && Once()) {
				_focus = i;
				Toggle(i);
			}
		}

		private function OnCardOver(e:MouseEvent):void {
			var i:int = CardIndex(e.currentTarget);
			if (i >= 0 && !_items[i].on) {
				Frame(Sprite(e.currentTarget), 1);
			}
		}

		private function OnCardOut(e:MouseEvent):void {
			Redraw();
		}

		// A card's frame: 0 none, 1 under the pointer or in focus, 2 on them.
		private function Frame(a_card:Sprite, a_level:int):void {
			a_card.graphics.clear();
			a_card.graphics.lineStyle(a_level == 2 ? 2 : 1, a_level == 2 ? 0x9CFF9C : 0xFFFFFF, a_level == 0 ? 0.15 : a_level == 1 ? 0.6 : 1.0);
			a_card.graphics.beginFill(a_level == 2 ? 0x9CFF9C : 0xFFFFFF, a_level == 2 ? 0.16 : 0.03);
			a_card.graphics.drawRect(0, 0, CARD_W, CARD_H);
			a_card.graphics.endFill();
		}

		private function Send(a_event:String, ... a_args):void {
			if (_f4se && _f4se.SendExternalEvent != null) {
				_f4se.SendExternalEvent.apply(_f4se, [a_event].concat(a_args));
			}
		}

		private function Text(a_parent:Sprite, a_size:int, a_x:Number, a_y:Number, a_w:Number):TextField {
			var t:TextField = new TextField();
			t.defaultTextFormat = new TextFormat(GAME_FONT, a_size, 0xFFFFFF);
			t.embedFonts = true;
			t.selectable = false;
			t.mouseEnabled = false;
			t.x = a_x;
			t.y = a_y;
			t.width = a_w;
			t.height = a_size + 10;
			a_parent.addChild(t);
			return t;
		}

		private function Button(a_label:String, a_x:Number, a_y:Number, a_w:Number, a_click:Function, a_size:int = 18):Sprite {
			var b:Sprite = new Sprite();
			b.x = a_x;
			b.y = a_y;
			b.buttonMode = true;
			b.mouseChildren = false;
			b.name = String(a_w);
			var t:TextField = new TextField();
			t.defaultTextFormat = new TextFormat(GAME_FONT, a_size, 0xFFFFFF);
			t.embedFonts = true;
			t.selectable = false;
			t.autoSize = TextFieldAutoSize.LEFT;
			t.text = a_label;
			t.x = Math.max(4, (a_w - t.width) / 2);
			t.y = a_size > 16 ? 5 : 6;
			b.addChild(t);
			b.addEventListener(MouseEvent.CLICK, function (e:MouseEvent):void {
				if (Once()) {
					a_click();
				}
			});
			_clickables.push({ s: b, f: a_click });
			addChild(b);
			Mark(b, false, true);
			return b;
		}

		private function Mark(a_button:Sprite, a_on:Boolean, a_enabled:Boolean):void {
			var w:Number = Number(a_button.name);
			a_button.graphics.clear();
			a_button.graphics.lineStyle(1, 0xFFFFFF, a_enabled ? 0.8 : 0.25);
			a_button.graphics.beginFill(0xFFFFFF, a_on ? 0.3 : 0.06);
			a_button.graphics.drawRect(0, 0, w, 32);
			a_button.graphics.endFill();
			a_button.alpha = a_enabled ? 1.0 : 0.4;
		}
	}
}

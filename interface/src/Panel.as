package {
	import flash.display.Loader;
	import flash.display.MovieClip;
	import flash.display.Shape;
	import flash.display.Sprite;
	import flash.events.Event;
	import flash.events.KeyboardEvent;
	import flash.events.MouseEvent;
	import flash.net.URLRequest;
	import flash.text.TextField;
	import flash.text.TextFieldAutoSize;
	import flash.text.TextFormat;
	import flash.utils.getTimer;

	// S-79: the picker window's panel. Whose body (an NPC the player aimed at, or the player), a grid of the
	// presets that fit them -- each with its picture, filtered -- and the one being tried on. A click tries it
	// on live; Apply keeps it; Cancel, Esc or closing puts back what they had. The bridge script does the work:
	// it fills the panel through UI.Invoke ("root1.Menu_mc.<function>") and hears every choice as an external
	// event.
	//
	// Pictures: tools/thumbnails.py draws every preset the pickers offer into one atlas a sex,
	// Data/Textures/Silhouette/Thumbs<Sex>.dds, cell k for the k-th preset of the list -- so an entry's place in
	// the list is its cell. F4SE's MountImage gives the atlas to Scaleform as img://<name>; each card shows its
	// cell through a mask. The player's own presets (kind y) are read in game and have no picture.
	public dynamic class Panel extends MovieClip {
		private static const MENU:String = "SilhouetteMenu";
		private static const X:Number = 780;
		private static const Y:Number = 10;
		private static const W:Number = 484;
		private static const COLS:int = 5;
		private static const ROWS:int = 3;
		private static const CELL_W:Number = 96;     // one cell of the atlas, in pixels
		private static const CELL_H:Number = 160;
		private static const ATLAS_COLS:int = 21;    // 2048 / 96
		private static const PIC:Number = 0.75;      // cells drawn at this scale
		private static const CARD_W:Number = 90;
		private static const CARD_H:Number = 154;
		private static const GRID_Y:Number = Y + 172;
		private static const GAME_FONT:String = "$MAIN_Font";
		private static const FILTERS:Array = ["All", "People", "Plain", "Rough", "Fine", "Yours"];

		private var _f4se:Object;
		private var _ready:Boolean = false;
		private var _names:Array = [];      // every preset, in the bridge's order: its index is what goes back
		private var _kinds:Array = [];      // y the player's own, p the random pool, o the rest, "" unknown
		private var _shown:Array = [];      // indices into _names that the filter lets through
		private var _filter:int = 0;
		private var _first:int = 0;         // the first shown entry on the grid, a multiple of COLS
		private var _selected:int = -1;     // index into _names of the preset tried on
		private var _canThem:Boolean = false;
		private var _mode:String = "";
		private var _atlas:String = "";     // img:// of the atlas of the target's sex, "" none mounted
		private var _busy:Boolean = false;  // a Them / Me switch is loading: clicks wait for its list
		private var _closing:Boolean = false;   // Apply or Cancel was sent: nothing more is
		private var _closingAt:int = 0;         // ... at this time: a close that never comes stops blocking
		private var _readyAt:int = 0;           // when the window was ready: the key that opened it is not a Cancel
		private var _userEvents:Boolean = false;  // the game sends its own directions: raw arrows are not needed

		private var _title:TextField;
		private var _status:TextField;
		private var _count:TextField;
		private var _cards:Array = [];
		private var _chips:Array = [];
		private var _them:Sprite;
		private var _me:Sprite;

		public function Panel() {
			var h:Number = GRID_Y - Y + ROWS * (CARD_H + 6) + 48;
			graphics.lineStyle(2, 0xFFFFFF, 0.6);
			graphics.beginFill(0x000000, 0.85);
			graphics.drawRect(X, Y, W, h);
			graphics.endFill();

			_title = Text(this, 26, X + 16, Y + 6, W - 32);
			_title.text = "Silhouette";
			_status = Text(this, 15, X + 16, Y + 42, W - 32);
			_status.multiline = _status.wordWrap = true;
			_status.height = 40;

			_them = Button("Them", X + 16, Y + 86, 110, function ():void { Target("them"); });
			_me = Button("Me", X + 134, Y + 86, 110, function ():void { Target("me"); });
			_count = Text(this, 15, X + 262, Y + 94, W - 278);

			for (var c:int = 0; c < FILTERS.length; c++) {
				_chips.push(Button(FILTERS[c], X + 16 + c * 76, Y + 128, 70, Filter(c), 15));
			}

			for (var i:int = 0; i < COLS * ROWS; i++) {
				var card:Sprite = new Sprite();
				card.x = X + 16 + (i % COLS) * (CARD_W + 2);
				card.y = GRID_Y + int(i / COLS) * (CARD_H + 6);
				card.buttonMode = true;
				card.mouseChildren = false;
				var pic:Sprite = new Sprite();
				pic.x = (CARD_W - CELL_W * PIC) / 2;
				pic.y = 2;
				var loader:Loader = new Loader();
				loader.scaleX = loader.scaleY = PIC;
				pic.addChild(loader);
				var mask:Shape = new Shape();
				mask.graphics.beginFill(0xFFFFFF);
				mask.graphics.drawRect(0, 0, CELL_W * PIC, CELL_H * PIC);
				mask.graphics.endFill();
				pic.addChild(mask);
				pic.mask = mask;
				card.addChild(pic);
				var none:TextField = Text(card, 13, 4, 40, CARD_W - 8);  // a preset with no picture
				none.multiline = none.wordWrap = true;
				none.height = 60;
				// Two lines: the tier and number that tell "Triggerman Plain F04" from F05 come last.
				var label:TextField = Text(card, 12, 2, CELL_H * PIC + 3, CARD_W - 4);
				label.multiline = label.wordWrap = true;
				label.height = 30;
				card.addEventListener(MouseEvent.CLICK, OnCardClick);
				card.addEventListener(MouseEvent.ROLL_OVER, OnCardOver);
				card.addEventListener(MouseEvent.ROLL_OUT, OnCardOut);
				addChild(card);
				_cards.push({ card: card, loader: loader, none: none, label: label, cell: -2 });
			}
			var bottom:Number = Y + h - 40;
			Button("Apply", X + 16, bottom, 140, Apply);
			Button("Cancel", X + W - 156, bottom, 140, Cancel);

			addEventListener(MouseEvent.MOUSE_WHEEL, function (e:MouseEvent):void { Scroll(e.delta > 0 ? -COLS : COLS); });
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

		// Whose body: a name to show, whether an NPC was aimed at ("Them" works), "them" or "me", their sex, which
		// picks the atlas, and the build of the list, which names it: an atlas drawn for another build is not
		// there to mount, and the cards show no picture rather than the wrong one.
		public function SetTarget(a_name:String, a_canThem:Boolean, a_mode:String, a_female:Boolean, a_build:String):void {
			_title.text = a_name;
			_canThem = a_canThem;
			_mode = a_mode;
			if (_mode == "me" && FILTERS[_filter] == "Yours") {
				_filter = 0;  // the player's own presets are offered for NPCs only
			}
			Mount(a_female ? "Female" : "Male", a_build);
			Paint();
		}

		// Every preset as "name" or "name<TAB>kind", joined by "|" (a Papyrus array holds only 128), and the
		// index of the one they wear or try on (-1 none).
		public function SetItems(a_joined:String, a_status:String, a_selected:int):void {
			_names = [];
			_kinds = [];
			var entries:Array = a_joined.length > 0 ? a_joined.split("|") : [];
			for (var i:int = 0; i < entries.length; i++) {
				var parts:Array = String(entries[i]).split("\t");
				_names.push(parts[0]);
				_kinds.push(parts.length > 1 ? parts[1] : "");
			}
			_selected = a_selected;
			_status.text = a_status;
			_busy = false;
			alpha = 1.0;
			Refilter();
		}

		public function SetStatus(a_status:String):void {
			_status.text = a_status;
		}

		public function SetSelected(a_selected:int):void {
			_selected = a_selected;
			Reveal();
			Redraw();
		}

		// The game's menu controls, when it sends them: the gamepad's (and keyboard's) Accept, Cancel and
		// directions, the bumpers turning pages and the triggers the filter. Acted on when pressed; the release
		// of a control acted on is ours too. They only ADD to the mouse and the raw keys below -- never switch
		// them off (0.3.1: a window whose input depended on them took none at all for a player).
		public function ProcessUserEvent(a_control:String, a_pressed:Boolean):Boolean {
			if (a_pressed) {
				Note("control " + a_control);
			}
			// A Cancel or Accept the window gets as it opens is the key that opened it (the hotkey, Esc leaving
			// MCM), not the player's answer: taken as one, it left the window waiting for a close that never came,
			// deaf to every click (0.3.0 and the owner's test of 0.3.1, 2026-10-01).
			var early:Boolean = !_ready || getTimer() - _readyAt < 400;
			if (early && (a_control == "Cancel" || a_control == "Accept")) {
				Note(a_control + " ignored: the window had only just opened");
				return true;
			}
			var ours:Boolean = true;
			switch (a_control) {
				case "Cancel":   if (a_pressed) { Cancel(); } break;
				case "Accept":   if (a_pressed) { Apply(); } break;
				case "Up":       if (a_pressed) { _userEvents = true; Step(-COLS); } break;
				case "Down":     if (a_pressed) { _userEvents = true; Step(COLS); } break;
				case "Left":     if (a_pressed) { _userEvents = true; Step(-1); } break;
				case "Right":    if (a_pressed) { _userEvents = true; Step(1); } break;
				case "LShoulder": if (a_pressed) { Scroll(-COLS * ROWS); } break;
				case "RShoulder": if (a_pressed) { Scroll(COLS * ROWS); } break;
				case "LTrigger": if (a_pressed) { NextFilter(-1); } break;
				case "RTrigger": if (a_pressed) { NextFilter(1); } break;
				default:         ours = false;
			}
			return ours;
		}

		// ---- inside

		private function OnStage(e:Event):void {
			stage.addEventListener(KeyboardEvent.KEY_DOWN, OnKey);
			stage.addEventListener(MouseEvent.MOUSE_DOWN, function (e:MouseEvent):void {
				Note("mouse down at " + int(e.stageX) + "," + int(e.stageY) + " on " + (e.target ? e.target.name : "nothing"));
			});
		}

		// Apply or Cancel was sent and the window is still open well after: that close is not coming, and the
		// window must not stay deaf waiting for it.
		private function OnWatch(e:Event):void {
			if (_closing && getTimer() - _closingAt > 1500) {
				_closing = false;
				Note("the close asked for did not come: the window takes clicks again");
			}
		}

		// What the window received, into Silhouette.log through the bridge: the evidence for an input problem.
		private function Note(a_line:String):void {
			Send("Silhouette_WindowNote", a_line);
		}

		// An F4SE older than 0.6.8 never calls onF4SEObjCreated: the object is on the root by the first frames.
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
				Send("Silhouette_WindowReady");
			}
		}

		// The atlas of a sex, for img://. The path is relative to Data/Textures, as F4SE's own mods pass it; the
		// Textures-rooted spelling is tried too. Unmounted by F4SE when the menu closes.
		private function Mount(a_sex:String, a_build:String):void {
			var name:String = "SilhouetteThumbs" + a_sex + a_build;
			if (_atlas == "img://" + name) {
				return;
			}
			_atlas = "";
			if (_f4se && _f4se.MountImage != null && a_build.length > 0) {
				var file:String = "Silhouette/Thumbs" + a_sex + "_" + a_build + ".dds";
				if (_f4se.MountImage(MENU, file, name) || _f4se.MountImage(MENU, "Textures/" + file, name)) {
					_atlas = "img://" + name;
				}
			}
			for (var i:int = 0; i < _cards.length; i++) {
				_cards[i].cell = -2;  // every card loads again
			}
		}

		// Raw keys: always Esc, Tab and Enter (Apply and Cancel go out once whichever way they come); the arrows
		// only while the game sends no directions of its own, so a step is not taken twice.
		private function OnKey(e:KeyboardEvent):void {
			if (_userEvents && e.keyCode >= 37 && e.keyCode <= 40) {
				return;
			}
			switch (e.keyCode) {
				case 27:  // Esc
				case 9:   // Tab
					Cancel();
					break;
				case 13:  // Enter
					Apply();
					break;
				case 37:  // Left, Right, Up, Down: the preset there goes on
					Step(-1);
					break;
				case 39:
					Step(1);
					break;
				case 38:
					Step(-COLS);
					break;
				case 40:
					Step(COLS);
					break;
				case 33:  // Page Up / Down
					Scroll(-COLS * ROWS);
					break;
				case 34:
					Scroll(COLS * ROWS);
					break;
			}
		}

		// Apply and Cancel are sent once: a key and a click, or a press seen twice, must not keep twice.
		private function Apply():void {
			if (!_closing) {
				_closing = true;
				_closingAt = getTimer();
				Send("Silhouette_WindowApply");
			}
		}

		private function Cancel():void {
			if (!_closing) {
				_closing = true;
				_closingAt = getTimer();
				Send("Silhouette_WindowCancel");
			}
		}

		private function Target(a_mode:String):void {
			if (_busy || _closing || a_mode == _mode || (a_mode == "them" && !_canThem)) {
				return;
			}
			_busy = true;  // until the other one's list arrives: a click now would name a card of this list
			alpha = 0.6;
			Send("Silhouette_WindowTarget", a_mode);
		}

		private function FilterUsable(a_index:int):Boolean {
			return !(FILTERS[a_index] == "Yours" && _mode == "me");
		}

		private function Filter(a_index:int):Function {
			return function ():void {
				if (FilterUsable(a_index)) {
					_filter = a_index;
					Refilter();
				}
			};
		}

		private function NextFilter(a_by:int):void {
			var f:int = _filter;
			do {
				f = (f + a_by + FILTERS.length) % FILTERS.length;
			} while (!FilterUsable(f));
			_filter = f;
			Refilter();
		}

		private function Passes(a_i:int):Boolean {
			var name:String = _names[a_i];
			var kind:String = _kinds[a_i];
			var tier:String = "";
			var m:Array = name.match(/(Plain|Rough|Fine) [FM]\d+$/);
			if (m) {
				tier = m[1];
			}
			switch (FILTERS[_filter]) {
				case "People": return tier == "" && kind != "y";
				case "Plain":  return tier == "Plain";
				case "Rough":  return tier == "Rough";
				case "Fine":   return tier == "Fine";
				case "Yours":  return kind == "y";
			}
			return true;
		}

		private function Refilter():void {
			_shown = [];
			for (var i:int = 0; i < _names.length; i++) {
				if (Passes(i)) {
					_shown.push(i);
				}
			}
			_first = 0;
			Reveal();
			Paint();
		}

		// Scrolls the tried-on preset into view when the filter shows it.
		private function Reveal():void {
			var at:int = _shown.indexOf(_selected);
			if (at >= 0 && (at < _first || at >= _first + COLS * ROWS)) {
				_first = Clamp(int(at / COLS) * COLS - COLS);
			}
		}

		private function Clamp(a_first:int):int {
			var last:int = Math.max(0, Math.ceil(_shown.length / COLS) - ROWS) * COLS;
			return Math.max(0, Math.min(a_first, last));
		}

		private function Step(a_by:int):void {
			if (_shown.length == 0) {
				return;
			}
			var was:int = _shown.indexOf(_selected);
			var at:int = was < 0 ? (a_by > 0 ? 0 : _shown.length - 1) : Math.max(0, Math.min(was + a_by, _shown.length - 1));
			if (at != was) {
				Pick(_shown[at]);  // at an edge the same preset is not put on again
			}
		}

		private function Pick(a_i:int):void {
			if (_busy || _closing) {
				Note("pick of " + _names[a_i] + " ignored: " + (_busy ? "a Them/Me switch is loading" : "the window is closing"));
				return;
			}
			_selected = a_i;
			Reveal();
			Redraw();
			Send("Silhouette_WindowPick", _names[a_i], a_i);
		}

		private function Scroll(a_by:int):void {
			_first = Clamp(_first + a_by);
			Redraw();
		}

		private function Paint():void {
			for (var c:int = 0; c < _chips.length; c++) {
				Mark(_chips[c], c == _filter, FilterUsable(c));
			}
			Mark(_them, _mode == "them", _canThem);
			Mark(_me, _mode == "me", true);
			Redraw();
		}

		private function Redraw():void {
			for (var i:int = 0; i < _cards.length; i++) {
				var c:Object = _cards[i];
				var n:int = _first + i;
				var index:int = n < _shown.length ? _shown[n] : -1;
				c.card.visible = index >= 0;
				if (index < 0) {
					continue;
				}
				var yours:Boolean = _kinds[index] == "y";
				c.label.text = _names[index];
				c.none.text = yours ? "your preset" : "";
				var cell:int = yours || _atlas == "" ? -1 : index;
				if (cell != c.cell) {
					c.cell = cell;
					c.loader.visible = cell >= 0;
					if (cell >= 0) {
						c.loader.x = -(cell % ATLAS_COLS) * CELL_W * PIC;
						c.loader.y = -int(cell / ATLAS_COLS) * CELL_H * PIC;
						if (c.loader.name != _atlas) {
							c.loader.name = _atlas;
							c.loader.load(new URLRequest(_atlas));
						}
					}
				}
				Frame(c.card, index == _selected ? 2 : 0);
			}
			_count.text = _shown.length + " of " + _names.length + " presets";
		}

		private function CardIndex(a_card:Object):int {
			for (var i:int = 0; i < _cards.length; i++) {
				if (_cards[i].card == a_card) {
					var n:int = _first + i;
					return n < _shown.length ? _shown[n] : -1;
				}
			}
			return -1;
		}

		private function OnCardClick(e:MouseEvent):void {
			var index:int = CardIndex(e.currentTarget);
			Note("card click: " + (index >= 0 ? _names[index] : "an empty card"));
			if (index >= 0) {
				Pick(index);
			}
		}

		private function OnCardOver(e:MouseEvent):void {
			if (CardIndex(e.currentTarget) != _selected) {
				Frame(Sprite(e.currentTarget), 1);
			}
		}

		private function OnCardOut(e:MouseEvent):void {
			Redraw();
		}

		// A card's frame: 0 none, 1 under the pointer, 2 the one tried on.
		private function Frame(a_card:Sprite, a_level:int):void {
			a_card.graphics.clear();
			a_card.graphics.lineStyle(a_level == 2 ? 2 : 1, 0xFFFFFF, a_level == 0 ? 0.15 : a_level == 1 ? 0.5 : 1.0);
			a_card.graphics.beginFill(0xFFFFFF, a_level == 2 ? 0.18 : 0.03);
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
			b.addEventListener(MouseEvent.CLICK, function (e:MouseEvent):void { a_click(); });
			addChild(b);
			Mark(b, false, true);
			return b;
		}

		// A button's frame: filled when it is the one chosen, faint when it cannot be used.
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

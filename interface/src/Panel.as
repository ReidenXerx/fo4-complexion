package {
	import flash.display.MovieClip;
	import flash.display.Sprite;
	import flash.events.Event;
	import flash.events.KeyboardEvent;
	import flash.events.MouseEvent;
	import flash.text.TextField;
	import flash.text.TextFieldAutoSize;
	import flash.text.TextFormat;

	// S-79: the picker window's panel. Whose body (an NPC the player aimed at, or the player), which presets
	// fit them, filtered, and the one being tried on. A click tries it on live; Apply keeps it; Cancel, Esc or
	// closing puts back what they had. The bridge script does the work: it fills the panel through UI.Invoke
	// ("root1.Menu_mc.<function>") and hears every choice as an external event.
	public dynamic class Panel extends MovieClip {
		private static const X:Number = 790;
		private static const Y:Number = 36;
		private static const W:Number = 470;
		private static const ROWS:int = 13;
		private static const ROW_H:Number = 30;
		private static const LIST_Y:Number = Y + 196;
		private static const GAME_FONT:String = "$MAIN_Font";
		private static const FILTERS:Array = ["All", "People", "Plain", "Rough", "Fine", "Yours"];

		private var _f4se:Object;
		private var _ready:Boolean = false;
		private var _names:Array = [];      // every preset, in the bridge's order: its index is what goes back
		private var _kinds:Array = [];      // y the player's own, p the random pool, o the rest, "" unknown
		private var _shown:Array = [];      // indices into _names that the filter lets through
		private var _filter:int = 0;
		private var _first:int = 0;
		private var _selected:int = -1;     // index into _names of the preset tried on
		private var _canThem:Boolean = false;
		private var _mode:String = "";

		private var _title:TextField;
		private var _status:TextField;
		private var _count:TextField;
		private var _rows:Array = [];
		private var _chips:Array = [];
		private var _them:Sprite;
		private var _me:Sprite;

		public function Panel() {
			var h:Number = LIST_Y - Y + ROWS * ROW_H + 72;
			graphics.lineStyle(2, 0xFFFFFF, 0.6);
			graphics.beginFill(0x000000, 0.82);
			graphics.drawRect(X, Y, W, h);
			graphics.endFill();

			_title = Text(26, X + 16, Y + 10, W - 32);
			_title.text = "Silhouette";
			_status = Text(15, X + 16, Y + 48, W - 32);
			_status.text = "";

			_them = Button("Them", X + 16, Y + 80, 110, function ():void { Target("them"); });
			_me = Button("Me", X + 134, Y + 80, 110, function ():void { Target("me"); });
			_count = Text(15, X + 260, Y + 88, W - 276);

			for (var c:int = 0; c < FILTERS.length; c++) {
				_chips.push(Button(FILTERS[c], X + 16 + c * 73, Y + 132, 68, Filter(c), 15));
			}
			graphics.lineStyle(1, 0xFFFFFF, 0.3);
			graphics.moveTo(X + 12, LIST_Y - 10);
			graphics.lineTo(X + W - 12, LIST_Y - 10);

			for (var i:int = 0; i < ROWS; i++) {
				var row:Sprite = new Sprite();
				row.x = X + 8;
				row.y = LIST_Y + i * ROW_H;
				row.buttonMode = true;
				var label:TextField = Text(18, 10, 2, W - 36);
				label.mouseEnabled = false;
				row.addChild(label);
				row.addEventListener(MouseEvent.CLICK, OnRowClick);
				row.addEventListener(MouseEvent.ROLL_OVER, OnRowOver);
				row.addEventListener(MouseEvent.ROLL_OUT, OnRowOut);
				addChild(row);
				_rows.push(row);
			}
			var bottom:Number = Y + h - 50;
			Button("Apply", X + 16, bottom, 140, function ():void { Send("Silhouette_WindowApply"); });
			Button("Cancel", X + W - 156, bottom, 140, function ():void { Send("Silhouette_WindowCancel"); });

			addEventListener(MouseEvent.MOUSE_WHEEL, function (e:MouseEvent):void { Scroll(e.delta > 0 ? -3 : 3); });
			addEventListener(Event.ADDED_TO_STAGE, OnStage);
			addEventListener(Event.ENTER_FRAME, OnFrame);
			Paint();
		}

		// ---- called by the root and by the bridge (UI.Invoke "root1.Menu_mc.<name>")

		public function Connect(a_f4se:Object):void {
			_f4se = a_f4se;
			Ready();
		}

		// Whose body: a name to show, whether an NPC was aimed at ("Them" works), and "them" or "me".
		public function SetTarget(a_name:String, a_canThem:Boolean, a_mode:String):void {
			_title.text = a_name;
			_canThem = a_canThem;
			_mode = a_mode;
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
			Refilter(true);
		}

		public function SetStatus(a_status:String):void {
			_status.text = a_status;
		}

		public function SetSelected(a_selected:int):void {
			_selected = a_selected;
			Reveal();
			Redraw();
		}

		// What vanilla menus receive for the game's own controls: a gamepad's B is "Cancel", A "Accept".
		public function ProcessUserEvent(a_control:String, a_pressed:Boolean):Boolean {
			if (a_pressed) {
				return false;
			}
			if (a_control == "Cancel") {
				Send("Silhouette_WindowCancel");
				return true;
			}
			if (a_control == "Accept") {
				Send("Silhouette_WindowApply");
				return true;
			}
			return false;
		}

		// ---- inside

		private function OnStage(e:Event):void {
			stage.addEventListener(KeyboardEvent.KEY_DOWN, OnKey);
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
				Send("Silhouette_WindowReady");
			}
		}

		private function OnKey(e:KeyboardEvent):void {
			switch (e.keyCode) {
				case 27:  // Esc
				case 9:   // Tab
					Send("Silhouette_WindowCancel");
					break;
				case 13:  // Enter
					Send("Silhouette_WindowApply");
					break;
				case 38:  // Up: the preset above goes on
					Step(-1);
					break;
				case 40:
					Step(1);
					break;
				case 33:  // Page Up / Down
					Scroll(-ROWS);
					break;
				case 34:
					Scroll(ROWS);
					break;
			}
		}

		private function Target(a_mode:String):void {
			if (a_mode == _mode || (a_mode == "them" && !_canThem)) {
				return;
			}
			Send("Silhouette_WindowTarget", a_mode);
		}

		private function Filter(a_index:int):Function {
			return function ():void {
				_filter = a_index;
				Refilter(true);
			};
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

		private function Refilter(a_reveal:Boolean):void {
			_shown = [];
			for (var i:int = 0; i < _names.length; i++) {
				if (Passes(i)) {
					_shown.push(i);
				}
			}
			_first = 0;
			if (a_reveal) {
				Reveal();
			}
			Paint();
		}

		// Scrolls the tried-on preset into view when the filter shows it.
		private function Reveal():void {
			var at:int = _shown.indexOf(_selected);
			if (at >= 0 && (at < _first || at >= _first + ROWS)) {
				_first = Math.max(0, Math.min(at - int(ROWS / 2), _shown.length - ROWS));
			}
		}

		private function Step(a_by:int):void {
			if (_shown.length == 0) {
				return;
			}
			var at:int = _shown.indexOf(_selected);
			at = at < 0 ? (a_by > 0 ? 0 : _shown.length - 1) : Math.max(0, Math.min(at + a_by, _shown.length - 1));
			Pick(_shown[at]);
		}

		private function Pick(a_i:int):void {
			_selected = a_i;
			Reveal();
			Redraw();
			Send("Silhouette_WindowPick", _names[a_i], a_i);
		}

		private function Scroll(a_by:int):void {
			_first = Math.max(0, Math.min(_first + a_by, Math.max(0, _shown.length - ROWS)));
			Redraw();
		}

		private function Paint():void {
			for (var c:int = 0; c < _chips.length; c++) {
				Mark(_chips[c], c == _filter, true);
			}
			Mark(_them, _mode == "them", _canThem);
			Mark(_me, _mode == "me", true);
			Redraw();
		}

		private function Redraw():void {
			for (var i:int = 0; i < ROWS; i++) {
				var row:Sprite = Sprite(_rows[i]);
				var label:TextField = TextField(row.getChildAt(0));
				var n:int = _first + i;
				var index:int = n < _shown.length ? _shown[n] : -1;
				label.text = index >= 0 ? _names[index] + (_kinds[index] == "y" ? "  (yours)" : "") : "";
				Shade(row, index >= 0 && index == _selected ? 0.3 : 0.0);
			}
			_count.text = _shown.length + " of " + _names.length + " presets";
		}

		private function OnRowClick(e:MouseEvent):void {
			var n:int = _first + _rows.indexOf(e.currentTarget);
			if (n < _shown.length) {
				Pick(_shown[n]);
			}
		}

		private function OnRowOver(e:MouseEvent):void {
			var row:Sprite = Sprite(e.currentTarget);
			var n:int = _first + _rows.indexOf(row);
			if (n < _shown.length && _shown[n] != _selected) {
				Shade(row, 0.12);
			}
		}

		private function OnRowOut(e:MouseEvent):void {
			Redraw();
		}

		private function Shade(a_row:Sprite, a_alpha:Number):void {
			a_row.graphics.clear();
			if (a_alpha > 0) {
				a_row.graphics.beginFill(0xFFFFFF, a_alpha);
				a_row.graphics.drawRect(0, 0, W - 16, ROW_H - 2);
				a_row.graphics.endFill();
			}
		}

		private function Send(a_event:String, ... a_args):void {
			if (_f4se && _f4se.SendExternalEvent != null) {
				_f4se.SendExternalEvent.apply(_f4se, [a_event].concat(a_args));
			}
		}

		private function Text(a_size:int, a_x:Number, a_y:Number, a_w:Number):TextField {
			var t:TextField = new TextField();
			t.defaultTextFormat = new TextFormat(GAME_FONT, a_size, 0xFFFFFF);
			t.embedFonts = true;
			t.selectable = false;
			t.x = a_x;
			t.y = a_y;
			t.width = a_w;
			t.height = a_size + 10;
			addChild(t);
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

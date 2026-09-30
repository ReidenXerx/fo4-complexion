package {
	import flash.display.MovieClip;
	import flash.display.Sprite;
	import flash.events.Event;
	import flash.events.KeyboardEvent;
	import flash.events.MouseEvent;
	import flash.text.TextField;
	import flash.text.TextFieldAutoSize;
	import flash.text.TextFormat;

	// S-79 spike: the picker window's panel. What it proves in game before the real window is built on it --
	// the menu opens through F4SE on both game versions, the game's own font renders from code (line A; line B
	// is a device font for comparison), and a click reaches Papyrus. The bridge fills it with SetItems once
	// the panel says it is ready; every click goes back as an external event.
	public dynamic class Panel extends MovieClip {
		private static const X:Number = 820;
		private static const Y:Number = 60;
		private static const W:Number = 420;
		private static const ROWS:int = 16;
		private static const ROW_H:Number = 28;
		private static const GAME_FONT:String = "$MAIN_Font";

		private var _f4se:Object;
		private var _ready:Boolean = false;
		private var _items:Array = [];
		private var _first:int = 0;
		private var _title:TextField;
		private var _status:TextField;
		private var _rows:Array = [];

		public function Panel() {
			var h:Number = 150 + ROWS * ROW_H + 60;
			graphics.lineStyle(2, 0xFFFFFF, 0.6);
			graphics.beginFill(0x000000, 0.8);
			graphics.drawRect(X, Y, W, h);
			graphics.endFill();

			_title = Text(GAME_FONT, true, 28, X + 16, Y + 10, W - 32);
			_title.text = "Silhouette";
			Text(GAME_FONT, true, 16, X + 16, Y + 52, W - 32).text = "A (game font): Aa Bb Cc 0123";
			Text("_sans", false, 16, X + 16, Y + 76, W - 32).text = "B (device font): Aa Bb Cc 0123";
			_status = Text(GAME_FONT, true, 16, X + 16, Y + 104, W - 32);
			_status.text = "waiting for the bridge...";

			for (var i:int = 0; i < ROWS; i++) {
				var row:Sprite = new Sprite();
				row.y = Y + 140 + i * ROW_H;
				row.x = X + 8;
				row.buttonMode = true;
				var label:TextField = Text(GAME_FONT, true, 18, 8, 2, W - 32);
				label.mouseEnabled = false;
				row.addChild(label);
				row.addEventListener(MouseEvent.CLICK, OnRowClick);
				row.addEventListener(MouseEvent.ROLL_OVER, OnRowOver);
				row.addEventListener(MouseEvent.ROLL_OUT, OnRowOut);
				addChild(row);
				_rows.push(row);
			}
			var close:Sprite = Button("Close", X + W - 116, Y + h - 46);
			close.addEventListener(MouseEvent.CLICK, function (e:MouseEvent):void { Send("Silhouette_WindowClose"); });
			var up:Sprite = Button("Up", X + 16, Y + h - 46);
			up.addEventListener(MouseEvent.CLICK, function (e:MouseEvent):void { Scroll(-ROWS); });
			var down:Sprite = Button("Down", X + 124, Y + h - 46);
			down.addEventListener(MouseEvent.CLICK, function (e:MouseEvent):void { Scroll(ROWS); });

			addEventListener(MouseEvent.MOUSE_WHEEL, function (e:MouseEvent):void { Scroll(e.delta > 0 ? -3 : 3); });
			addEventListener(Event.ADDED_TO_STAGE, OnStage);
			addEventListener(Event.ENTER_FRAME, OnFrame);
		}

		// ---- called by the root and by the bridge (UI.Invoke "root1.Menu_mc.<name>")

		public function Connect(a_f4se:Object):void {
			_f4se = a_f4se;
			Ready();
		}

		public function SetTitle(a_title:String):void {
			_title.text = a_title;
		}

		// Every preset name, joined by "|": a Papyrus array holds at most 128, a string any number.
		public function SetItems(a_joined:String, a_status:String):void {
			_items = a_joined.length > 0 ? a_joined.split("|") : [];
			_first = 0;
			_status.text = a_status;
			Redraw();
		}

		// What vanilla menus receive for the game's own controls: a gamepad's B is "Cancel".
		public function ProcessUserEvent(a_control:String, a_pressed:Boolean):Boolean {
			if (!a_pressed && a_control == "Cancel") {
				Send("Silhouette_WindowClose");
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
			if (_ready) {
				return;
			}
			_ready = true;
			Send("Silhouette_WindowReady");
		}

		private function OnKey(e:KeyboardEvent):void {
			if (e.keyCode == 27 || e.keyCode == 9) {  // Esc, Tab
				Send("Silhouette_WindowClose");
			} else if (e.keyCode == 38) {
				Scroll(-1);
			} else if (e.keyCode == 40) {
				Scroll(1);
			}
		}

		private function Scroll(a_by:int):void {
			_first = Math.max(0, Math.min(_first + a_by, Math.max(0, _items.length - ROWS)));
			Redraw();
		}

		private function Redraw():void {
			for (var i:int = 0; i < ROWS; i++) {
				var label:TextField = TextField(Sprite(_rows[i]).getChildAt(0));
				var n:int = _first + i;
				label.text = n < _items.length ? _items[n] : "";
			}
		}

		private function OnRowClick(e:MouseEvent):void {
			var n:int = _first + _rows.indexOf(e.currentTarget);
			if (n < _items.length) {
				_status.text = "picked: " + _items[n];
				Send("Silhouette_WindowPick", _items[n]);
			}
		}

		private function OnRowOver(e:MouseEvent):void {
			var row:Sprite = Sprite(e.currentTarget);
			row.graphics.clear();
			row.graphics.beginFill(0xFFFFFF, 0.15);
			row.graphics.drawRect(0, 0, W - 16, ROW_H - 2);
			row.graphics.endFill();
		}

		private function OnRowOut(e:MouseEvent):void {
			Sprite(e.currentTarget).graphics.clear();
		}

		private function Send(a_event:String, ... a_args):void {
			if (_f4se && _f4se.SendExternalEvent != null) {
				_f4se.SendExternalEvent.apply(_f4se, [a_event].concat(a_args));
			}
		}

		private function Text(a_font:String, a_embed:Boolean, a_size:int, a_x:Number, a_y:Number, a_w:Number):TextField {
			var t:TextField = new TextField();
			t.defaultTextFormat = new TextFormat(a_font, a_size, 0xFFFFFF);
			t.embedFonts = a_embed;
			t.selectable = false;
			t.x = a_x;
			t.y = a_y;
			t.width = a_w;
			t.height = a_size + 10;
			addChild(t);
			return t;
		}

		private function Button(a_label:String, a_x:Number, a_y:Number):Sprite {
			var b:Sprite = new Sprite();
			b.x = a_x;
			b.y = a_y;
			b.buttonMode = true;
			b.graphics.lineStyle(1, 0xFFFFFF, 0.8);
			b.graphics.beginFill(0x333333, 0.9);
			b.graphics.drawRect(0, 0, 100, 32);
			b.graphics.endFill();
			var t:TextField = new TextField();
			t.defaultTextFormat = new TextFormat(GAME_FONT, 18, 0xFFFFFF);
			t.embedFonts = true;
			t.selectable = false;
			t.mouseEnabled = false;
			t.autoSize = TextFieldAutoSize.LEFT;
			t.text = a_label;
			t.x = 10;
			t.y = 4;
			b.addChild(t);
			addChild(b);
			return b;
		}
	}
}

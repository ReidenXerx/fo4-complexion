package {
	import flash.display.MovieClip;

	// S-79: the picker window's document class. F4SE opens Interface/SilhouetteMenu.swf as a custom menu
	// (UI.RegisterCustomMenu, root path "root1.Menu_mc") and hangs its f4se object on this root -- which is
	// why the class is dynamic. Menu_mc is the panel the bridge script talks to through UI.Invoke.
	[SWF(width="1280", height="720", frameRate="30")]
	public dynamic class SilhouetteMenu extends MovieClip {
		public var Menu_mc:Panel;

		public function SilhouetteMenu() {
			Menu_mc = new Panel();
			Menu_mc.name = "Menu_mc";
			addChild(Menu_mc);
		}

		// F4SE 0.6.8 and later call this once the f4se object exists: the panel can talk from then on.
		public function onF4SEObjCreated(a_f4se:Object):void {
			Menu_mc.Connect(a_f4se);
		}
	}
}

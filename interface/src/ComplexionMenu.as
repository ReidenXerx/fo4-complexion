package {
	import flash.display.MovieClip;

	// C-19: the overlay window's document class. F4SE's custom menu loads this movie and calls
	// onF4SEObjCreated with its code object; the panel (Menu_mc) does the rest. Ported from Silhouette (S-79).
	[SWF(width="1280", height="720", frameRate="30", backgroundColor="#000000")]
	public class ComplexionMenu extends MovieClip {
		public var Menu_mc:Panel;

		public function ComplexionMenu() {
			Menu_mc = new Panel();
			Menu_mc.name = "Menu_mc";
			addChild(Menu_mc);
		}

		public function onF4SEObjCreated(a_f4se:Object):void {
			Menu_mc.Connect(a_f4se);
		}
	}
}

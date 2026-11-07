using System.Windows;using System.Windows.Interop;using System.Windows.Media;
namespace PhotosNative;
internal static class NativeMaterial {
 public static bool LastSuccess{get;private set;}public static string LastMode{get;private set;}="Solid";
 public static Brush Apply(Window window,HwndSource source,int material,bool light,bool transparency,bool contrast){var brush=SuiteWindow.Material(window,source,material,light,transparency,contrast,out bool ok);LastSuccess=ok;LastMode=ok?(material==1?"TranslucentSoft":"Translucent"):"Solid";return brush;}
}

using System.Windows;using System.Windows.Interop;using System.Windows.Media;
namespace PhotosNative;
internal static class NativeMaterial {
 public static bool LastSuccess{get;private set;}public static string LastMode{get;private set;}="Solid";
 public static Brush Apply(Window window,HwndSource source,int material,bool light,bool transparency,bool contrast,double opacityPercent=100){var brush=SuiteWindow.Material(window,source,material,light,transparency,contrast,out bool ok);if(!contrast && brush is SolidColorBrush background){var color=background.Color;color.A=transparency?(byte)System.Math.Round(255*System.Math.Clamp(opacityPercent,20,100)/100):(byte)255;brush=new SolidColorBrush(color);}LastSuccess=ok;LastMode=brush is SolidColorBrush solid && solid.Color.A==255?"Solid":ok?(material==1?"TranslucentSoft":"Translucent"):"Solid";return brush;}
}

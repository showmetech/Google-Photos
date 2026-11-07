using System;
using System.Windows;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Media;
using System.Runtime.InteropServices;
internal static class SuiteWindow {
 public static (double Width,double Height,double Margin) Fit(double width,double height){double margin=Math.Min(12,Math.Max(0,Math.Min(width,height)/10));return(Math.Max(1,Math.Min(360,width-2*margin)),Math.Max(1,Math.Min(600,height-2*margin)),margin);}
 public static void Keys(Window window,Action hide,Action settings){window.PreviewKeyDown+=(_,e)=>{if(e.Key==Key.Escape){hide();e.Handled=true;}else if(e.Key==Key.OemComma&&(Keyboard.Modifiers&ModifierKeys.Control)!=0){settings();e.Handled=true;}};}
 public static Brush Material(Window window,HwndSource source,int material,bool light,bool transparency,bool contrast,out bool success){
  success=!contrast;window.Background=Brushes.Transparent;if(source!=null)source.CompositionTarget.BackgroundColor=Colors.Transparent;
  if(contrast)return SystemColors.WindowBrush;
  byte alpha=material==1?(byte)210:material==2?(byte)145:(byte)180;
  return new SolidColorBrush(light?Color.FromArgb(alpha,243,243,243):Color.FromArgb(alpha,32,32,32));
 }
 [StructLayout(LayoutKind.Sequential)]struct Margins{public int Left,Right,Top,Bottom;}
 [DllImport("dwmapi.dll")]static extern int DwmSetWindowAttribute(IntPtr hwnd,int attribute,ref int value,int size);
 [DllImport("dwmapi.dll")]static extern int DwmExtendFrameIntoClientArea(IntPtr hwnd,ref Margins margins);
}

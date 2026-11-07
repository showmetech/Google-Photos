using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;
namespace PhotosNative;
// Crops the native surface on compositor frames without resizing WPF's layout.
internal sealed class WindowRevealAnimation:IDisposable {
 static int activeCount;public static bool IsRunning=>activeCount>0;
 readonly IntPtr hwnd;readonly int width,height;readonly bool opening;readonly Action completed;readonly Stopwatch watch=new();
 readonly Action<int>? sample;bool stopped;double previous;int previousHeight=-1;
 public int Frames{get;private set;} public double MaxFrameGapMs{get;private set;}
 public WindowRevealAnimation(Window window,bool opening,Action completed,Action<int>? sample=null){
  hwnd=new WindowInteropHelper(window).Handle;GetWindowRect(hwnd,out var r);width=r.Right-r.Left;height=r.Bottom-r.Top;this.opening=opening;this.completed=completed;this.sample=sample;
  activeCount++;Apply(opening?0:1);watch.Start();CompositionTarget.Rendering+=Render;
 }
 void Render(object? sender,EventArgs e){
  if(stopped)return;double ms=watch.Elapsed.TotalMilliseconds;MaxFrameGapMs=Math.Max(MaxFrameGapMs,ms-previous);previous=ms;Frames++;
  double t=Math.Clamp(ms/240,0,1),ease=1-Math.Pow(1-t,3);Apply(opening?ease:1-ease);
  if(t>=1){CompositionTarget.Rendering-=Render;stopped=true;activeCount=Math.Max(0,activeCount-1);if(opening)Reset();completed();}
 }
 void Apply(double progress){int h=Math.Max(1,(int)Math.Round(height*progress));if(h==previousHeight)return;previousHeight=h;var region=CreateRoundRectRgn(0,height-h,width+1,height+1,16,16);if(SetWindowRgn(hwnd,region,false)==0)DeleteObject(region);sample?.Invoke(h);}
 void Reset()=>SetWindowRgn(hwnd,IntPtr.Zero,true);
 public void Dispose(){CompositionTarget.Rendering-=Render;if(!stopped)activeCount=Math.Max(0,activeCount-1);stopped=true;Reset();}
 [StructLayout(LayoutKind.Sequential)]struct Rect{public int Left,Top,Right,Bottom;}
 [DllImport("user32.dll")]static extern bool GetWindowRect(IntPtr h,out Rect r);
 [DllImport("user32.dll")]static extern int SetWindowRgn(IntPtr h,IntPtr region,bool redraw);
 [DllImport("gdi32.dll")]static extern IntPtr CreateRoundRectRgn(int a,int b,int c,int d,int e,int f);
 [DllImport("gdi32.dll")]static extern bool DeleteObject(IntPtr obj);
}





using System;using System.IO;using System.Linq;using System.Collections.Generic;using System.Text.Json;using System.Threading.Tasks;using System.Windows;using System.Windows.Interop;using System.Windows.Media;using System.Runtime.InteropServices;
internal static class LiveProbe {
 static readonly DateTimeOffset boot=DateTimeOffset.UtcNow;static string last="";static bool busy;
 public static bool Running=>busy;
 public static void Poll(Window window,Action show,Action hide,Action settings,Func<bool> settingsOpen,Action back,Func<bool> tray,Func<bool> settingsGeometry,Func<object> facts){
  string path=Path.Combine(AppContext.BaseDirectory,".widget-live-test-request");string value;try{value=File.ReadAllText(path);}catch{return;}
  if(busy||value==last||!DateTimeOffset.TryParse(value,out var time)||time<boot||time>DateTimeOffset.UtcNow.AddSeconds(10))return;
  last=value;busy=true;_=Run(window,show,hide,settings,settingsOpen,back,tray,settingsGeometry,facts);
 }
 static async Task Run(Window window,Action show,Action hide,Action settings,Func<bool> settingsOpen,Action back,Func<bool> tray,Func<bool> settingsGeometry,Func<object> facts){
  var checks=new Dictionary<string,bool>();string? error=null;object? detail=null;
  try{
   checks["OutsideFocusPolicy"]=SuiteActivation.VerifyFocusPolicy();checks["NativeFocusDismissalAndPin"]=await SuiteActivation.VerifyNativeFocus(window,show);show();await Task.Delay(500);window.UpdateLayout();var hwnd=new WindowInteropHelper(window).Handle;var dpi=VisualTreeHelper.GetDpi(window);
   checks["StandardActionPositions"]=SuiteChrome.Aligned(window);checks["WindowOpened"]=window.IsVisible&&IsWindowVisible(hwnd);checks["TrayRegistered"]=tray();
   checks["StandardWidth"]=Math.Abs(window.ActualWidth-360)<1;checks["StandardHeight"]=Math.Abs(window.ActualHeight-600)<1;
   checks["BackgroundBrushAvailable"]=window.AllowsTransparency&&window.Content is System.Windows.Controls.Border surface&&surface.Background is SolidColorBrush brush&&brush.Color.A>=51;checks["DpiValid"]=dpi.DpiScaleX>0&&dpi.DpiScaleY>0;
   settings();for(int i=0;i<50&&!settingsOpen();i++)await Task.Delay(100);await Task.Delay(600);
   checks["SettingsOpened"]=settingsOpen();checks["SettingsGeometry"]=settingsGeometry();
   back();for(int i=0;i<50&&settingsOpen();i++)await Task.Delay(100);checks["SettingsClosed"]=!settingsOpen();
   hide();await Task.Delay(500);checks["WidgetHidden"]=!window.IsVisible&&!IsWindowVisible(hwnd);checks["TrayPreservedWhileHidden"]=tray();
   show();await Task.Delay(500);checks["WidgetReopened"]=window.IsVisible&&IsWindowVisible(hwnd);checks["TrayPreservedAfterReopen"]=tray();detail=facts();if(detail?.GetType().GetProperty("LayoutVerified")?.GetValue(detail) is bool layoutOK)checks["RequestedLayout"]=layoutOK;if(detail is Task<object> factTask)detail=await factTask;if(detail?.GetType().GetProperty("AccountConnection")?.GetValue(detail) is bool connected)checks["AccountConnection"]=connected;
  }catch(Exception ex){error=ex.ToString();checks["Completed"]=false;}
  finally{try{back();show();}catch{}try{var result=new{At=DateTimeOffset.Now,ProcessId=Environment.ProcessId,Version=System.Reflection.Assembly.GetEntryAssembly()?.GetName().Version?.ToString(),Checks=checks,Facts=detail,Passed=checks.Values.All(v=>v),Error=error,Method="Production handlers and native HWND/tray registration in the installed desktop process; no physical input, uploads or audio writes"};var path=Path.Combine(AppContext.BaseDirectory,".widget-live-test.json");File.WriteAllText(path+".tmp",JsonSerializer.Serialize(result,new JsonSerializerOptions{WriteIndented=true}));File.Move(path+".tmp",path,true);}finally{busy=false;}}
 }
 [DllImport("user32.dll")]static extern bool IsWindowVisible(IntPtr hwnd);
}

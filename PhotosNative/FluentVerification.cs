using System.IO;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
namespace PhotosNative;
public partial class MainWindow {
 async Task<bool> VerifyFluentControls(){
  var checks=new Dictionary<string,bool>();
  var original=prefs.DeepClone();
  try{
   foreach(int theme in new[]{1,2}){
    prefs["theme"]=theme;appearanceSignature="";ApplyAppearance();UpdateLayout();
    sync.IsEnabled=true;sync.ApplyTemplate();
    var buttonSurface=sync.Template.FindName("ButtonSurface",sync) as Border;
    checks["CornerRadius"+theme]=buttonSurface?.CornerRadius.TopLeft==4;
    checks["MouseOver"+theme]=VisualStateManager.GoToState(sync,"MouseOver",false);
    checks["Pressed"+theme]=VisualStateManager.GoToState(sync,"Pressed",false);
    checks["Normal"+theme]=VisualStateManager.GoToState(sync,"Normal",false);
    sync.IsEnabled=false;
    checks["Disabled"+theme]=VisualStateManager.GoToState(sync,"Disabled",false);
    OpenPanel(false);await Task.Delay(150);UpdateLayout();panel!.UpdateLayout();
    checks["SelectorText"+theme]=panel.Tag is ComboBox selector&&selector.SelectedItem is ComboBoxItem entry&&entry.Content is StackPanel;
    foreach(var capture in new[]{(window:(Window)this,name:"widget"),(window:panel!,name:"settings")}){
     var dpi=VisualTreeHelper.GetDpi(capture.window);var image=new RenderTargetBitmap((int)(capture.window.ActualWidth*dpi.DpiScaleX),(int)(capture.window.ActualHeight*dpi.DpiScaleY),96*dpi.DpiScaleX,96*dpi.DpiScaleY,PixelFormats.Pbgra32);image.Render(capture.window);
     var encoder=new PngBitmapEncoder();encoder.Frames.Add(BitmapFrame.Create(image));using var stream=File.Create(Path.Combine(Paths.Data,$"fluent-{capture.name}-{theme}.png"));encoder.Save(stream);
    }
   }
   prefs["animations"]=false;appearanceSignature="";ApplyAppearance();
   checks["KeyboardFocus"]=sync.FocusVisualStyle!=null;
   var passed=checks.Values.All(v=>v);File.WriteAllText(Path.Combine(Paths.Data,"fluent-verification.json"),JsonSerializer.Serialize(new{Passed=passed,Checks=checks},new JsonSerializerOptions{WriteIndented=true}));return passed;
  }finally{prefs=(System.Text.Json.Nodes.JsonObject)original;}
 }
}

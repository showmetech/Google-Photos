using System.IO;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Threading;
namespace PhotosNative;
public partial class MainWindow {
 async Task<bool> VerifyAdaptiveNavigation(){
  var results=new Dictionary<string,bool>();
  var nav=(ComboBox)panel!.Tag;int selected=nav.SelectedIndex;double width=panel.Width,height=panel.Height,scale=textScale;
  try{
   foreach(var size in new[]{(320d,520d),(360d,600d)})foreach(double zoom in new[]{1d,1.5d,2d}){
    panel.Width=size.Item1;panel.Height=size.Item2;ApplyTextScaleFactor(zoom);
    for(int index=0;index<8;index++){
     nav.SelectedIndex=index;panel.UpdateLayout();AdaptContent();panel.UpdateLayout();
     var host=(StackPanel)panelScroll!.Content;
     bool reachable=host.DesiredSize.Height<=panelScroll.ViewportHeight+1||panelScroll.VerticalScrollBarVisibility==ScrollBarVisibility.Auto;
     results[$"Reachable-{size.Item1}-{zoom}-{index}"]=reachable&&panelScroll.ScrollableWidth<1;
    }
   }
   panel.Width=width;panel.Height=height;ApplyTextScaleFactor(1);nav.SelectedIndex=4;panel.UpdateLayout();
   panel.Activate();nav.Focus();nav.MoveFocus(new TraversalRequest(FocusNavigationDirection.Next));
   await Dispatcher.Yield(DispatcherPriority.ApplicationIdle);
   results["NavigationBeforePageCommands"]=Keyboard.FocusedElement is Button b&&System.Windows.Automation.AutomationProperties.GetName(b)==Locale.Text("Mais opções de pastas");
   results["SingleNavigation"]=configurationRoot?.Children.OfType<System.Windows.Controls.Primitives.UniformGrid>().Any()==false;
  }finally{panel.Width=width;panel.Height=height;ApplyTextScaleFactor(scale);nav.SelectedIndex=selected;Position();}
  bool passed=results.Values.All(v=>v);
  File.WriteAllText(Path.Combine(Paths.Data,"adaptive-navigation.json"),JsonSerializer.Serialize(new{Passed=passed,Checks=results},new JsonSerializerOptions{WriteIndented=true}));return passed;
 }
}

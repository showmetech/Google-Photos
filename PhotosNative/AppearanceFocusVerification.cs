using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Threading;
namespace PhotosNative;
public partial class MainWindow {
 async Task<Dictionary<string,bool>> VerifyAppearanceKeyboardFocus(){
  var checks=new Dictionary<string,bool>();
  var saved=prefs.DeepClone();
  OpenPanel(false);await Task.Delay(500);
  var section=(ComboBox)panel!.Tag;int previous=section.SelectedIndex;
  try{
   section.SelectedIndex=3;panel.Activate();await Dispatcher.Yield(DispatcherPriority.ApplicationIdle);
   foreach(int theme in new[]{1,2}){
    bool sectionReset=false;
    SelectionChangedEventHandler selectionChanged=(_,_)=>{if(section.SelectedIndex<0)sectionReset=true;};
    section.SelectionChanged+=selectionChanged;
    try{
    themeChoice!.Focus();themeChoice.IsDropDownOpen=true;
    await Dispatcher.Yield(DispatcherPriority.ApplicationIdle);
    var item=(ComboBoxItem)themeChoice.ItemContainerGenerator.ContainerFromIndex(theme);
    item.Focus();item.IsSelected=true;themeChoice.IsDropDownOpen=false;
    // Model the native template's lost focus reported by the interactive QA.
    Keyboard.ClearFocus();
    await Dispatcher.Yield(DispatcherPriority.ApplicationIdle);
    checks["ThemeKeepsKeyboardFocus"+theme]=themeChoice.IsKeyboardFocusWithin;
    themeChoice.MoveFocus(new TraversalRequest(FocusNavigationDirection.Next));
    checks["ThemeTabContinuesToMaterial"+theme]=materialChoice!.IsKeyboardFocusWithin;
    checks["ThemeDoesNotResetSectionSelection"+theme]=!sectionReset;
    }finally{section.SelectionChanged-=selectionChanged;}
   }
  }finally{
   themeChoice!.IsDropDownOpen=false;
   themeChoice.SelectedIndex=saved["theme"]?.GetValue<int>()??0;
   prefs=(System.Text.Json.Nodes.JsonObject)saved;
   appearanceSignature="";ApplyAppearance();section.SelectedIndex=previous;
  }
  return checks;
 }
}

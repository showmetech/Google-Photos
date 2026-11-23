using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Threading;
namespace PhotosNative;
public partial class MainWindow {
 long appearanceFocusGeneration;
 FrameworkElement? CaptureAppearanceFocus(){
  if(themeChoice is {IsDropDownOpen:true} or {IsKeyboardFocusWithin:true})return themeChoice;
  if(materialChoice is {IsDropDownOpen:true} or {IsKeyboardFocusWithin:true})return materialChoice;
  if(Keyboard.FocusedElement is FrameworkElement element){
   var owner=Window.GetWindow(element);
   if(owner==this||owner==panel)return element;
  }
  return null;
 }
 void RestoreAppearanceFocus(FrameworkElement? target){
  long generation=++appearanceFocusGeneration;
  if(target==null)return;
  Dispatcher.BeginInvoke(DispatcherPriority.ContextIdle,new Action(()=>{
   if(generation!=appearanceFocusGeneration||!target.IsVisible||!target.IsEnabled)return;
   var owner=Window.GetWindow(target);
   if(owner?.IsActive!=true||target is ComboBox {IsDropDownOpen:true})return;
   // Do not steal focus if the user has already moved to another live control.
   var current=Keyboard.FocusedElement as FrameworkElement;
   if(current==null||current is Window||!current.IsVisible)target.Focus();
  }));
 }
}

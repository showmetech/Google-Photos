using System.Windows;
using System.Windows.Automation;
using System.Windows.Automation.Peers;
using System.Windows.Controls;
using System.Windows.Media;
using Windows.UI.ViewManagement;
namespace PhotosNative;
public partial class MainWindow {
 UISettings? accessibilitySettings;
 readonly Dictionary<DependencyObject,double> baseTextSizes=new();
 double textScale=1;
 string announced="";
 void InitializeAccessibility(){
  AutomationProperties.SetLiveSetting(status,AutomationLiveSetting.Polite);
  try{
   accessibilitySettings=new UISettings();
   accessibilitySettings.TextScaleFactorChanged+=TextScaleChanged;
   UpdateTextScale();
  }catch(System.Runtime.InteropServices.COMException){ }
 }
 void TextScaleChanged(UISettings sender,object args)=>Dispatcher.BeginInvoke(UpdateTextScale);
 void UpdateTextScale()=>ApplyTextScaleFactor(accessibilitySettings?.TextScaleFactor??1);
 void ApplyTextScaleFactor(double scale){
  textScale=Math.Clamp(scale,1,2.25);ApplyTextScale(this);if(panel!=null)ApplyTextScale(panel);
  foreach(var border in new[]{surface,panelSurface})if(border?.Child is Grid grid){double height=SuiteChrome.HeaderHeight*textScale;grid.RowDefinitions[0].Height=new GridLength(height);if(grid.Children.Count>0&&grid.Children[0] is FrameworkElement header)header.Height=height;}
 }
 void ApplyTextScale(DependencyObject element){
  var property=element is TextBlock?TextBlock.FontSizeProperty:element is Control?Control.FontSizeProperty:null;
  if(element is TextBlock glyph && glyph.FontFamily.Source.Contains("Segoe Fluent Icons"))property=null;
  if(property!=null&&element.ReadLocalValue(property)!=DependencyProperty.UnsetValue){
   if(!baseTextSizes.TryGetValue(element,out double original)){original=(double)element.GetValue(property);baseTextSizes[element]=original;}
   element.SetValue(property,original*textScale);
  }
  foreach(var child in LogicalTreeHelper.GetChildren(element))if(child is DependencyObject dependency)ApplyTextScale(dependency);
 }
 void AnnounceStatus(){
  if(announced==status.Text)return;announced=status.Text;
  if(UIElementAutomationPeer.FromElement(status) is AutomationPeer peer)peer.RaiseAutomationEvent(AutomationEvents.LiveRegionChanged);
 }
 void DisposeAccessibility(){if(accessibilitySettings!=null)accessibilitySettings.TextScaleFactorChanged-=TextScaleChanged;}
}

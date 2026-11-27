using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Animation;
namespace PhotosNative;

public partial class MainWindow {
 static readonly (string Title,string Icon)[] SettingsDestinations={
  ("Visão geral","\uE80F"),("Pendências","\uE9F9"),("Atividade","\uE9D9"),("Aparência","\uE790"),
  ("Pastas","\uE8B7"),("Conta","\uE77B"),("Envios","\uE895"),("Windows","\uE770")};
 void NavigateSettings(ComboBox choice,StackPanel[] sections){
  if(choice.SelectedIndex<0)return;
  int selected=choice.SelectedIndex;
  for(int i=0;i<sections.Length;i++)sections[i].Visibility=i==(selected<4?selected:4)?Visibility.Visible:Visibility.Collapsed;
  if(selected>=4)SelectConfigurationPage(selected-4);
  panelScroll?.ScrollToTop();
  var page=sections[selected<4?selected:4];
  Dispatcher.BeginInvoke(new Action(()=>{ApplyTextScale(page);AdaptContent();}));
  page.BeginAnimation(OpacityProperty,null);
  if(Animations&&!SystemParameters.HighContrast)
   page.BeginAnimation(OpacityProperty,new DoubleAnimation(.65,1,TimeSpan.FromMilliseconds(120)){FillBehavior=FillBehavior.Stop});
 }
 void AdaptContent(){
  if(previewFrame!=null)previewFrame.Height=Math.Clamp((ActualHeight-64*textScale-260*textScale),96,216);
  // Keep controls and typography usable; allow a single vertical scroll owner
  // only when the actual page exceeds its viewport (including Windows text zoom).
  if(panelScroll?.Content is StackPanel host&&panelScroll.ViewportWidth>0){
   host.Measure(new Size(panelScroll.ViewportWidth,double.PositiveInfinity));
   panelScroll.VerticalScrollBarVisibility=host.DesiredSize.Height>panelScroll.ViewportHeight+1?ScrollBarVisibility.Auto:ScrollBarVisibility.Disabled;
  }
 }
}

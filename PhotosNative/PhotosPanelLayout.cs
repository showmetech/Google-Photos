internal static class PhotosPanelLayout {
 internal record Frame(int Top,int Height,bool Overlay);
 internal static Frame Calculate(int workTop,int workBottom,int widgetTop,double scale){
  int gap=(int)System.Math.Round(12*scale),top=workTop+gap;
  int available=widgetTop-gap-top;
  if(available>=System.Math.Round(480*scale)){int capped=System.Math.Min(available,(int)System.Math.Round(600*scale));return new(widgetTop-gap-capped,capped,false);}
  // Short displays show Settings in the widget's right-hand column, covering
  // the widget until Settings closes, rather than clipping the controls.
  int height=System.Math.Max(1,System.Math.Min((int)System.Math.Round(600*scale),workBottom-workTop-2*gap));
  return new(workBottom-gap-height,height,true);
 }
}

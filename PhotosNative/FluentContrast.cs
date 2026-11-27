namespace PhotosNative;
internal static class FluentContrast {
 static double Linear(byte channel){double s=channel/255d;return s<=.04045?s/12.92:System.Math.Pow((s+.055)/1.055,2.4);}
 internal static double Luminance(byte r,byte g,byte b)=>.2126*Linear(r)+.7152*Linear(g)+.0722*Linear(b);
 internal static bool UseBlack(byte r,byte g,byte b){double l=Luminance(r,g,b);return (l+.05)/.05>=1.05/(l+.05);}
 internal static double BestRatio(byte r,byte g,byte b){double l=Luminance(r,g,b);return System.Math.Max((l+.05)/.05,1.05/(l+.05));}
}

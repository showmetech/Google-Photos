using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Windows;
using System.Windows.Markup;
namespace PhotosNative;
internal static class Locale {
 static Dictionary<string,string> english=new(),local=new();
 public static CultureInfo Culture=>CultureInfo.CurrentUICulture;
 public static string EffectiveLanguage{get;private set;}="en";
 public static void Configure(){
  var requested=Environment.GetCommandLineArgs().FirstOrDefault(a=>a.StartsWith("--ui-culture="))?[13..];
  if(requested!=null){try{CultureInfo.CurrentUICulture=CultureInfo.GetCultureInfo(requested);CultureInfo.CurrentCulture=CultureInfo.CurrentUICulture;}catch(CultureNotFoundException){CultureInfo.CurrentUICulture=CultureInfo.GetCultureInfo("en-US");}}
  string dir=Path.Combine(AppContext.BaseDirectory,"Locales");english=Read(Path.Combine(dir,"en.json"));
  foreach(string name in new[]{Culture.Name,Culture.TwoLetterISOLanguageName,"en"}){string path=Path.Combine(dir,name+".json");if(File.Exists(path)){local=Read(path);EffectiveLanguage=name;break;}}
 }
 static Dictionary<string,string> Read(string path){try{return JsonSerializer.Deserialize<Dictionary<string,string>>(File.ReadAllText(path))??new();}catch{return new();}}
 public static string Text(string value)=>local.GetValueOrDefault(value,english.GetValueOrDefault(value,value));
 public static string Format(string value,params object[] args)=>string.Format(CultureInfo.CurrentCulture,Text(value),args);
 public static void Apply(Window window){window.FlowDirection=Culture.TextInfo.IsRightToLeft?FlowDirection.RightToLeft:FlowDirection.LeftToRight;window.Language=XmlLanguage.GetLanguage(Culture.IetfLanguageTag);}
}

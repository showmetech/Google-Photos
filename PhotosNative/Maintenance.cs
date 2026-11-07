using System;
using System.Globalization;
using System.IO;
namespace PhotosNative;
internal static class Maintenance {
 internal static string ExitPath=>Path.Combine(Paths.Data,".widget-exit-request");
 internal static void RequestExit(string? path=null){path??=ExitPath;Directory.CreateDirectory(Path.GetDirectoryName(path)!);var temp=path+"."+Guid.NewGuid().ToString("N")+".tmp";File.WriteAllText(temp,DateTime.UtcNow.ToString("O",CultureInfo.InvariantCulture));File.Move(temp,path,true);}
 internal static bool ExitRequested(DateTime started,string? path=null){try{var value=DateTime.Parse(File.ReadAllText(path??ExitPath),CultureInfo.InvariantCulture,DateTimeStyles.RoundtripKind);return value>=started&&value<=DateTime.UtcNow.AddSeconds(10);}catch{return false;}}
}

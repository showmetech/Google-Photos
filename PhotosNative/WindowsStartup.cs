using Microsoft.Win32;
using System.IO;
namespace PhotosNative;
internal static class WindowsStartup {
 const string Run=@"Software\Microsoft\Windows\CurrentVersion\Run";
 internal const string Name="Google Photos Uploader";
 const string Legacy="GooglePhotosUploadManager";
 internal record State(bool Registered,bool? Disabled,bool Available=true);
 internal static State Read(){try{
  if(PackageContext.IsPackaged){var task=Windows.ApplicationModel.StartupTask.GetAsync(PackageContext.StartupId).AsTask().GetAwaiter().GetResult();return new(task.State==Windows.ApplicationModel.StartupTaskState.Enabled,task.State==Windows.ApplicationModel.StartupTaskState.DisabledByUser);}
  using var run=Registry.CurrentUser.OpenSubKey(Run);
  string? entry=run?.GetValue(Name) as string;string name=Name;
  if(string.IsNullOrEmpty(entry)){entry=run?.GetValue(Legacy) as string;name=Legacy;}
  if(string.IsNullOrEmpty(entry))return new(false,null);
  bool own=entry.Contains(Paths.Root,StringComparison.OrdinalIgnoreCase);
  // Read-only observation; Windows owns approval and policy. Never overwrite it.
  using var approval=Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run");
  var data=approval?.GetValue(name) as byte[];
  bool? disabled=data is {Length:>=4}?data[0] is 3 or 7?true:data[0] is 2 or 6?false:null:null;
  return new(own,disabled);}catch(Exception ex) when(ex is System.Security.SecurityException or UnauthorizedAccessException or IOException){return new(false,null,false);}
 }
 internal static void SetEnabled(bool enabled){
  if(PackageContext.IsPackaged){var task=Windows.ApplicationModel.StartupTask.GetAsync(PackageContext.StartupId).AsTask().GetAwaiter().GetResult();if(enabled)task.RequestEnableAsync().AsTask().GetAwaiter().GetResult();else task.Disable();return;}
  string exe=Path.Combine(Paths.Root,"native","GooglePhotosWidget.exe");
  if(enabled&&!File.Exists(exe))throw new FileNotFoundException(exe);
  using var run=Registry.CurrentUser.CreateSubKey(Run);
  if(enabled)run.SetValue(Name,"\""+exe+"\" --minimized",RegistryValueKind.String);
  else run.DeleteValue(Name,false);
  if(run.GetValue(Legacy) is string old&&old.Contains(Paths.Root,StringComparison.OrdinalIgnoreCase))run.DeleteValue(Legacy,false);
 }
}

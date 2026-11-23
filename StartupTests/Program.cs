using PhotosNative;
using Windows.ApplicationModel;
var cases = new[] {
 (StartupTaskState.Disabled, true, true, true),
 (StartupTaskState.DisabledByUser, true, true, true),
 (StartupTaskState.Enabled, true, false, true),
 (StartupTaskState.DisabledByPolicy, true, true, false),
 (StartupTaskState.EnabledByPolicy, true, false, false)
};
foreach(var (value,registered,disabled,available) in cases){
 var state=WindowsStartup.FromPackagedState(value);
 if(state.Registered!=registered || state.Disabled!=disabled || state.Available!=available)
  throw new Exception($"Incorrect startup state: {value}: {state}");
 if(disabled && string.IsNullOrEmpty(state.Message))throw new Exception($"Missing actionable message: {value}");
}
var unknown=WindowsStartup.FromPackagedState((StartupTaskState)99);
if(unknown.Registered || unknown.Available || unknown.Disabled!=null)throw new Exception("Unknown state must be unavailable");
Console.WriteLine("PASS: all five Windows startup states and unknown state; no registration changed.");
namespace PhotosNative {
 internal static class PackageContext { internal static bool IsPackaged=>false; internal const string StartupId="not-used"; }
 internal static class Paths { internal static string Root=>Path.GetTempPath(); }
}

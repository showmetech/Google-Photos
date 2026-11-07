using System.Runtime.InteropServices;
namespace PhotosNative;
internal static class PackageContext {
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode)]static extern int GetCurrentPackageFullName(ref uint length,System.Text.StringBuilder? value);
 internal static bool IsPackaged { get { uint length=0;return GetCurrentPackageFullName(ref length,null)!=15700; } }
 internal const string StartupId="GooglePhotosStartup";
}

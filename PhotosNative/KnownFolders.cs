using System.Runtime.InteropServices;
namespace PhotosNative;
internal static class KnownFolders {
 public static IEnumerable<string> Media(){
  foreach(var id in new[]{new Guid("33e28130-4e1e-4676-835a-98395c3bc3bb"),new Guid("18989b1d-99b5-455b-841c-ab7c74e4ddfc")}){
   IntPtr pointer=IntPtr.Zero;
   try{Guid folder=id;if(SHGetKnownFolderPath(ref folder,0,IntPtr.Zero,out pointer)==0){string? path=Marshal.PtrToStringUni(pointer);if(path!=null)yield return path;}}
   finally{if(pointer!=IntPtr.Zero)Marshal.FreeCoTaskMem(pointer);}
  }
 }
 [DllImport("shell32.dll")]static extern int SHGetKnownFolderPath(ref Guid id,uint flags,IntPtr token,out IntPtr path);
}

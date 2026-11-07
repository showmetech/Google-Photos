using System.IO;
using System.Windows;
namespace PhotosNative;
public partial class App:Application {
 Mutex? gate;EventWaitHandle? activation,exitSignal;RegisteredWaitHandle? wait,exitWait;
 protected override void OnStartup(StartupEventArgs e){
  base.OnStartup(e);DispatcherUnhandledException+=(_,error)=>{try{Directory.CreateDirectory(Paths.Data);File.AppendAllText(Path.Combine(Paths.Data,"startup-error.log"),error.Exception.ToString()+Environment.NewLine);}catch{}if(e.Args.Contains("--verify")){error.Handled=true;Shutdown(1);}};if(e.Args.Contains("--enable-startup")){WindowsStartup.SetEnabled(true);}if(e.Args.Contains("--exit")){Maintenance.RequestExit();try{using var signal=EventWaitHandle.OpenExisting(@"Local\Bruno.GooglePhotos.Exit");signal.Set();}catch(Exception ex) when(ex is WaitHandleCannotBeOpenedException or UnauthorizedAccessException){}Shutdown();return;}if(!e.Args.Contains("--verify")&&!e.Args.Contains("--supervised")){var launch=new System.Diagnostics.ProcessStartInfo(Path.Combine(Paths.Root,"runtime","pythonw.exe")){UseShellExecute=false,CreateNoWindow=true,WorkingDirectory=Paths.Root};launch.ArgumentList.Add(Path.Combine(Paths.Root,"launch_manager.pyw"));foreach(var arg in e.Args)launch.ArgumentList.Add(arg);System.Diagnostics.Process.Start(launch);Shutdown();return;}if(e.Args.Contains("--verify")){var testWindow=new MainWindow();MainWindow=testWindow;testWindow.Show();return;}gate=new Mutex(true,@"Local\Bruno.GooglePhotos.Native",out bool first);
  if(!first){try{using var signal=EventWaitHandle.OpenExisting(@"Local\Bruno.GooglePhotos.Show");signal.Set();}catch(Exception ex) when(ex is WaitHandleCannotBeOpenedException or UnauthorizedAccessException){}Shutdown();return;}
  DispatcherUnhandledException+=(_,a)=>{Directory.CreateDirectory(Paths.Data);File.AppendAllText(Path.Combine(Paths.Data,"native-ui-error.log"),DateTime.Now+" "+a.Exception+"\n");a.Handled=true;};
  var window=new MainWindow();MainWindow=window;window.Show();
  exitSignal=new(false,EventResetMode.AutoReset,@"Local\Bruno.GooglePhotos.Exit");
  exitWait=ThreadPool.RegisterWaitForSingleObject(exitSignal,(_,_)=>Dispatcher.BeginInvoke(new Action(window.RequestExit)),null,-1,false);
  activation=new(false,EventResetMode.AutoReset,@"Local\Bruno.GooglePhotos.Show");
  wait=ThreadPool.RegisterWaitForSingleObject(activation,(_,_)=>Dispatcher.BeginInvoke(new Action(window.ShowWidget)),null,-1,false);
 }
 protected override void OnExit(ExitEventArgs e){wait?.Unregister(null);exitWait?.Unregister(null);activation?.Dispose();exitSignal?.Dispose();gate?.Dispose();base.OnExit(e);}
}

internal static class Paths {
 public static string Root=Directory.GetParent(AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar))!.FullName;
 public static string Home {get {var custom=Environment.GetEnvironmentVariable("GOOGLE_PHOTOS_HOME");if(!string.IsNullOrWhiteSpace(custom))return Path.GetFullPath(custom);var standard=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"GooglePhotosUploader");return File.Exists(Path.Combine(standard,"config.json"))?standard:File.Exists(Path.Combine(Root,"config.json"))?Root:standard;}}
 public static string Data=>Path.Combine(Home,"data");
}

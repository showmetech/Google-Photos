using System;using System.IO;using System.Text.Json;using System.Threading.Tasks;
namespace PhotosNative;public partial class MainWindow {
 async Task<object> LiveConnectionFacts(){
  for(int i=0;i<30&&(Read(Path.Combine(Paths.Data,"ui-service-status.json"))["busy"]?.GetValue<bool>()??false);i++)await Task.Delay(500);
  if(Read(Path.Combine(Paths.Data,"ui-service-status.json"))["busy"]?.GetValue<bool>()==true)return new{AccountConnection=false,Reason="An existing operation is active; preserved"};
  string id=Guid.NewGuid().ToString("N");string dir=Path.Combine(Paths.Data,"ui-commands");Directory.CreateDirectory(dir);string request=Path.Combine(dir,id+".json");File.WriteAllText(request+".tmp",JsonSerializer.Serialize(new{command="doctor"}));File.Move(request+".tmp",request);
  for(int i=0;i<360;i++){var receipt=Read(Path.Combine(Paths.Data,"ui-receipts",id+".json"));if(receipt["ok"]?.GetValue<bool>()==false)return new{AccountConnection=false,Reason="Read-only diagnostic rejected",Receipt=id};if(receipt["completed"]?.GetValue<bool>()==true)return new{AccountConnection=receipt["exit_code"]?.GetValue<int>()==0,DiagnosticExitCode=receipt["exit_code"]?.GetValue<int>(),Receipt=id,UploadsRequested=false};await Task.Delay(500);}
  return new{AccountConnection=false,Reason="Read-only diagnostic timed out",Receipt=id};
 }
}

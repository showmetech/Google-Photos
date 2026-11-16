using System.IO;

using System.Text.Json.Nodes;

namespace PhotosNative;



public partial class MainWindow {

 string discoveryNotice="",lastDiscoveryId="";DateTime discoveryNoticeUntil;

 bool VerifyDiscoveryNotice(){

  if(string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("GOOGLE_PHOTOS_HOME")))return false;

  string path=Path.Combine(Paths.Data,"new-media-notification.json"),id=Guid.NewGuid().ToString("N");

  File.WriteAllText(path,new JsonObject{["schema"]=1,["id"]=id,["media_count"]=3,["folder_count"]=1,["albums"]=new JsonArray(new JsonObject{["name"]="Pasta de teste"})}.ToJsonString());

  Hide();RefreshDiscoveryNotice();bool firstVisible=IsVisible,firstText=subtitle.Text.Contains("Pasta de teste"),firstStatus=status.Text==Locale.Text("Novas mídias detectadas");bool first=firstVisible&&firstText&&firstStatus;

  Hide();RefreshDiscoveryNotice();bool once=!IsVisible&&Read(Path.Combine(Paths.Data,"new-media-notification-ack.json"))["id"]?.ToString()==id;

  File.WriteAllText(Path.Combine(Paths.Data,"discovery-verification-detail.json"),new JsonObject{["first"]=first,["firstVisible"]=firstVisible,["firstText"]=firstText,["firstStatus"]=firstStatus,["once"]=once,["visible"]=IsVisible,["status"]=status.Text,["subtitle"]=subtitle.Text,["ack"]=Read(Path.Combine(Paths.Data,"new-media-notification-ack.json"))["id"]?.ToString(),["id"]=id}.ToJsonString());Show();return first&&once;

 }

 void RefreshDiscoveryNotice(){

  var item=Read(Path.Combine(Paths.Data,"new-media-notification.json"));

  string id=item["id"]?.ToString()??"";

  if(id.Length==32&&item["schema"]?.GetValue<int>()==1&&item["media_count"]?.GetValue<int>() is int count&&count>0){

   string ackPath=Path.Combine(Paths.Data,"new-media-notification-ack.json");

   if(Read(ackPath)["id"]?.ToString()!=id&&lastDiscoveryId!=id){

    int folders=item["folder_count"]?.GetValue<int>()??1;

    string name=(item["albums"] as JsonArray)?.FirstOrDefault()?["name"]?.ToString()??"";

    discoveryNotice=Locale.Format("{0} novas mídias · {1} pasta(s)",count,folders)+(name.Length>0?"\n"+name:"");

    discoveryNoticeUntil=DateTime.UtcNow.AddMinutes(2);

    if(verify)Show();else ShowWidget();lastDiscoveryId=id;

    try{

     File.WriteAllText(ackPath+".tmp",new JsonObject{["id"]=id,["shown_at"]=DateTimeOffset.UtcNow.ToUnixTimeSeconds()}.ToJsonString());

     File.Move(ackPath+".tmp",ackPath,true);

    }catch(IOException){}catch(UnauthorizedAccessException){}

   }

  }

  if(DateTime.UtcNow<discoveryNoticeUntil){status.Text=Locale.Text("Novas mídias detectadas");subtitle.Text=discoveryNotice;}

 }

}


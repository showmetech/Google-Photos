using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using Microsoft.Win32;
namespace PhotosNative;

public partial class MainWindow:Window {
 readonly bool verify=Environment.GetCommandLineArgs().Contains("--verify");
 readonly DispatcherTimer timer=new(){Interval=TimeSpan.FromSeconds(1)};
 readonly DateTime maintenanceStarted=DateTime.UtcNow;long lastRefreshTick,lastAuditTick;
 readonly Border surface=new(){CornerRadius=new(8),BorderThickness=new(1)};
 readonly System.Windows.Controls.Image photo=new(){Stretch=Stretch.Uniform,HorizontalAlignment=HorizontalAlignment.Stretch,VerticalAlignment=VerticalAlignment.Stretch};
 readonly TextBlock previewPlaceholder=new(){TextWrapping=TextWrapping.Wrap,TextAlignment=TextAlignment.Center,VerticalAlignment=VerticalAlignment.Center,HorizontalAlignment=HorizontalAlignment.Center,Margin=new(16)};
 readonly TextBlock lastName=new(),lastDate=new(),status=new(),subtitle=new(),pending=new(),checkedAt=new(),error=new();
 readonly Button expand=new(),pin=new(),minimize=new(),sync=new(),automatic=new();
 readonly TextBlock origin=new(),counts=new(),activity=new(),pendingDetails=new(),serviceInfo=new();
 ScrollViewer? panelScroll;
 Window? panel;Border? panelSurface;ComboBox? themeChoice,materialChoice;CheckBox? animations;
 HwndSource? source;NativeTray? tray;WindowRevealAnimation? reveal, panelReveal;
 JsonObject prefs=new();bool exiting,animating;long interaction=Environment.TickCount64;string photoStamp="",appearanceSignature="",lastReceipt="";
 readonly HashSet<string> outstanding=new();DateTime lastServiceAttempt=DateTime.MinValue;
 bool Pinned=>prefs["pinned"]?.GetValue<bool>()??true;
 bool Animations=>(prefs["animations"]?.GetValue<bool>()??true)&&SystemParameters.ClientAreaAnimation;
 string PrefFile=>Path.Combine(Paths.Data,"native-widget.json");
 public MainWindow(){
  foreach(var arg in Environment.GetCommandLineArgs())if(arg.StartsWith("--root=")){Paths.Root=arg[7..];}
  Locale.Configure();prefs=Read(PrefFile);Locale.Apply(this);
  Title="Google Photos Uploader";Width=360;Height=600;WindowStyle=WindowStyle.None;ResizeMode=ResizeMode.NoResize;AllowsTransparency=true;Background=Brushes.Transparent;ShowInTaskbar=verify;
  FontFamily=new("Segoe UI Variable, Global User Interface");FontSize=14;UseLayoutRounding=true;SnapsToDevicePixels=true;SetResourceReference(ForegroundProperty,"Ink");
  surface.SetResourceReference(Border.BorderBrushProperty,"BorderLine");Content=surface;
  var grid=new Grid();grid.RowDefinitions.Add(new(){Height=new(64)});grid.RowDefinitions.Add(new(){Height=new(1,GridUnitType.Star)});grid.RowDefinitions.Add(new(){Height=new(44)});surface.Child=grid;
  
  SetIcon(minimize,"\uE8BB","Minimizar para a bandeja",(_,_)=>HideTogether());
  SetIcon(pin,"\uE718","Manter aberto",(_,_)=>{prefs["pinned"]=!Pinned;SavePrefs();UpdatePin();Touch();});
  SetIcon(expand,"\uE713","Abrir configurações",(_,_)=>TogglePanel());
  var head=SuiteChrome.Header(Text("Google Fotos",20,true),expand,pin,minimize);grid.Children.Add(head);
  var scroll=new ScrollViewer{VerticalScrollBarVisibility=ScrollBarVisibility.Auto,HorizontalScrollBarVisibility=ScrollBarVisibility.Disabled};Grid.SetRow(scroll,1);grid.Children.Add(scroll);
  var body=new StackPanel{Margin=new(20,8,20,8)};scroll.Content=body;
  var previewGrid=new Grid();previewGrid.Children.Add(photo);previewPlaceholder.Text=Locale.Text("Prévia indisponível");previewPlaceholder.SetResourceReference(TextBlock.ForegroundProperty,"SecondaryInk");previewGrid.Children.Add(previewPlaceholder);var frame=new Border{Height=216,CornerRadius=new(8),ClipToBounds=true,Child=previewGrid};frame.SetResourceReference(Border.BackgroundProperty,"TileBrush");body.Children.Add(frame);
  frame.SizeChanged+=(_,_)=>frame.Clip=new RectangleGeometry(new System.Windows.Rect(0,0,frame.ActualWidth,frame.ActualHeight),8,8);
  body.Children.Add(Text("Último envio confirmado",12,false,"SecondaryInk",new(0,10,0,2)));
  lastName.FontWeight=FontWeights.SemiBold;lastName.TextTrimming=TextTrimming.CharacterEllipsis;body.Children.Add(lastName);
  lastDate.FontSize=12;lastDate.SetResourceReference(TextBlock.ForegroundProperty,"SecondaryInk");lastDate.Margin=new(0,2,0,12);body.Children.Add(lastDate);
  body.Children.Add(Line());
  status.FontSize=16;status.FontWeight=FontWeights.SemiBold;status.Margin=new(0,12,0,4);body.Children.Add(status);
  subtitle.FontSize=12;subtitle.TextWrapping=TextWrapping.Wrap;subtitle.SetResourceReference(TextBlock.ForegroundProperty,"SecondaryInk");body.Children.Add(subtitle);
  var row=new DockPanel{Margin=new(0,10,0,10)};body.Children.Add(row);pending.SetResourceReference(TextBlock.ForegroundProperty,"AccentTextFillColorPrimaryBrush");pending.FontWeight=FontWeights.SemiBold;row.Children.Add(pending);
  automatic.Padding=new(8,2,8,2);automatic.HorizontalAlignment=HorizontalAlignment.Right;automatic.Click+=(_,_)=>Command("automatic",!(Read(Path.Combine(Paths.Home,"config.json"))["auto_monitor_enabled"]?.GetValue<bool>()??false));DockPanel.SetDock(automatic,Dock.Right);row.Children.Add(automatic);
  sync.Content=Locale.Text("Sincronizar agora");sync.Height=36;sync.SetResourceReference(BackgroundProperty,"Accent");sync.SetResourceReference(ForegroundProperty,"AccentInk");sync.Click+=(_,_)=>Command("upload");body.Children.Add(sync);
  error.TextWrapping=TextWrapping.Wrap;error.FontSize=12;error.Margin=new(0,8,0,0);error.Foreground=new SolidColorBrush(Color.FromRgb(230,100,80));body.Children.Add(error);
  var footer=new DockPanel{Margin=new(20,0,20,0)};Grid.SetRow(footer,2);grid.Children.Add(footer);
  checkedAt.FontSize=12;checkedAt.VerticalAlignment=VerticalAlignment.Center;checkedAt.SetResourceReference(TextBlock.ForegroundProperty,"SecondaryInk");footer.Children.Add(checkedAt);
  PreviewMouseMove+=(_,_)=>Touch();PreviewMouseDown+=(_,_)=>Touch();PreviewKeyDown+=(_,e)=>{Touch();if(e.Key==System.Windows.Input.Key.Escape)HideTogether();if(e.Key==System.Windows.Input.Key.F6||(e.Key==System.Windows.Input.Key.OemComma&&(System.Windows.Input.Keyboard.Modifiers&System.Windows.Input.ModifierKeys.Control)!=0))OpenPanel(false);};
  SuiteActivation.Attach(this,HideTogether,()=>Pinned);Loaded+=OnLoaded;Closing+=(_,e)=>{if(!exiting){e.Cancel=true;HideTogether();}};
  DpiChanged+=(_,_)=>Dispatcher.BeginInvoke(Position);
  SystemEvents.DisplaySettingsChanged+=DisplayChanged;SystemEvents.UserPreferenceChanged+=PreferenceChanged;
 }
 void Touch()=>interaction=Environment.TickCount64;
 void AuditState(){
  if(source==null)return;GetWindowRect(source.Handle,out var bounds);
  var state=new{At=DateTimeOffset.Now,Visible=IsVisible,NativeVisible=IsWindowVisible(source.Handle),Bounds=bounds,Pinned,PanelVisible=panel?.IsVisible==true,Animations,AnimationRunning=WindowRevealAnimation.IsRunning,FrameCount=reveal?.Frames,NativeMaterialSuccess=NativeMaterial.LastSuccess,Backdrop=NativeMaterial.LastMode,TrayIcon=tray?.IconFile,Culture=Locale.Culture.Name,EffectiveLanguage=Locale.EffectiveLanguage,Appearance=appearanceSignature,TrayRegistered=tray?.TryBounds(out _)==true};
  Directory.CreateDirectory(Paths.Data);var path=Path.Combine(Paths.Data,"ui-native-status.json");File.WriteAllText(path+".tmp",JsonSerializer.Serialize(state,new JsonSerializerOptions{IncludeFields=true}));File.Move(path+".tmp",path,true);
 }
 static JsonObject Read(string path){try{using var file=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite|FileShare.Delete);if(file.Length>1048576)return new();using var reader=new StreamReader(file);return JsonNode.Parse(reader.ReadToEnd()) as JsonObject??new();}catch{return new();}}
 void SavePrefs(){if(verify)return;Directory.CreateDirectory(Paths.Data);File.WriteAllText(PrefFile+".tmp",prefs.ToJsonString());File.Move(PrefFile+".tmp",PrefFile,true);}
 static TextBlock Text(string value,double size=14,bool bold=false,string brush="Ink",Thickness? margin=null){var t=new TextBlock{Text=Locale.Text(value),FontSize=size,FontWeight=bold?FontWeights.SemiBold:FontWeights.Normal,VerticalAlignment=VerticalAlignment.Center,TextWrapping=TextWrapping.Wrap,Margin=margin??new()};t.SetResourceReference(TextBlock.ForegroundProperty,brush);return t;}
 static Border Line(){var line=new Border{Height=1};line.SetResourceReference(Border.BackgroundProperty,"BorderLine");return line;}
 static void SetIcon(Button b,string glyph,string name,RoutedEventHandler handler){b.Width=32;b.Height=32;b.Margin=new(4,0,0,0);b.ToolTip=Locale.Text(name);b.Content=new TextBlock{Text=glyph,FontFamily=new("Segoe Fluent Icons"),FontSize=16};System.Windows.Automation.AutomationProperties.SetName(b,Locale.Text(name));SuiteChrome.Apply(b,glyph);b.Click+=handler;}
 Button ActionButton(string text,Action action){var b=new Button{Content=Locale.Text(text),Padding=new(10,8,10,8),Margin=new(0,4,0,4),HorizontalContentAlignment=HorizontalAlignment.Left};b.SetResourceReference(BackgroundProperty,"TileBrush");b.Click+=(_,_)=>{Touch();action();};return b;}
 void OnLoaded(object sender,RoutedEventArgs e){
  source=HwndSource.FromHwnd(new WindowInteropHelper(this).Handle);Icon=BitmapFrame.Create(new Uri(Path.Combine(AppContext.BaseDirectory,"Assets","App.ico")));
  Position();ApplyAppearance();UpdatePin();BuildPanel();InitializeAccessibility();Refresh();
  if(!verify){try{tray=new NativeTray(source,Path.Combine(AppContext.BaseDirectory,"Assets","Tray-dark.ico"),()=>{if(IsVisible)HideTogether();else ShowWidget();},TrayMenu);}catch(System.ComponentModel.Win32Exception){ShowInTaskbar=true;}EnsureService();}
  timer.Tick+=(_,_)=>Tick();timer.Start();
  if(verify)Dispatcher.BeginInvoke(new Action(async()=>await VerifyAsync()));
  else if(Environment.GetCommandLineArgs().Contains("--minimized"))Hide();
  else {Reveal(this,true);if(Environment.GetCommandLineArgs().Contains("--settings"))OpenPanel(true);if(string.IsNullOrWhiteSpace(Read(Path.Combine(Paths.Home,"config.json"))["photos_root"]?.ToString())){OpenPanel(false);if(panel?.Tag is ComboBox section)section.SelectedIndex=4;}}
 }
 void EnsureService(){
  var service=Read(Path.Combine(Paths.Data,"ui-service-status.json"));
  var age=DateTimeOffset.UtcNow.ToUnixTimeSeconds()-(service["heartbeat"]?.GetValue<double>()??0);
  if(age<10||DateTime.UtcNow-lastServiceAttempt<TimeSpan.FromSeconds(30))return;
  lastServiceAttempt=DateTime.UtcNow;
  var info=new ProcessStartInfo(Path.Combine(Paths.Root,"runtime","pythonw.exe")){UseShellExecute=false,CreateNoWindow=true,WorkingDirectory=Paths.Root};info.Environment["GOOGLE_PHOTOS_HOME"]=Paths.Home;info.ArgumentList.Add("-X");info.ArgumentList.Add("utf8");info.ArgumentList.Add(Path.Combine(Paths.Root,"photos_service.pyw"));Process.Start(info);
 }
 void Tick(){if(!verify)LiveProbe.Poll(this,ShowWidget,HideTogether,()=>OpenPanel(true),()=>panel?.IsVisible==true,ClosePanel,()=>tray?.TryBounds(out _)==true,()=>SuitePlacement.IsAbove(this,panel)&&panel!=null&&SuiteChrome.Aligned(panel,true),()=>new{AccountConfigured=Read(Path.Combine(Paths.Data,"ui-service-status.json"))["account_configured"]?.GetValue<bool>()??false,Backdrop=NativeMaterial.LastMode});if(!verify&&Maintenance.ExitRequested(maintenanceStarted)){Exit();return;}
  long now=Environment.TickCount64;bool visible=IsVisible||panel?.IsVisible==true;
  if(visible&&!WindowRevealAnimation.IsRunning)ApplyAppearance();
  if(now-lastRefreshTick>=(visible?1000:5000)){Refresh();lastRefreshTick=now;}
  if(!verify&&now-lastAuditTick>=10000){EnsureService();AuditState();lastAuditTick=now;}
  if(!LiveProbe.Running&&tray!=null&&!Pinned&&IsVisible&&panel?.IsVisible!=true&&Environment.TickCount64-interaction>20000&&!animating)HideTogether();
 }
 void Refresh(){
  var state=Read(Path.Combine(Paths.Data,"current_status.json"));var cfg=Read(Path.Combine(Paths.Home,"config.json"));var worker=Read(Path.Combine(Paths.Data,"ui-service-status.json"));
  bool busy=worker["busy"]?.GetValue<bool>()??false;int waiting=state["pending_files"]?.GetValue<int>()??0;string phase=state["phase"]?.ToString()??"idle";string failure=state["last_error"]?.ToString()??"";
  if(worker["last_exit_code"] is JsonValue exitValue && exitValue.TryGetValue<int>(out int lastCode) && lastCode!=0)failure=Locale.Text("A última operação falhou. Consulte a atividade.");
  var serviceAge=DateTimeOffset.UtcNow.ToUnixTimeSeconds()-(worker["heartbeat"]?.GetValue<double>()??0);
  status.Text=failure.Length>0?"Atenção necessária":busy?(phase=="upload"?"Enviando arquivos…":"Verificando arquivos…"):waiting>0?"Novos arquivos na fila":"Nenhum envio pendente";
  status.Text=Locale.Text(status.Text);
  subtitle.Text=Locale.Text("Somente arquivos novos ou modificados · Fotos");
  if(!verify&&serviceAge>15){status.Text=Locale.Text("Monitor indisponível");subtitle.Text=Locale.Text("Tentando restabelecer o serviço local…");}
  pending.Text=Locale.Format("{0} na fila",waiting);bool auto=cfg["auto_monitor_enabled"]?.GetValue<bool>()??false;automatic.Content=Locale.Text(auto?"Automático ligado":"Automático pausado");automatic.SetResourceReference(ForegroundProperty,auto?"AccentTextFillColorPrimaryBrush":"SecondaryInk");bool configured=worker["account_configured"]?.GetValue<bool>()??false;
  sync.IsEnabled=!busy&&serviceAge<15&&configured&&!string.IsNullOrWhiteSpace(cfg["photos_root"]?.ToString());
  if(!configured||string.IsNullOrWhiteSpace(cfg["photos_root"]?.ToString())){status.Text=Locale.Text("Conclua a configuração");subtitle.Text=Locale.Text("Escolha as pastas e autorize sua conta nas configurações.");}
  checkedAt.Text=Locale.Format("Verificado às {0}",(DateTime.TryParse(state["updated_at"]?.ToString(),System.Globalization.CultureInfo.InvariantCulture,System.Globalization.DateTimeStyles.None,out var check)?check.ToString("t"):"—"));
  lastName.Text=state["last_uploaded_file_name"]?.ToString()??Locale.Text("Nenhum envio registrado");
  lastDate.Text=DateTime.TryParse(state["last_uploaded_at"]?.ToString(),System.Globalization.CultureInfo.InvariantCulture,System.Globalization.DateTimeStyles.None,out var last)?last.ToString("g"):"";
  if(configured&&string.IsNullOrWhiteSpace(state["updated_at"]?.ToString())){status.Text=Locale.Text("Aguardando primeira verificação");subtitle.Text=Locale.Text("Confira o inventário antes de enviar.");}
  AnnounceStatus();error.Text=failure;
  foreach(var id in outstanding.ToArray()){
   var receipt=Read(Path.Combine(Paths.Data,"ui-receipts",id+".json"));if(receipt.Count==0)continue;
   if(receipt["ok"]?.GetValue<bool>()==false){outstanding.Remove(id);lastReceipt=receipt["error"]?.ToString()??Locale.Text("Falha na operação");}
   else if(receipt["completed"]?.GetValue<bool>()==true){outstanding.Remove(id);diagnosticResult.Text=Locale.Format("Operação: {0} · Resultado: {1}",receipt["command"]?.ToString()??"",receipt["exit_code"]?.ToString()??"—");}
   else if(receipt["command"]?.ToString() is "scan" or "doctor" or "upload" or "mark-baseline" or "reconcile" or "repair-online")diagnosticResult.Text=Locale.Text("Operação aceita. Aguardando conclusão…");
   else outstanding.Remove(id);
  }
  if(lastReceipt.Length>0)error.Text=lastReceipt;
  string path=Path.Combine(Paths.Data,"native-last-preview.jpg");if(!File.Exists(path))path=Path.Combine(Paths.Data,"last_uploaded_preview.jpg");string stamp=File.Exists(path)?File.GetLastWriteTimeUtc(path).Ticks.ToString():"";
  var previewReceipt=Read(Path.Combine(Paths.Data,"native-preview-source.json"));bool previewValid=previewReceipt.Count==0||(previewReceipt["ready"]?.GetValue<bool>()==true && previewReceipt["source"]?.ToString()==state["last_uploaded_file"]?.ToString());if(!previewValid){photo.Source=null;photoStamp="";}
  if(previewValid&&stamp!=photoStamp&&stamp.Length>0){try{using var stream=new MemoryStream(File.ReadAllBytes(path));var bitmap=new BitmapImage();bitmap.BeginInit();bitmap.CacheOption=BitmapCacheOption.OnLoad;bitmap.StreamSource=stream;bitmap.EndInit();bitmap.Freeze();photo.Source=bitmap;photoStamp=stamp;}catch(IOException){}}
  previewPlaceholder.Visibility=photo.Source==null?Visibility.Visible:Visibility.Collapsed;
  origin.Text=cfg["photos_root"]?.ToString()??"Origem não configurada";
  var roots=cfg["photos_roots"] as JsonArray;
  origin.Text=roots?.Count>0?string.Join("\n",roots.Select(r=>r?.ToString())):cfg["photos_root"]?.ToString()??Locale.Text("Origem não configurada");
  counts.Text=Locale.Format("{0} mídias pendentes\n{1} originais locais vazios conhecidos",waiting,state["known_local_invalid_files"]?.GetValue<int>()??0)+"\n\n"+Locale.Text(worker["baseline_recorded"]?.GetValue<bool>()==true?"O acervo anterior foi reconhecido por sua declaração. Os recibos confirmados permanecem preservados.":"Não há declaração de acervo anterior. Confira a fila antes de iniciar os envios.");
  serviceInfo.Text=Locale.Text(serviceAge<15?"Monitor local ativo · verificação a cada 15 minutos":"Monitor local indisponível");
  UpdateConfiguration(cfg,worker);
  System.Windows.Automation.AutomationProperties.SetName(photo,Locale.Text("Último envio confirmado")+": "+lastName.Text);
  if(panel?.IsVisible==true){
   try{var lines=ReadAuditLines(Path.Combine(Paths.Home,"audit","pending_media.csv"));pendingDetails.Text=lines.Length<=1?Locale.Text("Nenhuma pendência."):Locale.Text("Originais bloqueados / pendências")+"\n\n"+string.Join("\n",lines.Skip(1).Take(30))+"\n\n"+Locale.Text("Originais vazios permanecem bloqueados; a declaração de que as cópias antigas já estão online é preservada.");}catch(IOException){pendingDetails.Text=Locale.Text("Auditoria indisponível.");}
   try{activity.Text=ReadLogTail(Path.Combine(Paths.Home,"logs","native-service.log"));}catch(IOException){activity.Text=Locale.Text("Sem atividade nesta sessão.");}
  }
 }
 void Command(string command,bool? enabled=null)=>Send(new{command,enabled});
 static string[] ReadAuditLines(string path){using var file=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite|FileShare.Delete);using var reader=new StreamReader(file);var lines=new List<string>();while(lines.Count<32&&reader.ReadLine() is string line)lines.Add(line);return lines.ToArray();}
 static string ReadLogTail(string path){using var stream=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite);if(stream.Length>65536)stream.Seek(-65536,SeekOrigin.End);using var reader=new StreamReader(stream);if(stream.Position>0)reader.ReadLine();return string.Join("\n",reader.ReadToEnd().Split('\n').TakeLast(100));}
 static ComboBoxItem SectionItem(string title,string glyph){var row=new StackPanel{Orientation=Orientation.Horizontal};row.Children.Add(new TextBlock{Text=glyph,FontFamily=new("Segoe Fluent Icons"),Margin=new(0,0,8,0)});row.Children.Add(new TextBlock{Text=Locale.Text(title)});var item=new ComboBoxItem{Content=row};System.Windows.Automation.AutomationProperties.SetName(item,Locale.Text(title));return item;}
 void BuildPanel(){
  panel=new Window{Title=Locale.Text("Google Photos Uploader · Configurações"),Width=360,Height=600,WindowStyle=WindowStyle.None,ResizeMode=ResizeMode.NoResize,AllowsTransparency=true,Background=Brushes.Transparent,ShowInTaskbar=verify,FontFamily=FontFamily,FontSize=14,UseLayoutRounding=true};panel.SetResourceReference(ForegroundProperty,"Ink");Locale.Apply(panel);SuiteWindow.Keys(panel,ClosePanel,()=>{});
  panelSurface=new Border{CornerRadius=new(8),BorderThickness=new(1)};panelSurface.SetResourceReference(Border.BorderBrushProperty,"BorderLine");panel.Content=panelSurface;
  var grid=new Grid();grid.RowDefinitions.Add(new(){Height=new(64)});grid.RowDefinitions.Add(new(){Height=new(1,GridUnitType.Star)});panelSurface.Child=grid;
  var close=new Button();SetIcon(close,"\uE8BB","Fechar configurações",(_,_)=>ClosePanel());var head=SuiteChrome.Header(Text("Configurações",20,true),close);grid.Children.Add(head);
  panelScroll=new ScrollViewer{VerticalScrollBarVisibility=ScrollBarVisibility.Auto,HorizontalScrollBarVisibility=ScrollBarVisibility.Disabled};var scrolling=SuiteScroll.Wrap(panelScroll,Locale.Text);scrolling.Margin=new Thickness(20,0,20,12);Grid.SetRow(scrolling,1);grid.Children.Add(scrolling);
  var content=new StackPanel{Margin=new(0,0,0,12)};panelScroll.Content=content;
  var choice=new ComboBox{Margin=new(0,0,0,12),ItemsSource=new[]{("Visão geral","\uE80F"),("Pendências","\uE9F9"),("Atividade","\uE9D9"),("Aparência","\uE790"),("Configuração","\uE713")}.Select(item=>SectionItem(item.Item1,item.Item2)).ToArray(),SelectedIndex=0};content.Children.Add(choice);
  var sections=new StackPanel[5];for(int i=0;i<5;i++){sections[i]=new(){Visibility=i==0?Visibility.Visible:Visibility.Collapsed};content.Children.Add(sections[i]);}
  choice.SelectionChanged+=(_,_)=>{for(int i=0;i<5;i++)sections[i].Visibility=i==choice.SelectedIndex?Visibility.Visible:Visibility.Collapsed;};
  sections[0].Children.Add(Text("Pasta monitorada",14,true));origin.FlowDirection=FlowDirection.LeftToRight;
  sections[0].Children.Add(ActionButton("Configurar pastas e conta",()=>{choice.SelectedIndex=4;}));origin.TextWrapping=TextWrapping.Wrap;origin.FontSize=12;origin.Margin=new(0,8,0,12);sections[0].Children.Add(origin);
  serviceInfo.TextWrapping=TextWrapping.Wrap;serviceInfo.SetResourceReference(TextBlock.ForegroundProperty,"SecondaryInk");sections[0].Children.Add(serviceInfo);
  counts.TextWrapping=TextWrapping.Wrap;counts.FontSize=12;counts.Margin=new(0,12,0,12);sections[0].Children.Add(counts);
  sections[0].Children.Add(ActionButton("Verificar arquivos",()=>Command("scan")));
  sections[0].Children.Add(ActionButton("Testar acesso ao Google Fotos",()=>Command("doctor")));
  sections[0].Children.Add(ActionButton("Abrir pasta Fotos",()=>OpenLocal(origin.Text)));
  pendingDetails.TextWrapping=TextWrapping.Wrap;pendingDetails.FontSize=12;sections[1].Children.Add(pendingDetails);sections[1].Children.Add(ActionButton("Abrir auditoria e recibos",()=>OpenLocal(Path.Combine(Paths.Home,"audit"))));
  activity.TextWrapping=TextWrapping.Wrap;activity.FontFamily=new("Consolas");activity.FontSize=11;sections[2].Children.Add(activity);sections[2].Children.Add(ActionButton("Abrir logs",()=>OpenLocal(Path.Combine(Paths.Home,"logs"))));
  sections[3].Children.Add(Text("Tema",14,true));themeChoice=new ComboBox{ItemsSource=new[]{"Usar tema do Windows","Claro","Escuro"}.Select(Locale.Text).ToArray(),SelectedIndex=prefs["theme"]?.GetValue<int>()??0,Margin=new(0,8,0,16)};sections[3].Children.Add(themeChoice);
  sections[3].Children.Add(Text("Aparência",14,true));materialChoice=new ComboBox{ItemsSource=new[]{"Transparente · padrão","Transparente","Transparência suave","Transparência intensa"}.Select(Locale.Text).ToArray(),SelectedIndex=prefs["material"]?.GetValue<int>()??0,Margin=new(0,8,0,16)};sections[3].Children.Add(materialChoice);
  sections[3].Children.Add(Text("O fundo é transparente por padrão; textos e controles mantêm a opacidade. Alto contraste usa as cores do Windows.",12,false,"SecondaryInk",new(0,0,0,12)));
  animations=new CheckBox{Content=Locale.Text("Animações do Windows"),IsChecked=prefs["animations"]?.GetValue<bool>()??true,Margin=new(0,8,0,16)};sections[3].Children.Add(animations);var above=new CheckBox{Content=Locale.Text("Manter acima de outras janelas"),IsChecked=prefs["alwaysOnTop"]?.GetValue<bool>()??false,Margin=new(0,8,0,16)};above.Click+=(_,_)=>{prefs["alwaysOnTop"]=above.IsChecked==true;SavePrefs();UpdatePin();};sections[3].Children.Add(above);
  sections[3].Children.Add(Text("As configurações expandem acima do widget até o topo da tela, mantendo a mesma largura e uma margem de 12 DIP.",12,false,"SecondaryInk"));
  themeChoice.SelectionChanged+=(_,_)=>SaveAppearance();materialChoice.SelectionChanged+=(_,_)=>SaveAppearance();animations.Click+=(_,_)=>SaveAppearance();
  sections[4].Children.Add(BuildConfiguration());
  System.Windows.Automation.AutomationProperties.SetName(choice,Locale.Text("Seção de configurações"));
  System.Windows.Automation.AutomationProperties.SetName(themeChoice,Locale.Text("Tema"));
  System.Windows.Automation.AutomationProperties.SetName(materialChoice,Locale.Text("Aparência"));
  panel.Tag=choice;panel.Closing+=(_,e)=>{if(!exiting){e.Cancel=true;ClosePanel();}};panel.PreviewMouseMove+=(_,_)=>Touch();panel.PreviewMouseDown+=(_,_)=>Touch();
  panel.DpiChanged+=(_,_)=>Dispatcher.BeginInvoke(Position);
 }
 static void OpenLocal(string path){if(Directory.Exists(path))Process.Start(new ProcessStartInfo(path){UseShellExecute=true});}
 void SaveAppearance(){prefs["theme"]=themeChoice!.SelectedIndex;prefs["material"]=materialChoice!.SelectedIndex;prefs["animations"]=animations!.IsChecked==true;SavePrefs();appearanceSignature="";ApplyAppearance();}
 void ApplyAppearance(){
  const string key=@"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize";
  int theme=prefs["theme"]?.GetValue<int>()??0;bool light=theme==1||(theme==0&&(int)(Registry.GetValue(key,"AppsUseLightTheme",1)??1)!=0);
  bool transparency=(int)(Registry.GetValue(key,"EnableTransparency",1)??1)!=0;bool contrast=SystemParameters.HighContrast;
  int selected=prefs["material"]?.GetValue<int>()??0;
  int material=selected==0?0:selected-1;
  material=Math.Clamp(material,0,2);Color accent=contrast?SystemColors.HighlightColor:SystemColors.AccentColor;
  string signature=$"{Registry.GetValue(key,"SystemUsesLightTheme",1)}/{light}/{transparency}/{contrast}/{material}/{accent}";if(signature==appearanceSignature)return;appearanceSignature=signature;
  var resources=Application.Current.Resources;
  var dictionaries=resources.MergedDictionaries;var fluent=new ResourceDictionary{Source=new Uri("pack://application:,,,/PresentationFramework.Fluent;component/Themes/Fluent."+(light?"Light":"Dark")+".xaml")};if(dictionaries.Count==0)dictionaries.Add(fluent);else dictionaries[0]=fluent;
  resources["Ink"]=contrast?SystemColors.WindowTextBrush:Brush(light?"#1B1B1B":"#F3F3F3");resources["SecondaryInk"]=contrast?SystemColors.WindowTextBrush:Brush(light?"#606060":"#BCBEBE");
  resources["BorderLine"]=contrast?SystemColors.WindowTextBrush:Brush("#20808080");resources["TileBrush"]=contrast?SystemColors.ControlBrush:Brush(light?"#A0FFFFFF":"#18FFFFFF");resources["SurfaceBrush"]=contrast?SystemColors.WindowBrush:Brush(light?"#40FFFFFF":"#0C000000");
  resources["Accent"]=new SolidColorBrush(accent);resources["AccentInk"]=.2126*accent.R+.7152*accent.G+.0722*accent.B>145?Brushes.Black:Brushes.White;
  foreach(var item in new[]{(window:(Window)this,border:surface),(window:panel,border:panelSurface)}){
   if(item.window==null||item.border==null)continue;var hwnd=new WindowInteropHelper(item.window).Handle;if(hwnd==IntPtr.Zero)continue;
   int dark=light?0:1,corner=2;DwmSetWindowAttribute(hwnd,20,ref dark,4);DwmSetWindowAttribute(hwnd,33,ref corner,4);item.border.Background=NativeMaterial.Apply(item.window,HwndSource.FromHwnd(hwnd),item.window==panel&&selected==0?1:material,light,transparency,contrast);
  }
  error.Foreground=contrast?SystemColors.WindowTextBrush:new SolidColorBrush(light?Color.FromRgb(170,40,20):Color.FromRgb(255,188,171));
  bool taskbarLight=(int)(Registry.GetValue(key,"SystemUsesLightTheme",1)??1)!=0;
  bool lightBackground=contrast?(SystemColors.WindowColor.R+SystemColors.WindowColor.G+SystemColors.WindowColor.B)>384:taskbarLight;
  tray?.UpdateIcon(Path.Combine(AppContext.BaseDirectory,"Assets",(contrast?"Tray-hc-":"Tray-")+(lightBackground?"light":"dark")+".ico"));
  UpdatePin();
 }
 static SolidColorBrush Brush(string value)=>new((Color)ColorConverter.ConvertFromString(value));
 void UpdatePin(){Topmost=prefs["alwaysOnTop"]?.GetValue<bool>()??false;if(panel!=null)panel.Topmost=Topmost;if(Pinned)pin.SetResourceReference(BackgroundProperty,"Accent");else pin.Background=Brushes.Transparent;pin.SetResourceReference(ForegroundProperty,Pinned?"AccentInk":"Ink");}
 public void ShowWidget(){SuiteActivation.Claim();reveal?.Dispose();animating=false;Show();WindowState=WindowState.Normal;Position();appearanceSignature="";ApplyAppearance();Activate();Touch();Reveal(this,true);}
 void TogglePanel(){Touch();if(panel?.IsVisible==true)ClosePanel();else OpenPanel(false);}
 void OpenPanel(bool settings){if(panel==null)return;SuiteActivation.Claim();Touch();panelReveal?.Dispose();panel.Show();Position();appearanceSignature="";ApplyAppearance();if(settings&&panel.Tag is ComboBox choice)choice.SelectedIndex=4;panel.Activate();Refresh();Reveal(panel,true);expand.SetResourceReference(BackgroundProperty,"Accent");expand.SetResourceReference(ForegroundProperty,"AccentInk");}
 void ClosePanel(){if(panel?.IsVisible!=true)return;Reveal(panel,false,()=>{panel.Hide();Position();if(IsVisible&&!animating)Activate();});expand.Background=Brushes.Transparent;expand.SetResourceReference(ForegroundProperty,"Ink");Touch();}
 void HideTogether(){if(tray==null&&!verify){ShowInTaskbar=true;WindowState=WindowState.Minimized;return;}if(animating)return;ClosePanel();if(!IsVisible)return;animating=true;Reveal(this,false,()=>{Hide();animating=false;});}
 void Reveal(Window window,bool opening,Action? completed=null){
  if(window==this){reveal?.Dispose();reveal=null;}else{panelReveal?.Dispose();panelReveal=null;}
  if(!Animations){completed?.Invoke();return;}
  var animation=new WindowRevealAnimation(window,opening,()=>completed?.Invoke());if(window==this)reveal=animation;else panelReveal=animation;
 }
 void TrayMenu(){Touch();var menu=new ContextMenu{Placement=PlacementMode.MousePoint};SuiteActivation.MenuOpen=true;menu.Closed+=(_,_)=>SuiteActivation.MenuOpen=false;var open=new MenuItem{Header=Locale.Text(IsVisible?"Recolher widget":"Abrir widget")};open.Click+=(_,_)=>{if(IsVisible)HideTogether();else ShowWidget();};menu.Items.Add(open);var details=new MenuItem{Header=Locale.Text("Configurações")};details.Click+=(_,_)=>{ShowWidget();OpenPanel(true);};menu.Items.Add(details);menu.Items.Add(new Separator());var exit=new MenuItem{Header=Locale.Text("Sair do Google Photos Uploader")};exit.Click+=(_,_)=>Exit();menu.Items.Add(exit);menu.IsOpen=true;}
 public void RequestExit()=>Exit();
 void Exit(){DisposeAccessibility();Command("shutdown");exiting=true;timer.Stop();reveal?.Dispose();panelReveal?.Dispose();tray?.Dispose();panel?.Close();SystemEvents.DisplaySettingsChanged-=DisplayChanged;SystemEvents.UserPreferenceChanged-=PreferenceChanged;Application.Current.Shutdown();}
 void DisplayChanged(object? sender,EventArgs e)=>Dispatcher.BeginInvoke(Position);
 void PreferenceChanged(object sender,UserPreferenceChangedEventArgs e)=>Dispatcher.BeginInvoke(()=>{appearanceSignature="";ApplyAppearance();});
 void Position(){
  if(source==null)return;var monitor=MonitorFromWindow(source.Handle,2);var info=new MonitorInfo{Size=Marshal.SizeOf<MonitorInfo>()};if(!GetMonitorInfo(monitor,ref info))return;
  var dpi=VisualTreeHelper.GetDpi(this);double sw=(info.Work.Right-info.Work.Left)/dpi.DpiScaleX,sh=(info.Work.Bottom-info.Work.Top)/dpi.DpiScaleY;
  double margin=Math.Min(12,Math.Min(sw,sh)/10);var fit=SuiteWindow.Fit(sw,sh);Width=fit.Width;Height=fit.Height;UpdateLayout();
  int w=(int)Math.Round(Width*dpi.DpiScaleX),h=(int)Math.Round(Height*dpi.DpiScaleY),gap=(int)Math.Round(margin*dpi.DpiScaleY),right=info.Work.Right-(int)Math.Round(margin*dpi.DpiScaleX),bottom=info.Work.Bottom-gap;
  SetWindowPos(source.Handle,IntPtr.Zero,right-w,bottom-h,w,h,0x14);
  if(panel?.IsVisible==true){SuitePlacement.PrepareWidget(this);SuitePlacement.Above(this,panel);}
 }
 async Task VerifyAsync(){
  bool passed=false;Directory.CreateDirectory(Paths.Data);
  try{
   var checks=new Dictionary<string,bool>();TestLocalConfiguration();checks["LocalDiagnostics"]=diagnosticDetails.Contains(Locale.Text("Este teste não envia arquivos. Teste o Google Fotos separadamente."));checks["SettingsTitle"]=panel?.Title==Locale.Text("Google Photos Uploader · Configurações");Position();OpenPanel(false);await Task.Delay(350);if(panel?.Tag is ComboBox configChoice){configChoice.SelectedIndex=4;panel.UpdateLayout();panelScroll!.ScrollToTop();panel.UpdateLayout();panelScroll.ScrollToEnd();panel.UpdateLayout();checks["SettingsBottomReachable"]=Math.Abs(panelScroll.VerticalOffset-panelScroll.ScrollableHeight)<1;panelScroll.ScrollToTop();panel.UpdateLayout();checks["NoHorizontalSettingsScroll"]=panelScroll.ScrollableWidth<1;}if(Environment.GetCommandLineArgs().Contains("--inspect"))await Task.Delay(60000);
   GetWindowRect(source!.Handle,out var wr);GetWindowRect(new WindowInteropHelper(panel!).Handle,out var pr);
   checks["RightAligned"]=wr.Right==pr.Right&&wr.Left==pr.Left;checks["PanelExpandedAbove"]=SuitePlacement.IsAbove(this,panel);
   checks["LargeLastPhoto"]=string.IsNullOrWhiteSpace(Read(Path.Combine(Paths.Data,"current_status.json"))["last_uploaded_file"]?.ToString())?photo.Source==null:photo.Source!=null&&photo.ActualHeight>=150;checks["PendingPreserved"]=pending.Text==Locale.Format("{0} na fila",Read(Path.Combine(Paths.Data,"current_status.json"))["pending_files"]?.GetValue<int>()??0);
   double savedScale=textScale;foreach(double scale in new[]{1.0,1.5,2.0}){ApplyTextScaleFactor(scale);UpdateLayout();panel!.UpdateLayout();bool consistent=true;foreach(var border in new[]{surface,panelSurface})if(border?.Child is Grid rootGrid){var header=(FrameworkElement)rootGrid.Children[0];consistent&=Math.Abs(header.ActualHeight-rootGrid.RowDefinitions[0].ActualHeight)<1&&Math.Abs(header.ActualHeight-SuiteChrome.HeaderHeight*scale)<1;}checks["TextScaleHeader"+scale.ToString(System.Globalization.CultureInfo.InvariantCulture)]=consistent;}ApplyTextScaleFactor(savedScale);
   var original=prefs.DeepClone();foreach(int material in new[]{1,2,3}){prefs["material"]=material;appearanceSignature="";ApplyAppearance();checks["Material"+material]=surface.Background!=null&&panelSurface!.Background!=null;}
   foreach(int theme in new[]{0,1,2}){prefs["theme"]=theme;appearanceSignature="";ApplyAppearance();checks["Theme"+theme]=Application.Current.Resources["Ink"] is SolidColorBrush;if(theme>0){foreach(var capture in new[]{(window:(Window)this,border:surface,name:"widget"),(window:panel!,border:panelSurface!,name:"settings")}){capture.border.Background=Brush(theme==1?"#F3F3F3":"#202020");capture.window.UpdateLayout();var dpi=VisualTreeHelper.GetDpi(capture.window);var bitmap=new RenderTargetBitmap((int)(capture.window.ActualWidth*dpi.DpiScaleX),(int)(capture.window.ActualHeight*dpi.DpiScaleY),96*dpi.DpiScaleX,96*dpi.DpiScaleY,PixelFormats.Pbgra32);bitmap.Render(capture.window);var encoder=new PngBitmapEncoder();encoder.Frames.Add(BitmapFrame.Create(bitmap));using var imageFile=File.Create(Path.Combine(Paths.Data,capture.name+"-theme-"+theme+".png"));encoder.Save(imageFile);}}}
   prefs=(JsonObject)original;appearanceSignature="";ApplyAppearance();ClosePanel();await Task.Delay(400);checks["AnimatedPanelClose"]=!panel!.IsVisible;HideTogether();await Task.Delay(400);checks["AnimatedWidgetClose"]=!IsVisible;ShowWidget();await Task.Delay(400);checks["Reopen"]=IsVisible;checks["CultureFlow"]=FlowDirection==(Locale.Culture.TextInfo.IsRightToLeft?FlowDirection.RightToLeft:FlowDirection.LeftToRight);checks["KnownFolders"]=KnownFolders.Media().Any();checks["SetupSection"]=panel.Tag is ComboBox sections && sections.Items.Count==5;
   bool originalPinned=Pinned;prefs["pinned"]=true;UpdatePin();OpenPanel(false);await Task.Delay(350);minimize.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));await Task.Delay(900);checks["MinimizeWhilePinned"]=!IsVisible;checks["MinimizeAlsoHidesSettings"]=!panel.IsVisible;checks["MinimizeAccessibleName"]=System.Windows.Automation.AutomationProperties.GetName(minimize)==Locale.Text("Minimizar para a bandeja");prefs["pinned"]=originalPinned;ShowWidget();UpdatePin();checks["ReopenAfterMinimize"]=IsVisible;
   passed=checks.Values.All(v=>v);string report=Environment.GetCommandLineArgs().FirstOrDefault(a=>a.StartsWith("--report="))?[9..]??Path.Combine(Paths.Data,"native-verification.json");File.WriteAllText(report,JsonSerializer.Serialize(new{At=DateTimeOffset.Now,Culture=Locale.Culture.Name,EffectiveLanguage=Locale.EffectiveLanguage,Flow=FlowDirection.ToString(),Backdrop=NativeMaterial.LastMode,Checks=checks,Passed=passed,Widget=wr,Panel=pr},new JsonSerializerOptions{WriteIndented=true,IncludeFields=true}));
  }catch(Exception ex){File.WriteAllText(Path.Combine(Paths.Data,"native-verification.json"),JsonSerializer.Serialize(new{Passed=false,Error=ex.ToString()},new JsonSerializerOptions{WriteIndented=true}));}finally{exiting=true;timer.Stop();panel?.Close();Application.Current.Shutdown(passed?0:1);}
 }
 [StructLayout(LayoutKind.Sequential)]public struct Rect{public int Left,Top,Right,Bottom;}
 [StructLayout(LayoutKind.Sequential)]struct MonitorInfo{public int Size;public Rect Monitor,Work;public uint Flags;}
 [DllImport("user32.dll")]static extern IntPtr MonitorFromWindow(IntPtr hwnd,uint flags);
 [DllImport("user32.dll",CharSet=CharSet.Auto)]static extern bool GetMonitorInfo(IntPtr monitor,ref MonitorInfo info);
 [DllImport("user32.dll")]static extern bool SetWindowPos(IntPtr h,IntPtr after,int x,int y,int w,int height,uint flags);
 [DllImport("user32.dll")]static extern bool GetWindowRect(IntPtr h,out Rect r);
 [DllImport("user32.dll")]static extern bool IsWindowVisible(IntPtr h);
 [DllImport("dwmapi.dll")]static extern int DwmSetWindowAttribute(IntPtr hwnd,int attribute,ref int value,int size);
}

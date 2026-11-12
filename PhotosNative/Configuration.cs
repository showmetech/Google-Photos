using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using Microsoft.Win32;
namespace PhotosNative;
public partial class MainWindow {
 readonly ObservableCollection<string> chosenSources=new();
 readonly TextBlock accountInfo=new(),configurationInfo=new();
 Control? importClient;
 readonly TextBlock diagnosticResult=new(){TextWrapping=TextWrapping.Wrap,FontSize=12,Margin=new(0,8,0,12)},startupInfo=new(){TextWrapping=TextWrapping.Wrap,FontSize=12};
 CheckBox? startupToggle;
 string diagnosticDetails="";
 Button? connectAccount;
 CheckBox? syncToggle;
 readonly List<Button> settingsOperations=new();
 StackPanel? configurationRoot;
 readonly List<StackPanel> configurationPages=new();
 readonly List<Button> configurationTabs=new();
 int configurationPage;
 StackPanel BuildConfiguration(){
  var section=new StackPanel();configurationRoot=section;var cfg=Read(Path.Combine(Paths.Home,"config.json"));
  var saved=cfg["photos_roots"] as JsonArray;
  foreach(string path in saved?.Select(v=>v?.ToString()??"")??new[]{cfg["photos_root"]?.ToString()??""})if(path.Length>0)chosenSources.Add(path);
  if(chosenSources.Count==0)foreach(string path in KnownFolders.Media())chosenSources.Add(path);
  var navigation=new System.Windows.Controls.Primitives.UniformGrid{Columns=4,Margin=new(0,0,0,12)};section.Children.Add(navigation);
  var pages=new StackPanel();section.Children.Add(pages);
  foreach(var entry in new[]{("Pastas","\uE8B7"),("Conta","\uE77B"),("Sincronização","\uE895"),("Windows","\uE770")}){
   int index=configurationPages.Count;var page=new StackPanel{Visibility=index==0?Visibility.Visible:Visibility.Collapsed};configurationPages.Add(page);pages.Children.Add(page);
   var label=new StackPanel{HorizontalAlignment=HorizontalAlignment.Center};label.Children.Add(new TextBlock{Text=entry.Item2,FontFamily=new("Segoe Fluent Icons"),FontSize=18,HorizontalAlignment=HorizontalAlignment.Center,Margin=new(0,0,0,4)});label.Children.Add(new TextBlock{Text=Locale.Text(entry.Item1=="Sincronização"?"Envios":entry.Item1),FontSize=11,HorizontalAlignment=HorizontalAlignment.Center});
   var tab=new Button{Content=label,MinHeight=52,Padding=new(4),Margin=new(0,0,index==3?0:4,0),ToolTip=Locale.Text(entry.Item1)};AutomationProperties.SetName(tab,Locale.Text(entry.Item1));tab.Click+=(_,_)=>SelectConfigurationPage(index);configurationTabs.Add(tab);navigation.Children.Add(tab);
  }
  SelectConfigurationPage(0);
  var folders=SettingsCard(configurationPages[0],"\uE8B7","Pastas",out var folderHead);
  var list=new ListBox{ItemsSource=chosenSources,Height=80,HorizontalContentAlignment=HorizontalAlignment.Stretch,FlowDirection=FlowDirection.LeftToRight,Margin=new(0,8,0,8)};
  ScrollViewer.SetHorizontalScrollBarVisibility(list,ScrollBarVisibility.Disabled);AutomationProperties.SetName(list,Locale.Text("Pastas de fotos e vídeos"));
  var factory=new FrameworkElementFactory(typeof(TextBlock));factory.SetBinding(TextBlock.TextProperty,new System.Windows.Data.Binding());factory.SetBinding(TextBlock.ToolTipProperty,new System.Windows.Data.Binding());factory.SetValue(TextBlock.TextTrimmingProperty,TextTrimming.CharacterEllipsis);factory.SetValue(TextBlock.FontSizeProperty,12d);list.ItemTemplate=new DataTemplate{VisualTree=factory};folders.Children.Add(list);
  var folderMore=MenuButton("Mais opções de pastas",()=>{
   var menu=NewSettingsMenu();AddMenu(menu,"Remover seleção",()=>{if(list.SelectedItem is string path)chosenSources.Remove(path);},list.SelectedItem!=null);
   AddMenu(menu,"Detectar Imagens e Vídeos do Windows",()=>{chosenSources.Clear();foreach(string path in KnownFolders.Media())chosenSources.Add(path);});
   AddMenu(menu,"Ver caminhos completos",()=>ShowSettingsDetails("Pastas de fotos e vídeos",string.Join("\n\n",chosenSources)));
   AddMenu(menu,"Abrir pasta selecionada",()=>{if(list.SelectedItem is string path)OpenLocal(path);},list.SelectedItem!=null);return menu;
  });DockPanel.SetDock(folderMore,Dock.Right);folderHead.Children.Insert(0,folderMore);
  var add=SettingsAction("\uE710","Adicionar",()=>{var dialog=new OpenFolderDialog{Title=Locale.Text("Escolha uma pasta"),Multiselect=true};if(dialog.ShowDialog(panel)==true)foreach(string folder in dialog.FolderNames)if(!chosenSources.Contains(folder))chosenSources.Add(folder);});
  var save=SettingsAction("\uE74E","Salvar pastas",()=>Send(new{command="configure",folders=chosenSources.ToArray()}));save.ToolTip=Locale.Text("Salvar origens e pausar automático");folders.Children.Add(ActionPair(add,save));
  folders.Children.Add(SettingsCaption("Alterar as pastas pausa o automático."));
  var account=SettingsCard(configurationPages[1],"\uE77B","Conta",out var accountHead);
  var accountMore=MenuButton("Mais opções da conta",()=>{
   var menu=NewSettingsMenu();importClient=AddMenu(menu,"Importar cliente OAuth do Google…",ImportOAuthClient,!(Read(Path.Combine(Paths.Data,"ui-service-status.json"))["account_configured"]?.GetValue<bool>()??false));
   AddMenu(menu,"Guia oficial de autorização",()=>Process.Start(new ProcessStartInfo("https://developers.google.com/photos/overview/authorization"){UseShellExecute=true}));
   AddMenu(menu,"Abrir Google Fotos",()=>Process.Start(new ProcessStartInfo("https://photos.google.com/"){UseShellExecute=true}));return menu;
  });DockPanel.SetDock(accountMore,Dock.Right);accountHead.Children.Insert(0,accountMore);
  accountInfo.TextWrapping=TextWrapping.Wrap;accountInfo.FontSize=12;accountInfo.Margin=new(0,4,0,8);accountInfo.SetResourceReference(TextBlock.ForegroundProperty,"SecondaryInk");account.Children.Add(accountInfo);
  var connect=SettingsAction("\uE8A7","Conectar",()=>Command("connect"));connect.ToolTip=Locale.Text("Conectar ou reconectar no navegador");connectAccount=connect;settingsOperations.Add(connect);
  var test=SettingsAction("\uE73E","Testar acesso",()=>Command("doctor"));test.ToolTip=Locale.Text("Testar acesso ao Google Fotos");settingsOperations.Add(test);account.Children.Add(ActionPair(connect,test));
  var syncCard=SettingsCard(configurationPages[2],"\uE895","Sincronização",out var syncHead);
  var online=MenuButton("Conferência online",()=>{
   var menu=NewSettingsMenu();bool idle=!(Read(Path.Combine(Paths.Data,"ui-service-status.json"))["busy"]?.GetValue<bool>()??false);
   AddMenu(menu,"Comparar pastas com álbuns online",()=>Command("reconcile"),idle);
   AddMenu(menu,"Abrir relatório da conferência",()=>OpenLocal(Path.Combine(Paths.Home,"audit","online-reconciliation.html")),File.Exists(Path.Combine(Paths.Home,"audit","online-reconciliation.html")));
   AddMenu(menu,"Importar inventário do histórico…",()=>{var file=new OpenFileDialog{Title=Locale.Text("Importar inventário do histórico…"),Filter="JSON (*.json)|*.json",CheckFileExists=true};if(file.ShowDialog(panel)==true)Send(new{command="reconcile",inventory=file.FileName});},idle);
   var comparison=Read(Path.Combine(Paths.Data,"online-reconciliation-summary.json"));
   AddMenu(menu,"Reenviar ausências comprovadas",()=>Command("repair-online"),idle&&(comparison["repair_candidates"]?.GetValue<int>()??0)>0);
   AddMenu(menu,"Limites da conferência",()=>ShowSettingsDetails("Conferência online",Locale.Text("A API só permite consultar conteúdo criado por este cliente. Histórico não visível não significa ausente. Nomes e contagens não comprovam integridade binária. Só itens anteriormente observados por ID, com recibo local inalterado e ausência confirmada em consulta completa, podem ser reenviados. Outros casos precisam de conferência no Google Fotos.")));
   return menu;
  });DockPanel.SetDock(online,Dock.Right);syncHead.Children.Insert(0,online);
  var results=SettingsIcon("\uE9D9","Resultado do último teste",()=>ShowSettingsDetails("Resultado do último teste",diagnosticDetails.Length>0?diagnosticDetails:diagnosticResult.Text.Length>0?diagnosticResult.Text:Locale.Text("Nenhum teste realizado nesta tela.")));DockPanel.SetDock(results,Dock.Right);syncHead.Children.Insert(0,results);
  syncToggle=new CheckBox{Content=Locale.Text("Sincronização automática"),Margin=new(0,6,0,0),FontSize=13};syncToggle.Click+=(_,_)=>Command("automatic",syncToggle.IsChecked==true);syncCard.Children.Add(syncToggle);
  syncCard.Children.Add(SettingsCaption("Novos arquivos · a cada 15 minutos"));
  var scan=SettingsAction("\uE721","Verificar",()=>Command("scan"));scan.ToolTip=Locale.Text("Verificar arquivos sem enviar");settingsOperations.Add(scan);settingsOperations.Add(save);
  var local=SettingsAction("\uE9D9","Testes locais",TestLocalConfiguration);local.ToolTip=Locale.Text("Testar pastas e monitor local");syncCard.Children.Add(ActionPair(scan,local));
  diagnosticResult.Margin=new(0,6,0,0);diagnosticResult.MaxHeight=36;diagnosticResult.TextTrimming=TextTrimming.CharacterEllipsis;diagnosticResult.SetResourceReference(TextBlock.ForegroundProperty,"SecondaryInk");diagnosticResult.ToolTip=Locale.Text("Abra o resultado pelo botão de detalhes.");syncCard.Children.Add(diagnosticResult);
  var windows=SettingsCard(configurationPages[3],"\uE770","Windows",out var windowsHead);
  var startupSettings=SettingsIcon("\uE8A7","Abrir aplicativos de inicialização do Windows",()=>Process.Start(new ProcessStartInfo("ms-settings:startupapps"){UseShellExecute=true}));DockPanel.SetDock(startupSettings,Dock.Right);windowsHead.Children.Insert(0,startupSettings);
  startupToggle=new CheckBox{Content=Locale.Text("Iniciar com o Windows"),Margin=new(0,6,0,4),FontSize=13};
  startupToggle.Click+=(_,_)=>{if(verify)return;try{WindowsStartup.SetEnabled(startupToggle.IsChecked==true);RefreshStartup();}catch(Exception ex){diagnosticResult.Text=ex.Message;RefreshStartup();}};windows.Children.Add(startupToggle);
  startupInfo.TextWrapping=TextWrapping.Wrap;startupInfo.FontSize=12;startupInfo.SetResourceReference(TextBlock.ForegroundProperty,"SecondaryInk");windows.Children.Add(startupInfo);
  var advanced=SettingsAction("\uE713","Avançado",()=>{
   var menu=NewSettingsMenu();AddMenu(menu,"Declarar que o acervo atual já está online…",DeclareExistingLibrary);
   AddMenu(menu,"Abrir recibos de operações",()=>OpenLocal(Path.Combine(Paths.Data,"ui-receipts")));
   AddMenu(menu,"Abrir logs",()=>OpenLocal(Path.Combine(Paths.Home,"logs")));
   AddMenu(menu,"Abrir dados locais",()=>OpenLocal(Paths.Home));
   AddMenu(menu,"Sobre e configuração atual",()=>ShowSettingsDetails("Sobre e configuração atual",configurationInfo.Text+"\n\n"+Locale.Text("Somente arquivos novos ou modificados. Nenhum original é apagado.")));menu.PlacementTarget=panel;menu.Placement=System.Windows.Controls.Primitives.PlacementMode.MousePoint;menu.IsOpen=true;
  });advanced.HorizontalAlignment=HorizontalAlignment.Stretch;advanced.Margin=new(0,0,0,4);section.Children.Add(advanced);
  return section;
 }
 void SelectConfigurationPage(int index){configurationPage=index;for(int i=0;i<configurationPages.Count;i++){configurationPages[i].Visibility=i==index?Visibility.Visible:Visibility.Collapsed;configurationTabs[i].SetResourceReference(BackgroundProperty,i==index?"Accent":"TileBrush");configurationTabs[i].SetResourceReference(ForegroundProperty,i==index?"AccentInk":"Ink");AutomationProperties.SetHelpText(configurationTabs[i],Locale.Text(i==index?"Seção selecionada":"Abrir seção"));}Touch();}
 static TextBlock SettingsCaption(string value){var text=Text(value,12,false,"SecondaryInk",new(0,4,0,4));return text;}
 StackPanel SettingsCard(StackPanel parent,string glyph,string title,out DockPanel header){
  var body=new StackPanel();header=new DockPanel{LastChildFill=true};var heading=new StackPanel{Orientation=Orientation.Horizontal};heading.Children.Add(new TextBlock{Text=glyph,FontFamily=new("Segoe Fluent Icons"),FontSize=16,VerticalAlignment=VerticalAlignment.Center,Margin=new(0,0,8,0)});heading.Children.Add(Text(title,14,true));header.Children.Add(heading);body.Children.Add(header);
  var card=new Border{CornerRadius=new(8),Padding=new(12,8,12,10),Margin=new(0,0,0,8),Child=body};card.SetResourceReference(Border.BackgroundProperty,"TileBrush");parent.Children.Add(card);return body;
 }
 Button SettingsAction(string glyph,string title,Action action){
  var content=new StackPanel{Orientation=Orientation.Horizontal,HorizontalAlignment=HorizontalAlignment.Center};content.Children.Add(new TextBlock{Text=glyph,FontFamily=new("Segoe Fluent Icons"),FontSize=14,VerticalAlignment=VerticalAlignment.Center,Margin=new(0,0,6,0)});content.Children.Add(new TextBlock{Text=Locale.Text(title),FontSize=12,VerticalAlignment=VerticalAlignment.Center});
  var button=new Button{Content=content,MinHeight=32,Padding=new(8,4,8,4),HorizontalContentAlignment=HorizontalAlignment.Center,ToolTip=Locale.Text(title)};button.SetResourceReference(BackgroundProperty,"TileBrush");AutomationProperties.SetName(button,Locale.Text(title));button.Click+=(_,_)=>{Touch();action();};return button;
 }
 Button SettingsIcon(string glyph,string label,Action action){var button=new Button();SetIcon(button,glyph,label,(_,_)=>{Touch();action();});button.Margin=new(4,0,0,0);return button;}
 static Grid ActionPair(Button first,Button second){var row=new Grid();row.ColumnDefinitions.Add(new());row.ColumnDefinitions.Add(new(){Width=new GridLength(8)});row.ColumnDefinitions.Add(new());row.Children.Add(first);Grid.SetColumn(second,2);row.Children.Add(second);return row;}
 Button MenuButton(string label,Func<ContextMenu> build){Button? button=null;button=SettingsIcon("\uE712",label,()=>{var menu=build();menu.PlacementTarget=button;menu.IsOpen=true;});return button;}
 System.Windows.Media.Brush SettingsPopupBrush(){if(SystemParameters.HighContrast)return SystemColors.WindowBrush;bool dark=((System.Windows.Media.SolidColorBrush)FindResource("Ink")).Color.R>128;return new System.Windows.Media.SolidColorBrush(dark?System.Windows.Media.Color.FromRgb(32,32,32):System.Windows.Media.Color.FromRgb(249,249,249));}
 ContextMenu NewSettingsMenu(){var menu=new ContextMenu{Background=SettingsPopupBrush(),BorderThickness=new(1),Padding=new(4),MinWidth=220,UseLayoutRounding=true};menu.SetResourceReference(ForegroundProperty,"Ink");menu.SetResourceReference(BorderBrushProperty,"BorderLine");return menu;}
 static MenuItem AddMenu(ContextMenu menu,string label,Action action,bool enabled=true){var item=new MenuItem{Header=Locale.Text(label),IsEnabled=enabled};AutomationProperties.SetName(item,Locale.Text(label));item.Click+=(_,_)=>action();menu.Items.Add(item);return item;}
 void ImportOAuthClient(){var file=new OpenFileDialog{Title=Locale.Text("Importar cliente OAuth do Google…"),Filter="Google OAuth JSON (*.json)|*.json",CheckFileExists=true};if(file.ShowDialog(panel)==true)Send(new{command="import-client",file=file.FileName});}
 void DeclareExistingLibrary(){if(MessageBox.Show(panel,Locale.Text("Isso registra somente sua declaração. Não confere fotos online e evita enviar o acervo atual. Apenas arquivos novos ou alterados serão enviados depois. Confirma que todas as mídias dessas origens já estão no Google Fotos?"),"Google Photos Uploader",MessageBoxButton.YesNo,MessageBoxImage.Question)==MessageBoxResult.Yes)Send(new{command="mark-baseline",confirmed_existing=true});}
 void ShowSettingsDetails(string title,string body){
  var dialog=new Window{Title=Locale.Text(title),Owner=panel,Width=440,Height=380,MinWidth=320,MinHeight=240,WindowStartupLocation=WindowStartupLocation.CenterOwner,ShowInTaskbar=false,FontFamily=FontFamily,FontSize=14,ResizeMode=ResizeMode.CanResize};dialog.Background=SettingsPopupBrush();dialog.SetResourceReference(ForegroundProperty,"Ink");Locale.Apply(dialog);
  var layout=new DockPanel{Margin=new(16)};var close=new Button{Content=Locale.Text("Fechar"),IsCancel=true,MinWidth=100,MinHeight=32,HorizontalAlignment=HorizontalAlignment.Right,Margin=new(0,12,0,0)};close.Click+=(_,_)=>dialog.Close();DockPanel.SetDock(close,Dock.Bottom);layout.Children.Add(close);
  var text=new TextBox{Text=body,IsReadOnly=true,TextWrapping=TextWrapping.Wrap,VerticalScrollBarVisibility=ScrollBarVisibility.Auto,HorizontalScrollBarVisibility=ScrollBarVisibility.Disabled,BorderThickness=new(0),Background=System.Windows.Media.Brushes.Transparent,FontSize=13};AutomationProperties.SetName(text,Locale.Text(title));layout.Children.Add(text);dialog.Content=layout;dialog.ShowDialog();
 }
 void UpdateConfiguration(JsonObject cfg,JsonObject worker){
  bool connected=worker["account_configured"]?.GetValue<bool>()??false;bool busy=worker["busy"]?.GetValue<bool>()??false;
  accountInfo.Text=Locale.Text(connected?"Autorização salva neste usuário.":"Conta ainda não conectada.");accountInfo.ToolTip=Locale.Text("O teste confirma o acesso à API. A conta é a que você escolheu na tela de autorização do Google.");
  if(importClient!=null)importClient.IsEnabled=!connected&&!busy;
  if(syncToggle!=null){syncToggle.IsChecked=cfg["auto_monitor_enabled"]?.GetValue<bool>()??false;syncToggle.IsEnabled=!busy;}
  foreach(var button in settingsOperations)button.IsEnabled=!busy;
  if(connectAccount?.Content is StackPanel connectContent && connectContent.Children.OfType<TextBlock>().LastOrDefault() is TextBlock connectLabel){connectLabel.Text=Locale.Text(connected?"Reconectar":"Conectar");AutomationProperties.SetName(connectAccount,connectLabel.Text);}
  RefreshStartup();
  if(!busy&&worker["operation"]?.ToString() is "reconcile" or "repair-online"){
   var report=Read(Path.Combine(Paths.Data,"online-reconciliation-summary.json"));var evidence=report["counts"] as JsonObject;
   int verified=evidence?["receipt_and_online"]?.GetValue<int>()??0;int total=report["local_files"]?.GetValue<int>()??0;
   diagnosticResult.Text=Locale.Format("Online conferido: {0} · Ainda sem comprovação: {1}",verified,Math.Max(0,total-verified));
   diagnosticDetails=diagnosticResult.Text+"\n\n"+Locale.Text("A API não permite conferir todo o histórico. Abra o relatório da conferência.");
  }
  configurationInfo.Text=Locale.Format("Dados locais: {0}\nWindows: {1} · App: {2}\nIdioma da interface: {3}",Paths.Home,RuntimeInformation.OSArchitecture,RuntimeInformation.ProcessArchitecture,Locale.EffectiveLanguage);
 }
 void RefreshStartup(){
  if(startupToggle==null)return;var state=WindowsStartup.Read();startupToggle.IsChecked=state.Registered&&state.Disabled!=true;
  startupToggle.IsEnabled=state.Available;startupInfo.Text=Locale.Text(!state.Available?"Inicialização indisponível por permissão ou política do Windows.":!state.Registered?"Não cadastrado na inicialização.":state.Disabled==true?"Desativado no Windows. Abra a lista para ativar.":"Registrado para iniciar na bandeja.");
 }
 void TestLocalConfiguration(){
  var cfg=Read(Path.Combine(Paths.Home,"config.json"));var worker=Read(Path.Combine(Paths.Data,"ui-service-status.json"));var results=new List<string>();bool healthy=true;
  var roots=cfg["photos_roots"] as JsonArray;var folders=roots?.Select(p=>p?.ToString()??"").ToArray()??new[]{cfg["photos_root"]?.ToString()??""};
  foreach(var folder in folders){bool readable=false;try{if(Directory.Exists(folder)){using var entries=Directory.EnumerateFileSystemEntries(folder).GetEnumerator();entries.MoveNext();readable=true;}}catch(IOException){}catch(UnauthorizedAccessException){}healthy&=readable;results.Add(Locale.Text(readable?"Pasta acessível: ":"Pasta indisponível: ")+folder);}
  double age=DateTimeOffset.UtcNow.ToUnixTimeSeconds()-(worker["heartbeat"]?.GetValue<double>()??0);healthy&=age<15;results.Add(Locale.Text(age<15?"Monitor local respondendo.":"Monitor local sem resposta recente."));
  try{var test=Path.Combine(Paths.Data,"write-test-"+Guid.NewGuid().ToString("N")+".tmp");File.WriteAllText(test,"test");File.Delete(test);results.Add(Locale.Text("Gravação dos dados locais: OK."));}catch(Exception ex) when(ex is IOException or UnauthorizedAccessException){healthy=false;results.Add(Locale.Text("Falha ao gravar os dados locais."));}
  bool componentFound=File.Exists(Path.Combine(Paths.Root,"tools","rclone","rclone.exe"));healthy&=componentFound;results.Add(Locale.Text(componentFound?"Componente de envio encontrado.":"Componente de envio ausente."));
  results.Add(Locale.Text("Este teste não envia arquivos. Teste o Google Fotos separadamente."));diagnosticDetails=string.Join("\n",results);diagnosticResult.Text=Locale.Text(healthy?"Pastas e monitor: OK":"Há itens que precisam de atenção.");RefreshStartup();
 }
 void Send(object request){
  if(verify)return;diagnosticDetails="";lastReceipt="";string id=Guid.NewGuid().ToString("N");string dir=Path.Combine(Paths.Data,"ui-commands");Directory.CreateDirectory(dir);
  string target=Path.Combine(dir,id+".json");File.WriteAllText(target+".tmp",JsonSerializer.Serialize(request));File.Move(target+".tmp",target);outstanding.Add(id);Touch();
 }
}

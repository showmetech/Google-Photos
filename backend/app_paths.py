"""Per-user state, independent of the installation path and Windows language."""
import json,os
from pathlib import Path
CODE=Path(__file__).resolve().parent
DEFAULT_HOME=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData'/'Local')))/'GooglePhotosUploader'
def home():
    override=os.environ.get('GOOGLE_PHOTOS_HOME')
    if override:return Path(override).expanduser().resolve()
    if (DEFAULT_HOME/'config.json').exists():return DEFAULT_HOME
    if (CODE/'config.json').exists():return CODE  # Existing installations migrate transactionally.
    return DEFAULT_HOME
def bootstrap():
    from reliable_history import atomic_json
    target=home();target.mkdir(parents=True,exist_ok=True)
    for name in ('data','audit','logs'):(target/name).mkdir(exist_ok=True)
    cfg_path=target/'config.json'
    if not cfg_path.exists():
        cfg=json.loads((CODE/'config.example.json').read_text(encoding='utf-8-sig'))
        cfg.update(photos_root='',photos_roots=[],auto_monitor_enabled=False)
        cfg['rclone_config']=str(target/'data'/'rclone.conf')
        atomic_json(cfg_path,cfg)
    return target

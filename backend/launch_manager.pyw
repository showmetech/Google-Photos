"""Launch and supervise the native widget independently of Codex."""
from pathlib import Path
import sys
from ui_supervisor import main
raise SystemExit(main(Path(__file__).resolve().parent, sys.argv[1:]))

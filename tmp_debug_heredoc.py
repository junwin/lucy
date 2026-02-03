from src.config_manager import ConfigManager
from src.handlers.command_execution_handler2 import CommandExecutionHandler2
import json

cfg = ConfigManager('config.json')
handler = CommandExecutionHandler2(cfg)
inner = "python3 - <<'PY'\nprint(\"hello-from-heredoc\")\nPY"
cmd = f"bash -lc \"{inner}\""
args = {
    "location": "external",
    "external_root": "repo_lucy",
    "command": cmd,
    "working_directory": ".",
    "timeout_seconds": 5,
    "success_exit_codes": [0],
}
res = handler.execute(args)
print(json.dumps(res, indent=2))

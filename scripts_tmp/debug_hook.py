import os
import sys
from pathlib import Path

home = Path.home()
os.environ["CLAUDE_PROJECT_DIR"] = r"g:\PaperAgent"
cwd = Path(os.environ["CLAUDE_PROJECT_DIR"]).resolve()
print("home:", home)
print("cwd:", cwd)
print("cwd.anchor:", cwd.anchor)
projects_dir = home / ".claude" / "projects"
print("projects_dir:", projects_dir, "exists:", projects_dir.exists())
slug = str(cwd).replace(":", "").replace("\\", "-").replace("/", "-")
print("slug candidate:", slug)
exact = projects_dir / slug
print("exact dir exists:", exact.exists())
if exact.exists():
    print("jsonl files in exact (first 3):")
    for p in list(exact.glob("*.jsonl"))[:3]:
        print("  ", p.name, p.stat().st_size, "bytes")

"""Write Re03 完工报告."""

from pathlib import Path

# Read the report body from this script's own __file__ companion.
# Simpler: just embed the long content.
CONTENT = open("G:/PaperAgent/_re03_writer.py", "r", encoding="utf-8").read()
# Strip the script wrapper
import re
m = re.search(r"CONTENT = r'''(.*?)'''", CONTENT, re.DOTALL)
if m:
    Path("G:/PaperAgent/Plan/PaperAgent_Re03_完工报告.md").write_text(m.group(1), encoding="utf-8")
    print(f"Wrote {len(m.group(1))} chars")
else:
    print("No match")

"""Loads reconstructed game content shipped with the port."""
import json
from pathlib import Path

_DIR = Path(__file__).resolve().parent / "content"

# [bin] DIALOGS.REC -> 51 trail-ordered "talk to people" advice records.
DIALOGS = json.loads((_DIR / "dialogs.json").read_text(encoding="latin1"))

# The Oregon Trail Deluxe — Python port

A faithful Python re-creation of the 1990 MECC **Oregon Trail Deluxe** (`OREGON.EXE`),
reverse-engineered from the original binary and live DOSBox play. This package is
**self-contained**: everything the game needs at runtime — the recovered MCGA art, the
landmark tunes, and the Hall-of-Fame records — ships under [`assets/`](assets/).

## Run it

Requirements: **Python 3.11+** and **Pillow**. The GUI uses **tkinter** (Python standard
library), so nothing else is needed.

```
pip install Pillow
python -m oregon_deluxe.gui
```

Run the command from the directory that *contains* the `oregon_deluxe/` folder (the
package's relative imports need it importable as `oregon_deluxe`).

## Controls

| Key | Action |
|-----|--------|
| number keys | pick a numbered menu item |
| ENTER | confirm the typed choice |
| SPACE | continue past a message |
| Y / N | answer yes/no prompts |
| ESC | quit from the main menu; back out of a screen elsewhere |

**Hunting** (menu option 8 on the open trail, or when food runs low): turn the hunter
with the **arrow keys** or **W/A/S/D**, hold **CTRL** to walk forward the way he's facing,
and press **SPACE** to fire. Buffalo, deer, and rabbits cross the grassland; trees and
rocks give them cover. You have ~15 seconds and your remaining bullets. **ENTER** (or ESC)
ends the hunt early — meat is tallied, and as in the original you can carry only ~100 lbs
back to the wagon.

## What's in the package

| file | role |
|------|------|
| `data.py` | all recovered game data — trail landmarks + mileages, prices and the confirmed `1.0 + 0.25·fort` markup, scoring, weather/health/pace/rations/disease enums, professions. Values tagged `[bin]`/`[obs]`/`[tune]` for provenance. |
| `engine.py` | UI-agnostic `Game` engine: setup, stores, day-by-day travel, events, river crossings, forks (South Pass / The Dalles), health/rations/pace, and Hall-of-Fame scoring. |
| `content.py` | the "Talk to people" advice records parsed from `DIALOGS.REC`. |
| `hunt.py` | the interactive hunting minigame (UI-agnostic sim): hunter movement, animal spawning/movement, bullets, obstacle cover, meat tally. |
| `music.py` | plays the per-landmark MML tunes from `assets/SONGS.TXT`. |
| `gui.py` | tkinter front end drawing the real MCGA art (`assets/mcga/`): title, setup, store, animated traveling scene, per-landmark scenes (`p0`–`p17`), rivers, forks, hunting, map, and scoring. |
| `assets/` | the art (`mcga/*.png`) plus `SONGS.TXT` and `HISCORES.REC` the game reads at runtime. |

## Fidelity notes

- **Verified from the binary / live play:** trail landmarks and mileages, all store prices
  and the per-fort markup rule, the scoring formula, the game enums, and the
  river/guide/fork mechanics.
- **Approximate (`[tune]`):** exact event probabilities, the daily-mileage and health
  formulas, and hunting yield. These match observed behaviour but are not byte-exact;
  they're isolated constants in `data.py`/`engine.py` and easy to refine.
- Carpenter/farmer starting cash ($800/$400) is folklore; only the banker's $1600 was
  confirmed on screen.

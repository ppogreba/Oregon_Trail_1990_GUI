"""The Oregon Trail Deluxe - tkinter front end.

Renders the recovered MCGA art (assets/mcga/) over the reconstructed engine using a
tkinter Canvas (stdlib) with Pillow for nearest-neighbour pixel-art scaling.
Run with:  python -m oregon_deluxe.gui
Keyboard: number keys pick menu items, ENTER confirms, SPACE continues, Y/N answers,
ESC quits from the main menu.

Rendering model: layout is authored in the original 320x200 "MCGA space"; every
coordinate/size is multiplied by S when drawn, so pixel art is nearest-neighbour
upscaled while text is crisp at the final window resolution.
"""
from __future__ import annotations
import math
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path

from PIL import Image, ImageTk

from . import data as D
from . import music
from .engine import Game
from .hunt import Hunt, FACE_KEYS

# Everything the game needs at runtime lives inside the package under assets/.
ASSETS = Path(__file__).resolve().parent / "assets"
ART = ASSETS / "mcga"

# One MML tune per landmark (SONGS.TXT has 18 non-empty lines matching p0.png..p17.png).
try:
    SONGS = [ln for ln in (ASSETS / "SONGS.TXT").read_text(encoding="latin1").splitlines() if ln.strip()]
except OSError:
    SONGS = []

LW, LH = 320, 200            # logical (MCGA) resolution
S = 3                        # scale factor -> 960x600 window
WIN_W, WIN_H = LW * S, LH * S

BLACK = (0, 0, 0)
INK = (236, 230, 214)
DIM = (168, 150, 122)
GOLD = (222, 176, 84)
BROWN = (150, 96, 40)
RED = (176, 32, 32)
GROUND = (150, 128, 44)

# Foreground band tint from BOTH weather and location (see UI._ground_color).
GROUND_GREEN = (96, 138, 44)      # lush plains meadow
GROUND_MTN = (170, 182, 168)      # cold high country -> pale, snow-leaning
GROUND_TAN = (178, 156, 98)       # dry valley
GROUND_MUSTARD = (156, 148, 20)   # hot & dry
GROUND_BROWN = (152, 118, 74)     # scorched (a tan-brown, "very hot")
GROUND_SNOW = (228, 226, 212)     # snow on the ground

# "Learn about the trail" pages (verbatim recovered from OREGON.EXE)
LEARN_PAGES = [
    "Try taking a journey by covered wagon across 2000 miles of plains, rivers, and "
    "mountains.  On the plains, will you slosh your oxen through mud and water-filled "
    "ruts or will you plod through dust six inches deep?",
    "How will you cross the rivers?  If you have money, you might take a ferry (if there "
    "is a ferry).  Or, you can ford the river and hope you and your wagon aren't "
    "swallowed alive!",
    "What about supplies?  Well, if you're low on food you can hunt.  You might get a "
    "buffalo... you might.  And there are bear in the mountains.",
    "At the Dalles, you can try navigating the Columbia River, but if running the rapids "
    "with a makeshift raft makes you queasy, better take the Barlow Road.",
    "If for some reason you don't survive -- your wagon burns, or thieves steal your "
    "oxen, or you run out of provisions, or you die of cholera -- don't give up!  Try "
    "again...and again...until your name is up with the others on The Oregon Top Ten.",
]


# Which scenery.png sprite to show on the horizon as you approach each landmark (by index).
SCENE_SPRITE = ["town", "river", "river", "fort0", "spire", "fort1", "rocks", "peaks",
                "fort2", "bigriver", "spring", "fort3", "bigriver", "fort4", "peaks",
                "fort0", "peaks", "valley"]

# crop boxes into travelox.png (wagon frames) and scenery.png (backdrops + landmarks)
WAGON_FRAMES = {
    "wagon_walk0": (1, 1, 79, 33), "wagon_walk1": (89, 1, 167, 33),
    "wagon_walk2": (177, 1, 255, 33),
    "wagon_broken": (1, 35, 78, 72), "wagon_fire": (86, 35, 180, 72),
}
FLOAT_CROPS = {   # river-crossing pictures from float.png (blue water background kept)
    "cross_ferry": (4, 4, 78, 57), "cross_ford": (82, 4, 164, 53),
    "cross_caulk": (164, 4, 215, 53), "cross_tipped": (6, 60, 73, 110),
}
EVENT_CROPS = {
    "ev_berries": (2, 2, 29, 19), "ev_cloudy": (36, 2, 72, 16),
    "ev_snowy": (80, 3, 118, 19), "ev_rainy": (126, 3, 165, 25),
    "ev_storm": (174, 3, 213, 21),
    "ev_robber_supplies": (226, 3, 241, 27), "ev_robber_clothes": (251, 3, 273, 27),
}
SCENERY_CROPS = {
    "bg_meadow": (0, 1, 320, 18), "bg_mtns": (0, 19, 320, 47),
    "fort0": (3, 50, 56, 75), "fort1": (65, 52, 109, 72), "fort2": (118, 52, 159, 75),
    "fort3": (167, 52, 210, 74), "fort4": (222, 50, 297, 74),
    "town": (2, 81, 43, 103), "spire": (52, 83, 79, 106), "river": (94, 83, 150, 106),
    "valley": (163, 84, 220, 104),
    "rocks": (3, 113, 38, 129), "rocks2": (59, 115, 99, 131), "spring": (111, 109, 152, 127),
    "peaks": (170, 111, 221, 127), "bigriver": (226, 107, 309, 130),
}

def _hcell(col, row, hs, vs):
    # breaks hunter.png up into a 4x6 grid with hs=horizontal pixel step size, and vs vertical pixel step size
    """Crop box for one hunter.png cell at the hs/vs step size (col 0-5, row 0-3)."""
    x, y = col * hs, row * vs
    return (x, y, x + hs, y + vs)

# (row, starting-column) of each cardinal's 3-frame group within the grid above.
_HUNTER_DIRS = {"up": (0, 0), "right": (1, 3), "left": (2, 0), "down": (3, 3)}
HUNTER_CROPS = {
    f"hunter_{d}_{frame}": _hcell(col0 + col, row, hs=44, vs=41)
    for d, (row, col0) in _HUNTER_DIRS.items()
    for col, frame in ((0, "stand"), (1, "0"), (2, "1"))
}
# animals.png: 6 animals, one per row; each row is 8 frames = [dead-R, R0, R1, R2 | L2, L1,
# L0, dead-L].  Columns 0-3 face RIGHT, columns 4-7 face LEFT (native mirror, no flipping).
# Rows: 0 buffalo, 1 bear, 2 buck, 3 deer, 4 rabbit, 5 squirrel.  Each animal has three walk
# frames each way plus a dead frame.
ANIMAL_CROPS = {
    # buffalo (row 0)
    "buf_r0": (40, 2, 66, 21), "buf_r1": (79, 2, 106, 21), "buf_r2": (120, 2, 146, 21),
    "buf_l0": (235, 2, 261, 21), "buf_l1": (195, 2, 222, 21), "buf_l2": (155, 2, 181, 21),
    "buf_dead_r": (4, 2, 32, 21), "buf_dead_l": (268, 2, 296, 21),
    # bear (row 1)
    "bear_r0": (39, 24, 67, 39), "bear_r1": (82, 24, 107, 39), "bear_r2": (117, 24, 142, 39),
    "bear_l0": (234, 24, 262, 39), "bear_l1": (194, 24, 219, 39), "bear_l2": (159, 24, 184, 39),
    "bear_dead_r": (6, 24, 32, 39), "bear_dead_l": (268, 24, 294, 39),
    # buck (row 2 -- antlered)
    "buck_r0": (38, 44, 63, 67), "buck_r1": (81, 44, 105, 67), "buck_r2": (122, 44, 145, 67),
    "buck_l0": (238, 44, 263, 67), "buck_l1": (196, 44, 220, 67), "buck_l2": (156, 44, 179, 67),
    "buck_dead_r": (6, 44, 31, 67), "buck_dead_l": (269, 44, 294, 67),
    # deer (row 3 -- doe)
    "deer_r0": (42, 71, 70, 93), "deer_r1": (77, 71, 107, 93), "deer_r2": (115, 71, 143, 93),
    "deer_l0": (231, 71, 259, 93), "deer_l1": (194, 71, 224, 93), "deer_l2": (158, 71, 186, 93),
    "deer_dead_r": (4, 71, 34, 93), "deer_dead_l": (266, 71, 296, 93),
    # rabbit (row 4)
    "rab_r0": (34, 97, 48, 111), "rab_r1": (64, 97, 77, 111), "rab_r2": (92, 97, 105, 111),
    "rab_l0": (175, 97, 189, 111), "rab_l1": (146, 97, 159, 111), "rab_l2": (118, 97, 131, 111),
    "rab_dead_r": (6, 97, 19, 111), "rab_dead_l": (281, 97, 294, 111),
    # squirrel (row 5)
    "sqrl_r0": (35, 114, 60, 127), "sqrl_r1": (73, 114, 98, 127), "sqrl_r2": (113, 114, 136, 127),
    "sqrl_l0": (219, 114, 242, 127), "sqrl_l1": (187, 114, 212, 127), "sqrl_l2": (149, 114, 174, 127),
    "sqrl_dead_r": (5, 114, 28, 127), "sqrl_dead_l": (271, 114, 294, 127),
}
ANIMAL_PREFIX = {"buffalo": "buf", "bear": "bear", "buck": "buck",
                 "deer": "deer", "rabbit": "rab", "squirrel": "sqrl"}
# terrain.png holds every hunting-field prop in one sheet: two rows of trees on the left,
# a block of on-screen keyboard keys in the middle (skipped), then grasses/flowering
# bushes/boulders on the right.  Each box is the tight bounding box of that sprite's
# colored pixels -- no bleed into a neighbour, no black margin past the last lit pixel.
TERRAIN_CROPS = {
    # left block: seven trees (top row of four, bottom row of three)
    "tree1": (0, 0, 35, 42), "tree2": (46, 1, 80, 44),
    "tree3": (99, 8, 116, 41), "tree4": (116, 14, 136, 43),
    "tree5": (0, 48, 36, 88), "tree6": (49, 48, 78, 89), "tree7": (93, 47, 127, 88),
    # right block: grass tufts, flowering bushes, boulder clusters
    "grass1": (210, 4, 254, 18), "grass2": (269, 9, 311, 19),
    "bush_purple": (213, 28, 237, 48), "bush_yellow": (252, 26, 282, 52),
    "bush_blue": (296, 27, 320, 49), "bush_red": (273, 54, 319, 68),
    "rock1": (192, 56, 228, 71), "rock2": (236, 56, 266, 71),
}


def _hex(c):
    return c if isinstance(c, str) else "#%02x%02x%02x" % c

# The float.png crossing pictures sit on a solid blue (64,176,252) water field with a
# darker (0,92,156) shading.  We knock those out so the wagon/raft composites over our
# own animated water band and can ride up onto the tan banks at either edge.
WATER_BLUE = (64, 176, 252)
WATER_DEEP = (0, 92, 156)


def _blue_transparent(im):
    """Make the float sprite's blue water background transparent, keeping the wagon."""
    im = im.convert("RGBA")
    px = im.load()
    W, H = im.size
    for y in range(H):
        for x in range(W):
            r, g, b, a = px[x, y]
            if (abs(r - WATER_BLUE[0]) + abs(g - WATER_BLUE[1]) + abs(b - WATER_BLUE[2]) < 30
                    or abs(r - WATER_DEEP[0]) + abs(g - WATER_DEEP[1]) + abs(b - WATER_DEEP[2]) < 30):
                px[x, y] = (0, 0, 0, 0)
    return im


def _bg_transparent(im):
    """Flood-fill border-connected near-black pixels to transparent, leaving interior
    black (wheels, outlines) opaque, so a sprite composites cleanly over a backdrop."""
    from collections import deque
    im = im.convert("RGBA")
    W, H = im.size
    px = im.load()
    def nb(p):
        return p[0] < 26 and p[1] < 26 and p[2] < 26
    seen = bytearray(W * H)
    dq = deque()
    for x in range(W):
        dq.append((x, 0)); dq.append((x, H - 1))
    for y in range(H):
        dq.append((0, y)); dq.append((W - 1, y))
    while dq:
        x, y = dq.popleft()
        if x < 0 or y < 0 or x >= W or y >= H or seen[y * W + x]:
            continue
        seen[y * W + x] = 1
        if not nb(px[x, y]):
            continue
        px[x, y] = (0, 0, 0, 0)
        dq.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])
    return im


class UI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("The Oregon Trail Deluxe")
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(self.root, width=WIN_W, height=WIN_H,
                                bg="black", highlightthickness=0)
        self.canvas.pack()
        self.font = tkfont.Font(family="Consolas", size=15)
        self.big = tkfont.Font(family="Consolas", size=30, weight="bold")
        self.art = self._load_art()
        self._photo: dict = {}                   # (name, w, h) -> PhotoImage cache
        self.anim = 0.0
        self._tframe = 0
        self.sound = True
        self.learn_page = 0
        self._resume_state = "menu"
        self.hiscores = self._load_hiscores()
        self.held: set[str] = set()              # keys currently down (hunting movement)
        self._reset_state()
        self.root.bind("<Key>", self.on_key)
        self.root.bind("<KeyRelease>", self.on_release)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

    def _reset_state(self):
        self.g: Game | None = None
        self.hunt: Hunt | None = None
        self.held.clear()
        self.state = "menu"
        self.messages: list[str] = []
        self.pending = None
        self.text_input = ""
        self.names: list[str] = []
        self._prof_key = "banker"
        self.store_item = None
        self.store_msg = ""
        self.extras = {"wheel": "", "axle": "", "tongue": ""}
        self.extras_sel = 0
        self.talk = ("", "")
        self._river = (0, 0.0)
        self._cross = None               # in-progress river-crossing animation state
        self.choice = ""                 # typed menu number, committed with ENTER
        self._warned_low_food = False
        music.stop()

    def _load_art(self):
        art = {}
        for p in ART.glob("*.png"):
            art[p.stem] = Image.open(p).convert("RGBA")
        if "travelox" in art:                       # wagon animation + affliction frames
            for name, box in WAGON_FRAMES.items():
                art[name] = _bg_transparent(art["travelox"].crop(box))
        if "scenery" in art:                        # backdrops + approaching-landmark sprites
            for name, box in SCENERY_CROPS.items():
                art[name] = _bg_transparent(art["scenery"].crop(box))
        if "events" in art:                          # event / weather icons
            for name, box in EVENT_CROPS.items():
                art[name] = _bg_transparent(art["events"].crop(box))
        if "float" in art:                           # river-crossing wagon/raft (blue knocked out)
            for name, box in FLOAT_CROPS.items():
                art[name] = _blue_transparent(art["float"].crop(box))
        if "hunter" in art:                          # hunting minigame: player poses
            for name, box in HUNTER_CROPS.items():
                art[name] = _bg_transparent(art["hunter"].crop(box))
        if "animals" in art:                         # hunting minigame: quarry
            for name, box in ANIMAL_CROPS.items():
                art[name] = _bg_transparent(art["animals"].crop(box))
        if "terrain" in art:                         # hunting minigame: cover/obstacles
            for name, box in TERRAIN_CROPS.items():
                art[name] = _bg_transparent(art["terrain"].crop(box))
        return art

    def _event_image(self, msg):
        m = msg.lower()
        if "wild fruit" in m or "berries" in m or "berr" in m:
            return "ev_berries"
        if "thief" in m or "steal" in m:
            return "ev_robber_clothes" if "cloth" in m else "ev_robber_supplies"
        if "blizzard" in m or "snow" in m:
            return "ev_snowy"
        if "storm" in m or "hail" in m or "lightning" in m:
            return "ev_storm"
        if "rain" in m:
            return "ev_rainy"
        return None

    def _weather_icon(self):
        w = self.g.weather
        if w == "very rainy":
            return "ev_storm"
        if w == "rainy":
            return "ev_rainy"
        if w in ("snowy", "very snowy"):
            return "ev_snowy"
        if w in ("cold", "cool", "very cold"):
            return "ev_cloudy"
        return None                                  # warm / hot / clear -> no clouds

    def _load_hiscores(self):
        """Parse the original HISCORES.REC: 10 fixed 18-byte records
        (length-prefixed name, score as a little-endian word at offset 16)."""
        try:
            data = (ASSETS / "HISCORES.REC").read_bytes()
        except OSError:
            return []
        out = []
        for i in range(len(data) // 18):
            o = i * 18
            name = data[o + 1:o + 1 + data[o]].decode("latin1", "replace").strip()
            score = int.from_bytes(data[o + 16:o + 18], "little")
            if name:
                out.append((name, score))
        return out

    # ------------------------------------------------------------ draw helpers
    def text(self, s, x, y, color=INK, font=None):
        self.canvas.create_text(x * S, y * S, text=s, anchor="nw",
                                fill=_hex(color), font=font or self.font)

    def center(self, s, y, color=INK, font=None):
        self.canvas.create_text(WIN_W // 2, y * S, text=s, anchor="n",
                                fill=_hex(color), font=font or self.font)

    def rect(self, color, r, width=0):
        x1, y1 = r[0] * S, r[1] * S
        x2, y2 = (r[0] + r[2]) * S, (r[1] + r[3]) * S
        if width:
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=_hex(color), width=width * S)
        else:
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=_hex(color), outline="")

    def box(self, r, border=INK, fill=BLACK):
        self.rect(fill, r)
        self.rect(border, r, 1)

    def poly(self, color, pts):
        self.canvas.create_polygon([c * S for xy in pts for c in xy],
                                   fill=_hex(color), outline="")

    def blit(self, name, x, y, w=None, h=None):
        base = self.art.get(name)
        if base is None:
            return
        w = w if w is not None else base.width
        h = h if h is not None else base.height
        key = (name, w, h)
        photo = self._photo.get(key)
        if photo is None:
            photo = ImageTk.PhotoImage(base.resize((w * S, h * S), Image.NEAREST))
            self._photo[key] = photo
        self.canvas.create_image(x * S, y * S, anchor="nw", image=photo)

    def wrap(self, s, n):
        out, line = [], ""
        for w in s.replace("\\", " ").split():
            if len(line) + len(w) + 1 > n:
                out.append(line); line = w
            else:
                line = (line + " " + w).strip()
        if line:
            out.append(line)
        return out

    def textbox(self, lines, y=150, border=INK):
        self.box((8, y, LW - 16, len(lines) * 11 + 8), border)
        for i, ln in enumerate(lines):
            self.text(ln, 14, y + 5 + i * 11)

    # ================================================================== loop
    def start(self):
        self.root.after(120, self.root.focus_force)   # grab keyboard focus on launch
        self.tick()
        self.root.mainloop()

    def tick(self):
        self.update()
        self.render()
        self.anim += 0.2
        self.root.after(33, self.tick)

    def render(self):
        self.canvas.delete("all")
        getattr(self, f"draw_{self.state}", lambda: None)()
        if self.messages:
            self._draw_message(self.messages[0])

    def on_release(self, event):
        self.held.discard(event.keysym)

    def on_key(self, event):
        ks, ch = event.keysym, event.char
        self.held.add(ks)                                # for hold-to-move in the hunt
        if ks == "Escape":
            self.choice = ""
            if self.state == "menu":
                self.root.destroy()
            elif self.state == "confirm":
                self.state = self._resume_state          # cancel, resume game
            elif self.state in ("learn", "topten", "manage"):
                self.state = "menu"
            elif self.state == "store" and self.store_item:
                self.store_item, self.text_input = None, ""   # cancel the purchase
            elif self.state == "extras":
                self.store_msg, self.state = "", "store"      # cancel spare-parts form
            elif self.state == "hunt":
                self._finish_hunt()                      # end the hunt, tally the meat
            else:                                        # in-game -> confirm return to menu
                self._resume_state = self.state
                self.messages = []
                self.state = "confirm"
            return
        if self.messages:
            if ks in ("space", "Return"):
                self.messages.pop(0)
                if not self.messages and self.pending:
                    cb, self.pending = self.pending, None
                    cb()
            return
        getattr(self, f"key_{self.state}", lambda k, c: None)(ks, ch)

    def queue(self, msgs, then=None):
        self.messages = [m for m in msgs if m]
        self.pending = then
        if not self.messages and then:
            then()

    def _menu_key(self, ks, ch, on_commit, allow="123456789"):
        """Numbered-menu input: digits accumulate in self.choice and show on screen;
        ENTER commits the typed number, BackSpace erases it. Nothing happens until ENTER."""
        if ch and ch in allow:
            self.choice = ch                  # every menu here is a single digit
        elif ks == "BackSpace":
            self.choice = ""
        elif ks == "Return" and self.choice:
            val = self.choice
            self.choice = ""
            on_commit(val)

    def _yesno_key(self, ks, ch, on_commit):
        """Y/N input: letter shows on screen, ENTER commits it."""
        if ch and ch.lower() in ("y", "n"):
            self.choice = ch.lower()
        elif ks == "BackSpace":
            self.choice = ""
        elif ks == "Return" and self.choice:
            val = self.choice
            self.choice = ""
            on_commit(val)

    def update(self):
        """Per-frame logic: drive the animated travel scene one day per second."""
        if self.state == "hunt" and self.hunt and not self.messages:
            self.hunt.update(0.033, self.held)
            if self.hunt.done:
                self._finish_hunt()
            return
        if self.state == "crossing" and self._cross and self._cross["res"] and not self.messages:
            self._update_crossing()
            return
        if self.state == "traveling" and not self.messages:
            self._tframe += 1
            if self._tframe >= 30:           # ~1 game-day/sec at the 33ms tick rate
                self._tframe = 0
                g = self.g
                start = g.landmark
                step = g.travel_one_day()
                if g.finished:
                    self.queue(step, then=lambda: setattr(self, "state", "gameover"))
                elif g.landmark != start:
                    # Arrived: switch to the landmark scene right away so the reached
                    # landmark sits by the oxen (the landmark screen announces "You are now
                    # at X" itself, so drop the engine's duplicate line).  The *next*
                    # landmark only starts approaching once the player continues on.
                    self.state = "landmark"
                    self.queue([m for m in step if not m.startswith("You are now at")])
                else:
                    # check for low food whether or not today had its own event message
                    # (queue() fires `then` immediately when there's nothing to show)
                    self.queue(step, then=self._check_food_warning)

    def _check_food_warning(self):
        """Pause the journey to offer hunting when food is about to run out."""
        g = self.g
        per_day = max(1, len(g.alive_members()) * D.RATION_LBS[g.rations])
        low = per_day * 3                     # <= 3 days of food left
        if g.food <= low and not self._warned_low_food:
            self._warned_low_food = True
            self.choice = ""
            self.state = "foodwarn"
        elif g.food > low * 2:
            self._warned_low_food = False     # re-arm the warning once well stocked again

    # ================================================================ input
    def key_menu(self, ks, ch):
        self._menu_key(ks, ch, self._menu_commit, allow="123456")

    def _menu_commit(self, val):
        if val == "1":
            self.state = "prof"
        elif val == "2":
            self.learn_page = 0
            self.state = "learn"
        elif val == "3":
            self.state = "topten"
        elif val == "4":
            self.sound = not self.sound
            if not self.sound:
                music.stop()
        elif val == "5":
            self.state = "manage"
        elif val == "6":
            self.root.destroy()

    def key_learn(self, ks, ch):
        if ks in ("space", "Return"):
            self.learn_page += 1
            if self.learn_page >= len(LEARN_PAGES):
                self.state = "menu"
        else:
            self.state = "menu"

    def key_topten(self, ks, ch):
        self.state = "menu"

    def key_manage(self, ks, ch):
        self.state = "menu"

    def key_confirm(self, ks, ch):
        self._yesno_key(ks, ch, self._confirm_commit)

    def _confirm_commit(self, val):
        if val == "y":
            self._reset_state()                          # discard game, back to menu
        else:
            self.state = self._resume_state

    def key_prof(self, ks, ch):
        self._menu_key(ks, ch, self._prof_commit, allow="123")

    def _prof_commit(self, val):
        self._prof_key = D.PROFESSIONS[int(val) - 1]["key"]
        self.names, self.text_input = [], ""
        self.state = "names"

    def key_names(self, ks, ch):
        if ks == "Return":
            default = ["Ma", "Pa", "Mary", "Luke", "Sue"][len(self.names)]
            self.names.append(self.text_input.strip() or default)
            self.text_input = ""
            if len(self.names) == 5:
                self.state = "month"
        elif ks == "BackSpace":
            self.text_input = self.text_input[:-1]
        elif ch and ch.isprintable() and ch != " " and len(self.text_input) < 12:
            self.text_input += ch

    def key_month(self, ks, ch):
        self._menu_key(ks, ch, self._month_commit, allow="12345")

    def _month_commit(self, val):
        self.g = Game(self._prof_key, self.names, D.MONTHS[int(val) - 1])
        self.store_item, self.store_msg = None, "Welcome to Matt's General Store."
        self.state = "store"

    STORE_ITEMS = ["oxen", "food", "clothing", "ammunition"]
    EXTRAS_FIELDS = ["wheel", "axle", "tongue"]     # spare parts, bought together

    def key_store(self, ks, ch):
        g = self.g
        if self.store_item is None:
            self._menu_key(ks, ch, self._store_pick, allow="123456")
        else:
            if ks == "Return":
                qty = int(self.text_input) if self.text_input.isdigit() else 0
                if qty > 0:
                    if self.store_item == "oxen" and g.landmark == 0:
                        self.store_msg = g.buy("oxen", qty * 2)[1]   # yokes -> oxen
                    else:
                        self.store_msg = g.buy(self.store_item, qty)[1]
                self.store_item, self.text_input = None, ""
            elif ks == "BackSpace":
                self.text_input = self.text_input[:-1]
            elif ch.isdigit() and len(self.text_input) < 5:
                self.text_input += ch

    def _store_pick(self, val):
        if val == "6":
            self.state = "trailmenu"
        elif val == "5":                            # Extra supplies -> spare-parts form
            self.extras = {k: "" for k in self.EXTRAS_FIELDS}
            self.extras_sel = 0
            self.store_msg = ""
            self.state = "extras"
        else:
            self.store_item, self.text_input = self.STORE_ITEMS[int(val) - 1], ""

    def key_extras(self, ks, ch):
        key = self.EXTRAS_FIELDS[self.extras_sel]
        if ks in ("Up", "w", "W"):
            self.extras_sel = (self.extras_sel - 1) % len(self.EXTRAS_FIELDS)
        elif ks in ("Down", "s", "S"):
            self.extras_sel = (self.extras_sel + 1) % len(self.EXTRAS_FIELDS)
        elif ks == "Return":
            self._buy_extras()
        elif ks == "BackSpace":
            self.extras[key] = ""
        elif ch and ch.isdigit():
            self.extras[key] = ch                   # single-digit quantity (max is 3)

    def _buy_extras(self):
        """Sum every spare part the player entered and buy them in one transaction."""
        g = self.g
        prices = g.store_prices()
        qtys = {k: (int(self.extras[k]) if self.extras[k].isdigit() else 0)
                for k in self.EXTRAS_FIELDS}
        if not any(qtys.values()):
            self.state, self.store_msg = "store", ""      # nothing entered -> back
            return
        for k in self.EXTRAS_FIELDS:
            if qtys[k] and g.parts[k] + qtys[k] > D.MAX_SPARE_EACH:
                self.store_msg = f"You may only carry {D.MAX_SPARE_EACH} of each spare part."
                return
        total_cents = sum(round(prices[k] * qtys[k] * 100) for k in self.EXTRAS_FIELDS)
        if total_cents > g.cash_cents:
            self.store_msg = "You cannot afford all those parts."
            return
        for k in self.EXTRAS_FIELDS:
            if qtys[k]:
                g.buy(k, qtys[k])
        self.store_msg = "Purchased your spare parts."
        self.state = "store"

    def _atfort(self):
        """True only while STOPPED at a town/fort (Independence or a fort) -- the places
        the original offers 'Talk to people'/'Buy supplies'.  Once you're travelling again
        (seg_miles > 0, even just after leaving a fort) the menu reverts to the open-trail
        'Hunt for food' with no store.  [obs] DATA_TABLES.md: menu is context-sensitive."""
        g = self.g
        if g.seg_miles != 0:
            return False
        return g.landmark == 0 or g.here()["kind"] == D.FORT

    def key_trailmenu(self, ks, ch):
        self._menu_key(ks, ch, self._trailmenu_commit, allow="123456789")

    def _trailmenu_commit(self, val):
        g = self.g
        if val == "1":
            self._continue()
        elif val == "2":
            self.state = "supplies"
        elif val == "3":
            self.state = "map"
        elif val == "4":
            g.pace = D.PACE[(D.PACE.index(g.pace) + 1) % 3]
        elif val == "5":
            g.rations = D.RATIONS[(D.RATIONS.index(g.rations) + 1) % 3]
        elif val == "6":
            self.queue([g.rest(3)])
        elif val == "7":
            self.queue(["No one wants to trade with you right now."])
        elif val == "8":
            if self._atfort():
                self.talk = g.talk_to_people(); self.state = "talk"
            else:
                self._begin_hunt()
        elif val == "9" and self._atfort() and g.store_prices():
            self.store_item, self.store_msg = None, ""
            self.state = "store"

    def _continue(self):
        g = self.g
        if g.here()["kind"] == D.RIVER and g.seg_miles == 0 and g.landmark not in g.crossed:
            self._river = g.river_state(); self.state = "river"; return
        if g.here().get("fork") and g.seg_miles == 0 and g.landmark not in g.forked:
            self.state = "fork"; return
        self._tframe = 0
        self.state = "traveling"

    def key_traveling(self, ks, ch):
        self.state = "trailmenu"          # any key pauses the journey

    def key_landmark(self, ks, ch):
        self._yesno_key(ks, ch, self._landmark_commit)

    def _landmark_commit(self, val):
        if val == "y":
            self.state = "scene"
            if self.sound and 0 <= self.g.landmark < len(SONGS):
                music.play(SONGS[self.g.landmark])
        else:
            self.state = "trailmenu"

    def key_scene(self, ks, ch):
        music.stop()
        self.state = "trailmenu"

    def key_supplies(self, ks, ch):
        self.state = "trailmenu"

    def key_map(self, ks, ch):
        self.state = "trailmenu"

    def key_talk(self, ks, ch):
        self.state = "trailmenu"

    def _begin_hunt(self):
        g = self.g
        if g.bullets <= 0:
            self.queue(["You don't have any bullets left to hunt with."])
            return
        self.held.clear()
        mountains = g.here().get("zone", 12) == 12
        self.hunt = Hunt(g.rng, g.bullets, field=(14, 46, 306, 168), mountains=mountains)
        self.state = "hunt"

    def _finish_hunt(self):
        if not self.hunt:
            return
        g = self.g
        g.bullets = self.hunt.ammo                    # apply bullets fired this hunt
        msg = g.finish_hunt(self.hunt.bagged)
        self.hunt = None
        self.held.clear()
        self.state = "trailmenu"
        self.queue([msg])

    def key_hunt(self, ks, ch):
        if not self.hunt:
            return
        if ks in FACE_KEYS:                      # arrows / WASD only turn him
            self.hunt.face(FACE_KEYS[ks])
        elif ks == "space":
            self.hunt.shoot()
        elif ks == "Return":
            self._finish_hunt()

    def key_river(self, ks, ch):
        self._menu_key(ks, ch, self._river_commit, allow="123456")

    def _river_commit(self, val):
        g = self.g
        opts = g.river_options()
        if not (1 <= int(val) <= len(opts)):
            return
        choice, (w, depth) = opts[int(val) - 1], self._river
        if choice.startswith("attempt to ford"):
            method, img = "ford", "cross_ford"
        elif choice.startswith("caulk"):
            method, img = "caulk", "cross_caulk"
        elif choice.startswith("take a ferry"):
            method, img = "ferry", "cross_ferry"
        elif choice.startswith("hire"):
            method, img = "guide", "cross_ferry"
        elif choice.startswith("wait"):
            g.rest(1); self._river = g.river_state(); return
        else:                                    # get more information
            return
        res = g.cross_river(method, depth)
        g.crossed.add(g.landmark)                # <- lets the trail continue past the river
        bad = any(k in res.lower() for k in ("tip", "swamp", "lose", "too deep"))
        self._begin_crossing(img, bad, res)

    # ---- animated bank-to-bank crossing ------------------------------------
    CROSS_SECS = 8.0                             # a clean crossing takes ~8 seconds (unhurried)
    CROSS_SETTLE = 1.2                           # beat to let a mishap register before the message

    def _begin_crossing(self, img, bad, res):
        """Set up the ~5s crossing.  A doomed wagon travels normally until a random
        1-4s mark, then the mishap plays out mid-river for a little suspense."""
        fail_t = self.g.rng.uniform(1.0, 4.0) if bad else None
        self._cross = {"img": img, "res": res, "bad": bad, "t": 0.0,
                       "fail_t": fail_t, "tipped": False, "tip_t": 0.0, "tip_prog": 0.0}
        self.state = "crossing"

    def _update_crossing(self):
        c = self._cross
        c["t"] += 0.033
        if c["bad"] and not c["tipped"] and c["t"] >= c["fail_t"]:
            c["tipped"] = True
            c["tip_t"] = c["t"]
            c["tip_prog"] = min(1.0, c["fail_t"] / self.CROSS_SECS)
        if c["tipped"]:
            if c["t"] - c["tip_t"] >= self.CROSS_SETTLE:
                self._finish_crossing()
        elif c["t"] >= self.CROSS_SECS:
            self._finish_crossing()

    def _finish_crossing(self):
        res, self._cross["res"] = self._cross["res"], None    # keep the frozen scene, show once
        self.queue([res], then=lambda: setattr(self, "state", "trailmenu"))

    def _cross_progress(self):
        c = self._cross
        return c["tip_prog"] if c["tipped"] else min(1.0, c["t"] / self.CROSS_SECS)

    def key_crossing(self, ks, ch):
        pass                                     # advanced by the message queue (SPACE)

    def key_fork(self, ks, ch):
        self._menu_key(ks, ch, self._fork_commit, allow="123")

    def _fork_commit(self, val):
        g = self.g
        opts = g.fork_options()
        if not (1 <= int(val) <= len(opts)):
            return
        i = int(val) - 1
        if opts[i].startswith("see the map"):
            self.state = "map"; return
        self.queue([g.choose_fork(i)], then=lambda: setattr(self, "state", "trailmenu"))

    def key_foodwarn(self, ks, ch):
        self._yesno_key(ks, ch, self._foodwarn_commit)

    def _foodwarn_commit(self, val):
        if val == "y":
            self._begin_hunt()
        else:
            self._tframe = 0
            self.state = "traveling"

    def key_gameover(self, ks, ch):
        if ks in ("space", "Return"):
            self._reset_state()

    # ================================================================ render
    def _draw_message(self, msg):
        lines = self.wrap(msg, 40)
        name = self._event_image(msg)                 # berries / robbers / weather icon
        if name and name in self.art:
            im = self.art[name]
            w, h = im.width * 2, im.height * 2
            self.blit(name, (LW - w) // 2, 82 - h, w, h)
        self.box((8, 86, LW - 16, len(lines) * 11 + 10), INK)
        for i, ln in enumerate(lines):
            self.center(ln, 91 + i * 11)
        self.center("Press SPACE BAR to continue", 190, GOLD)

    def _status(self):
        g = self.g
        return [f"Date: {g.date:%B %d, %Y}", f"Weather: {g.weather}",
                f"Health: {g.health()}", f"Food: {g.food} pounds",
                f"Next landmark: {max(0, g.seg_target() - g.seg_miles)} miles",
                f"Miles traveled: {g.total_miles} miles"]

    def draw_menu(self):
        self.blit("banner", 0, 6)
        self.text("You may:", 40, 82)
        opts = ["1. Travel the trail", "2. Learn about the trail",
                "3. See the Oregon Top Ten",
                f"4. Turn sound {'off' if self.sound else 'on'}",
                "5. Choose Management Options", "6. End"]
        for i, o in enumerate(opts):
            self.text(o, 56, 96 + i * 12)
        self.text(f"What is your choice?  {self.choice}", 40, 178, GOLD)

    def draw_prof(self):
        self.blit("family", 60, 2, 200, 79)
        self.center("Many kinds of people made the trip to Oregon.", 88)
        self.text("You may:", 40, 104)
        for i, p in enumerate(D.PROFESSIONS):
            self.text(f"{i+1}. Be a {p['label']}", 56, 120 + i * 14)
        self.center(f"What is your choice?  {self.choice}", 176, GOLD)

    def draw_names(self):
        self.blit("family", 0, 6)
        n = len(self.names)
        prompt = ("What is the first name of the wagon leader?" if n == 0
                  else f"First name of party member {n+1} of 5?")
        self.textbox(self.wrap(prompt, 40) + [f"> {self.text_input}"], y=136)

    def draw_month(self):
        self.blit("p0", 70, 2, 180, 78)
        self.center("It is 1848.  You must decide which", 86)
        self.center("month to leave Independence.", 96)
        for i, m in enumerate(D.MONTHS):
            self.text(f"{i+1}. {m}", 120, 112 + i * 13)
        self.center(f"What is your choice?  {self.choice}", 182, GOLD)

    def _store_name(self):
        return "Matt's General Store" if self.g.landmark == 0 else self.g.here()["name"]

    def draw_store(self):
        g = self.g
        if self.store_item:                 # purchase overlay for the selected item
            self._draw_buy_overlay()
            return
        prices = g.store_prices()
        matts = g.landmark == 0
        self.center(self._store_name(), 6)
        self.center(f"{g.date:%B %d, %Y}", 22, GOLD)
        self.rect(RED, (8, 34, LW - 16, 1))
        rows = [("1. Oxen", "oxen", "ox"), ("2. Food", "food", "lb"),
                ("3. Clothing", "clothing", "set"), ("4. Ammunition", "ammunition", "box")]
        for i, (label, key, unit) in enumerate(rows):
            y = 44 + i * 13
            self.text(label, 20, y)
            if key == "oxen" and matts:      # Matt's sells oxen by the yoke (2 oxen)
                self.text(f"${prices['oxen'] * 2:.2f} per yoke", 175, y, GOLD)
            else:
                self.text(f"${prices[key]:.2f} per {unit}", 175, y, GOLD)
        y5 = 44 + 4 * 13
        self.text("5. Extra supplies", 20, y5)                 # wheels / axles / tongues
        self.text(f"${prices['wheel']:.2f} each", 175, y5, GOLD)
        self.text("6. Leave store", 20, y5 + 13)
        self.text(f"You have ${g.cash():.2f} to spend.", 20, 152, INK)
        self.text(f"Which number?  {self.choice}", 20, 168, GOLD)
        if self.store_msg:
            self.text(self.store_msg, 20, 184, DIM)

    def draw_extras(self):
        g = self.g
        prices = g.store_prices()
        self.center(self._store_name(), 6)
        self.center(f"{g.date:%B %d, %Y}", 22, GOLD)
        self.rect(RED, (8, 34, LW - 16, 1))
        self.center("Extra Supplies -- wagon spare parts", 44, INK)
        labels = {"wheel": "Wagon wheels", "axle": "Wagon axles", "tongue": "Wagon tongues"}
        total = 0.0
        for i, key in enumerate(self.EXTRAS_FIELDS):
            y = 66 + i * 15
            qty = int(self.extras[key]) if self.extras[key].isdigit() else 0
            sub = prices[key] * qty
            total += sub
            sel = (i == self.extras_sel)
            self.text(("> " if sel else "  ") + labels[key], 22, y, GOLD if sel else INK)
            self.text(f"(have {g.parts[key]})", 150, y, DIM)
            self.text(f"x {self.extras[key] or '0'}", 214, y)
            self.text(f"${sub:.2f}", 262, y, DIM)
        self.text(f"${prices['wheel']:.2f} each  (max {D.MAX_SPARE_EACH} of each)", 22, 118, DIM)
        self.text(f"Total: ${total:.2f}     You have ${g.cash():.2f}", 22, 150, INK)
        if self.store_msg:
            self.text(self.store_msg, 22, 166, RED)
        self.center("UP/DOWN choose   type a quantity   ENTER buy   ESC cancel", 186, GOLD)

    def _buy_text(self, item, matts, party, prices):
        """Shopkeeper's advice + recommendation for the selected item.
        Returns (lines, quantity_noun)."""
        if item == "oxen":
            if matts:
                return (["There are 2 oxen in a yoke.",
                         "I recommend at least 3 yoke.",
                         f"I charge ${prices['oxen'] * 2:.0f} a yoke."], "yoke")
            return (["You'll want a strong team of oxen.",
                     f"I charge ${prices['oxen']:.2f} per ox.",
                     "I recommend at least 6 oxen."], "oxen")
        if item == "food":
            return ([f"I recommend at least 200 pounds of food",
                     f"for each person.  You have {party} people.",
                     f"My price is {int(round(prices['food'] * 100))} cents a pound."], "pounds")
        if item == "clothing":
            return (["You'll need warm clothing in the mountains.",
                     "I recommend at least 2 sets per person.",
                     f"Each set is ${prices['clothing']:.2f}."], "sets")
        if item == "ammunition":
            return (["I sell ammunition in boxes of 20 bullets.",
                     f"Each box costs ${prices['ammunition']:.2f}.",
                     "Take plenty if you plan to hunt."], "boxes")
        pname = {"wheel": "wheels", "axle": "axles", "tongue": "tongues"}[item]
        return (["It's a good idea to carry a few spare parts.",
                 f"A wagon {item} costs ${prices[item]:.2f} each.",
                 "I recommend carrying at least one."], pname)

    def _draw_buy_overlay(self):
        g = self.g
        matts = g.landmark == 0
        party = len(g.alive_members())
        prices = g.store_prices()
        lines, noun = self._buy_text(self.store_item, matts, party, prices)
        self.center(self._store_name(), 6)
        self.center(f"{g.date:%B %d, %Y}", 22, GOLD)
        self.rect(RED, (8, 34, LW - 16, 1))
        self.blit("supplies", 88, 44, 144, 60)
        for i, ln in enumerate(lines):
            self.center(ln, 112 + i * 12)
        self.text(f"How many {noun} do you want?  {self.text_input}", 24, 158, GOLD)
        # running cost
        qty = int(self.text_input) if self.text_input.isdigit() else 0
        oxen_mult = 2 if (self.store_item == "oxen" and matts) else 1
        unit_price = prices["oxen"] * oxen_mult if self.store_item == "oxen" else prices[self.store_item]
        self.text(f"Cost: ${unit_price * qty:.2f}    You have ${g.cash():.2f}", 24, 172, DIM)
        self.text("ENTER to buy, ESC to cancel", 24, 186, DIM)

    # Original Deluxe travel-scene bands (logical 320x200): black sky up top with the terrain
    # horizon (grassy prairie on the plains, snow-capped peaks in the Rockies), the
    # wagon/landmark riding high on the black, a mustard foreground band the team stands on,
    # and a white status panel across the bottom.
    HORIZON = 36            # baseline the horizon strip sits on (grass/mountains rise to here)
    GROUND_BOT = 72         # wagon + landmark baseline = top of the mustard foreground band
    BAND_BOT = 118          # bottom of the mustard band = top of the white status panel
    OXEN_LEFT = 150
    PANEL = (248, 248, 244)

    def _ground_color(self):
        """Foreground band color from BOTH the weather and where you are.

        Weather wins at the extremes -- snow blankets everything, a scorching or hot-and-dry
        spell bakes it -- otherwise the location sets the base tone (green plains meadow,
        pale snow-leaning mountains, dry tan valley) and rain darkens/wets it.
        """
        g = self.g
        w = g.weather
        here = g.here()
        if w in ("snowy", "very snowy", "very cold"):
            return GROUND_SNOW                     # snowing / hard freeze -> snow cover
        if w == "very hot":
            return GROUND_BROWN                    # scorched tan-brown
        if w == "hot":
            return GROUND_MUSTARD                  # hot & dry
        if here.get("kind") in (D.VALLEY, D.END):
            base = GROUND_TAN                      # dry valley
        elif here.get("zone", 12) == 12:
            base = GROUND_MTN                      # cold high country, snow-leaning
        else:
            base = GROUND_GREEN                    # lush plains meadow
        if w in ("rainy", "very rainy"):
            base = tuple(int(c * 0.72) for c in base)   # wet weather darkens the ground
        elif w in ("cold", "cool"):
            base = tuple(int(c * 0.85) for c in base)   # overcast/cloudy -> a touch duller
        return base

    def _ground_text(self):
        """Readable text color for the ground band -- dark on the light snow band."""
        r, g, b = self._ground_color()
        return BLACK if (0.3 * r + 0.59 * g + 0.11 * b) > 150 else INK

    def _trail_scene(self, arrived=False):
        g = self.g
        mountains = g.here().get("zone", 12) == 12
        self.rect(BLACK, (0, 0, LW, self.GROUND_BOT))           # black sky / middle distance
        # horizon strip: grassy prairie on the plains, snow-capped mountains in the Rockies
        bg = "bg_mtns" if mountains else "bg_meadow"
        if bg in self.art:
            h = self.art[bg].height
            self.blit(bg, 0, self.HORIZON - h, LW, h)           # rises up to the horizon line
        wi = self._weather_icon()                               # ambient weather in the sky
        if wi and wi in self.art and not self.messages:
            self.blit(wi, LW - self.art[wi].width - 180, 4)
        self.rect(self._ground_color(), (0, self.GROUND_BOT, LW, LH - self.GROUND_BOT))
        moving = self._moving()
        if arrived:
            self._draw_arrived()             # the landmark we just reached, next to the oxen
        else:
            self._draw_approaching()         # the next landmark, approaching down the road
        frame = self._wagon_frame()                             # walking / broken / fire
        img = self.art.get(frame)
        if img:
            bob = int(2 * math.sin(self.anim)) if moving else 0
            self.blit(frame, self.OXEN_LEFT + bob, self.GROUND_BOT - img.height)

    def _status_panel(self):
        """White panel with black status text across the bottom, as in the original."""
        self.rect(self.PANEL, (0, self.BAND_BOT, LW, LH - self.BAND_BOT - 6))
        for i, s in enumerate(self._status()):
            self.center(s, self.BAND_BOT + 5 + i * 11, BLACK)

    def _moving(self):
        return self.state == "traveling" and not self.messages

    def _draw_arrived(self):
        """The landmark we just reached, sitting directly to the left of the oxen."""
        g = self.g
        idx = g.landmark
        if idx >= len(SCENE_SPRITE):
            return
        sprite = SCENE_SPRITE[idx]
        if sprite not in self.art:
            return
        img = self.art[sprite]
        w, h = img.width, img.height
        self.blit(sprite, self.OXEN_LEFT - 6 - w, self.GROUND_BOT - h, w, h)

    def _draw_approaching(self):
        """Show the upcoming landmark's sprite on the horizon, growing as you near it."""
        g = self.g
        n = g.landmark + 1
        while n in g.skip:
            n += 1
        if n >= len(SCENE_SPRITE):
            return
        sprite = SCENE_SPRITE[n]
        if sprite not in self.art:
            return
        target = g.seg_target() or 1
        closeness = min(1.0, g.seg_miles / target)              # 0 far .. 1 arriving
        img = self.art[sprite]
        scale = 0.3 + 0.7 * closeness                           # emerges small, grows in
        w = max(4, round(img.width * scale)); h = max(3, round(img.height * scale))
        # slides along the dirt path from the left edge to directly left of the oxen
        x = round(4 + (self.OXEN_LEFT - 8 - w - 4) * closeness)
        self.blit(sprite, x, self.GROUND_BOT - h, w, h)

    def _wagon_frame(self):
        msg = self.messages[0].lower() if self.messages else ""
        if "fire" in msg:
            return "wagon_fire"
        if "broken wagon" in msg:
            return "wagon_broken"
        if self._moving():                                      # animate oxen only while moving
            return ["wagon_walk2", "wagon_walk1", "wagon_walk0"][int(self.anim * 2) % 3]
        return "wagon_walk0"

    def draw_traveling(self):
        self._trail_scene()
        if not self.messages:
            self.center("Press any key to stop", self.GROUND_BOT + 30, self._ground_text())
            self._status_panel()

    def draw_trailmenu(self):
        g = self.g
        self.center(g.here()["name"] if g.seg_miles == 0 else "On the trail", 4)
        self.center(f"{g.date:%B %d, %Y}", 14, GOLD)
        self.box((8, 26, LW - 16, 42))
        for i, s in enumerate([f"Weather: {g.weather}", f"Health: {g.health()}",
                               f"Pace: {g.pace}", f"Rations: {g.rations}"]):
            self.text(s, 14, 30 + i * 9)
        opts = ["1. Continue on trail", "2. Check supplies", "3. Look at map",
                "4. Change pace", "5. Change food rations", "6. Stop to rest",
                "7. Attempt to trade",
                "8. Talk to people" if self._atfort() else "8. Hunt for food"]
        if self._atfort() and g.store_prices():
            opts.append("9. Buy supplies")
        self.text("You may:", 12, 74)
        for i, o in enumerate(opts):
            self.text(o, 28, 84 + i * 11)
        self.text(f"What is your choice?  {self.choice}", 12, 188, GOLD)

    def draw_landmark(self):
        self._trail_scene(arrived=True)
        g = self.g
        if not self.messages:            # let an arrival event message have the band to itself
            # dialog box on the mustard foreground band (white border, black interior)
            lines = self.wrap(f"You are now at {g.here()['name']}.  "
                              f"Would you like to look around?  {self.choice}", 40)
            self.box((12, 76, LW - 24, len(lines) * 10 + 10))
            for i, ln in enumerate(lines):
                self.center(ln, 80 + i * 10)
        self._status_panel()

    def draw_scene(self):
        g = self.g
        if f"p{g.landmark}" in self.art:
            self.blit(f"p{g.landmark}", 0, 0, LW, 160)
        self.box((60, 168, 200, 24))
        self.center(g.here()["name"], 171)
        self.center(f"{g.date:%B %d, %Y}", 182, GOLD)

    def draw_supplies(self):
        g = self.g
        self.center("Check Supplies", 5, GOLD)
        self.blit("supplies", 68, 14, 184, 78)
        left = [f"Oxen: {g.oxen}", f"Food: {g.food} lbs",
                f"Clothing: {g.clothing} sets", f"Bullets: {g.bullets}"]
        right = [f"Cash: ${g.cash():.2f}",
                 f"Parts: {g.parts['wheel']}w {g.parts['axle']}a {g.parts['tongue']}t",
                 f"Pace: {g.pace}", f"Rations: {g.rations}"]
        for i, r in enumerate(left):
            self.text(r, 24, 104 + i * 13)
        for i, r in enumerate(right):
            self.text(r, 172, 104 + i * 13)
        self.box((8, 158, LW - 16, 22))
        self.text("Party: " + ", ".join(m.name for m in g.alive_members()), 14, 164)
        self.center("Press any key to return", 190, GOLD)

    def draw_map(self):
        self.blit("map", 0, 50, LW, 100)
        self.center("The Oregon Trail", 12, GOLD)
        self.center(f"You are near {self.g.here()['name']} - {self.g.total_miles} miles", 158)
        self.text("Press any key", 12, 190, GOLD)

    def draw_talk(self):
        self._trail_scene(arrived=True)
        spk, adv = self.talk
        self.textbox([f"{spk} tells you:"] + self.wrap(adv, 40), y=112)

    def _hunter_sprite(self):
        h = self.hunt
        f = h.facing
        if h.moving:                                     # walk cycle while holding CTRL
            return f"hunter_{f}_{int(h.walk) % 2}"
        return f"hunter_{f}_stand"                        # standing frame already aims the gun

    def draw_hunt(self):
        h = self.hunt
        if not h:
            return
        self.rect(BLACK, (0, 40, LW, LH - 40))          # black hunting field
        # obstacles, animals and hunter, back-to-front by their base line
        drawables = []
        for o in h.obstacles:
            drawables.append((o.y + o.h, o.kind, o.x, o.y, o.w, o.h))
        for sp, facing, x, y in h.carcasses:              # shot animals lie where they fell
            key = f"{ANIMAL_PREFIX[sp]}_dead_{'r' if facing == 'right' else 'l'}"
            drawables.append((y + 8, key, x, y, None, None))
        for a in h.animals:
            key = f"{ANIMAL_PREFIX[a.species]}_{'r' if a.facing == 'right' else 'l'}"
            key += str(int(self.anim * 3) % 3)           # 3-frame walk cycle
            drawables.append((a.y + a.h, key, a.x, a.y, None, None))
        img = self.art.get(self._hunter_sprite())
        hw = img.width if img else 30
        hh = img.height if img else 34
        drawables.append((h.hy + 4, self._hunter_sprite(),
                          h.hx - hw / 2, h.hy - hh / 2, None, None))
        for _, name, x, y, w, hgt in sorted(drawables, key=lambda d: d[0]):
            self.blit(name, round(x), round(y), w, hgt)
        # bullets
        for b in h.bullets:
            self.rect(GOLD, (round(b.x) - 1, round(b.y) - 1, 3, 3))
        # HUD
        self.rect(BLACK, (0, 0, LW, 40))
        self.rect(RED, (0, 39, LW, 1))
        self.text(f"Bullets: {h.ammo}", 8, 6, INK)
        self.text(f"Meat: {h.bagged} lbs", 8, 22, GOLD)
        secs = max(0, int(math.ceil(h.time_left)))
        self.text(f"Time: {secs}", 250, 6, INK if secs > 4 else RED)
        bar = int(196 * max(0.0, h.time_left) / 15.0)
        self.rect(DIM, (110, 24, 196, 6))
        self.rect(GOLD if secs > 4 else RED, (110, 24, bar, 6))
        if h.flash > 0:                                  # brief hit feedback
            self.rect(INK, (0, 40, LW, LH - 40), 1)
        self.center("Arrows / WASD look  -  CTRL walk  -  SPACE shoot  -  ENTER stop", 190, GOLD)

    def draw_river(self):
        g = self.g
        w, depth = self._river
        self.center(g.here()["name"], 6)
        self.center(f"{g.date:%B %d, %Y}", 18, GOLD)
        self.text(f"River width: {w} feet", 12, 40)
        self.text(f"River depth: {depth} feet", 12, 52)
        self.text("You may:", 12, 72)
        for i, o in enumerate(g.river_options()):
            self.text(f"{i+1}. {o}", 20, 86 + i * 11)
        self.text(f"What is your choice?  {self.choice}", 12, 186, GOLD)

    def draw_foodwarn(self):
        g = self.g
        self._trail_scene()
        self.textbox(self.wrap(f"Your food supply is running low ({g.food} pounds).  "
                               f"Would you like to stop and hunt for food?  {self.choice}", 40),
                     y=110)

    # The crossing plays inside a centred window matching the screen's 1.6 aspect ratio
    # (black bars crop the sides), with the far bank in the upper-left corner and the near
    # bank in the lower-right -- the direction the isometric wagon sprites face.
    CROSS_BOX = (70, 36, 180, 112)     # x, y, width, height  (width/height == 320/200)

    def draw_crossing(self):
        g = self.g
        c = self._cross
        bx, by, bw, bh = self.CROSS_BOX
        bx1, by1 = bx + bw, by + bh
        self.rect(WATER_BLUE, (bx, by, bw, bh))                 # river inside the framed box
        self.poly(GROUND_TAN, [(bx, by), (bx + 72, by), (bx, by + 50)])       # far bank
        self.poly(GROUND_TAN, [(bx1, by1), (bx1 - 72, by1), (bx1, by1 - 50)])  # near bank
        self.center(g.here()["name"], 6)
        self.center(f"{g.date:%B %d, %Y}", 18, GOLD)

        prog = self._cross_progress()
        name = "cross_tipped" if c["tipped"] else c["img"]
        img = self.art.get(name)
        if img:
            w, h = max(1, img.width // 2), max(1, img.height // 2)   # half native size
            # Travel between two centres that both sit on open water -- start just off the
            # near (lower-right) bank, finish short of the far bank, so it never rides onto
            # the tan or past the blue.
            scx, scy = bx1 - 32, by1 - 20                       # near-shore centre
            ecx, ecy = bx + 52, by + 52                         # far-shore centre (still on blue)
            x = (scx + prog * (ecx - scx)) - w
            y = (scy + prog * (ecy - scy)) - h
            if c["tipped"]:
                y += min(12, (c["t"] - c["tip_t"]) * 18)        # lurch down as it swamps
            else:
                y += 1.0 * math.sin(self.anim * 1.2)            # gentle bob while afloat
            self.blit(name, round(x), round(y), w, h)

    def draw_fork(self):
        self._trail_scene(arrived=True)
        lines = ["The trail divides here.  You may:"]
        for i, o in enumerate(self.g.fork_options()):
            lines.append(f"  {i+1}. {o}")
        lines.append(f"What is your choice?  {self.choice}")
        self.textbox(lines, y=110)

    def draw_gameover(self):
        g = self.g
        if g.outcome == "arrived":
            self.blit("p17", 0, 0, LW, 128)
            self.center("You have arrived in Oregon!", 134, GOLD)
        else:
            self.center("Your journey has ended.", 50, RED, self.big)
            self.center({"everyone died": "Everyone in the party has died.",
                         "no oxen": "You have no oxen to pull your wagon."}
                        .get(g.outcome, ""), 90)
        surv = [m.name for m in g.alive_members()]
        self.center(f"Survivors: {', '.join(surv) if surv else 'none'}", 150)
        self.center(f"SCORE: {g.score()}", 164, GOLD)
        self.center("Press SPACE to play again", 184, DIM)

    def draw_learn(self):
        self.blit("banner", 0, 6)
        self.center("Learn about the Trail", 74, GOLD)
        page = LEARN_PAGES[min(self.learn_page, len(LEARN_PAGES) - 1)]
        for i, ln in enumerate(self.wrap(page, 44)):
            self.center(ln, 96 + i * 12)
        last = self.learn_page >= len(LEARN_PAGES) - 1
        self.center(f"({self.learn_page + 1} of {len(LEARN_PAGES)})", 168, DIM)
        self.center("Press SPACE for the menu" if last else "Press SPACE for more", 182, GOLD)

    def draw_topten(self):
        self.center("The Oregon Top Ten", 10, GOLD)
        self.center("Hall of Fame", 22, DIM)
        top = sorted(self.hiscores, key=lambda t: -t[1])[:10]
        for i, (name, score) in enumerate(top):
            y = 42 + i * 13
            self.text(f"{i+1:2}.", 40, y, DIM)
            self.text(name, 66, y)
            self.text(f"{score:>6}", 230, y, GOLD)
        self.center("Press any key to return", 188, GOLD)

    def draw_manage(self):
        self.ornate()
        self.center("Management Options", 24, GOLD)
        for i, o in enumerate([f"Sound is currently {'ON' if self.sound else 'OFF'}",
                               "Difficulty: standard",
                               "Saved games: none",
                               "(classroom management area)"]):
            self.center(o, 60 + i * 16)
        self.center("Press any key to return", 186, GOLD)

    def ornate(self, y=12):
        self.rect(BROWN, (20, y, LW - 40, 1))
        self.rect(GOLD, (LW // 2 - 6, y - 1, 12, 2))

    def draw_confirm(self):
        self.center("Leaving the Oregon Trail", 60, GOLD)
        self.textbox(self.wrap("Are you sure you want to return to the main menu?  "
                               "Your current journey will be lost.", 40)
                     + ["", f"Press Y for yes, N to keep playing.  {self.choice}"], y=96)


def main():
    UI().start()


if __name__ == "__main__":
    main()

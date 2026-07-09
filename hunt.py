"""Interactive hunting minigame for The Oregon Trail Deluxe port.

This is pure simulation -- no rendering.  The tkinter front end (gui.py) feeds it the
set of currently-held keys and a per-frame delta time, then draws the hunter, animals,
bullets and obstacles it tracks.  The player walks the hunter around a grassland with
the arrow keys (or W/A/S/D) and fires in the facing direction with SPACE.  Meat bagged
is tallied when the hunt ends; the engine then caps how much can be carried back.

Frame/art details (which sprite sheet, which crop) live in gui.py; here an animal only
knows its species, hitbox, speed and meat value.
"""
from __future__ import annotations

# --- gameplay parameters (logical MCGA pixels; speeds are px/second) -----------
# w/h = hitbox, speed = (min,max), value = meat pounds (min,max), weight = spawn odds,
# terrain = "any" (plains + mountains) or "mountain" (only shows up in the Rockies).
SPECIES = {
    "buffalo":  dict(w=26, h=17, speed=(26, 40),   value=(300, 520), weight=2, terrain="any"),
    "bear":     dict(w=27, h=14, speed=(30, 48),   value=(120, 220), weight=1, terrain="mountain"),
    "buck":     dict(w=25, h=20, speed=(55, 80),   value=(45, 70),   weight=3, terrain="any"),
    "deer":     dict(w=27, h=20, speed=(60, 85),   value=(30, 50),   weight=3, terrain="any"),
    "rabbit":   dict(w=14, h=12, speed=(80, 112),  value=(2, 4),     weight=5, terrain="any"),
    "squirrel": dict(w=22, h=11, speed=(90, 120),  value=(1, 3),     weight=5, terrain="mountain"),
}

# tkinter keysyms that TURN the hunter (arrows + WASD, either case). Turning only
# changes where he looks; he holds still until you press the walk key.
FACE_KEYS = {
    "Left": "left", "a": "left", "A": "left",
    "Right": "right", "d": "right", "D": "right",
    "Up": "up", "w": "up", "W": "up",
    "Down": "down", "s": "down", "S": "down",
}
# hold to walk forward in the direction he's facing
WALK_KEYS = {"Control_L", "Control_R", "Control"}

# obstacle display/hitbox sizes, keyed by the art name gui.py loads (each roughly its
# terrain.png crop scaled up, keeping that crop's aspect ratio so nothing looks squashed).
OBSTACLE_SIZE = {
    "tree1": (44, 52), "tree2": (42, 53), "tree3": (21, 41), "tree4": (25, 36),
    "tree5": (45, 50), "tree6": (36, 51), "tree7": (42, 51),
    "bush_purple": (31, 26), "bush_yellow": (39, 34), "bush_blue": (31, 29),
    "bush_red": (46, 14), "rock1": (47, 20), "rock2": (39, 20),
}
# obstacle kinds that are solid to animals (they can't walk through the big boulders)
ANIMAL_SOLID = {"rock1", "rock2"}

HUNTER_SPEED = 62.0        # logical px / second
BULLET_SPEED = 240.0
RELOAD = 0.28              # seconds you must wait between shots
HUNT_SECONDS = 15.0        # length of a hunt
MAX_ANIMALS = 2


class Animal:
    __slots__ = ("species", "x", "y", "vx", "w", "h", "value", "facing")

    def __init__(self, species, x, y, vx, w, h, value):
        self.species = species
        self.x, self.y, self.vx = x, y, vx       # x,y = top-left; vx = horizontal speed
        self.w, self.h, self.value = w, h, value
        self.facing = "right" if vx > 0 else "left"


class Bullet:
    __slots__ = ("x", "y", "vx", "vy")

    def __init__(self, x, y, vx, vy):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy


class Obstacle:
    __slots__ = ("kind", "x", "y", "w", "h")

    def __init__(self, kind, x, y, w, h):
        self.kind, self.x, self.y, self.w, self.h = kind, x, y, w, h


class Hunt:
    def __init__(self, rng, ammo, field, mountains=False):
        self.rng = rng
        self.ammo = ammo                         # bullets remaining (local copy)
        self.x0, self.y0, self.x1, self.y1 = field
        self.mountains = mountains
        self.hx = (self.x0 + self.x1) / 2         # hunter centre
        self.hy = (self.y0 + self.y1) / 2
        self.facing = "down"
        self.walk = 0.0                           # walk-cycle phase (for animation)
        self.moving = False
        self.reload = 0.0
        self.time_left = HUNT_SECONDS
        self.bagged = 0                           # pounds of meat shot
        self.kills = 0
        self.flash = 0.0                          # brief "you hit one" flash timer
        self.done = False
        self.animals: list[Animal] = []
        self.bullets: list[Bullet] = []
        self.carcasses: list[list] = []          # [species, facing, x, y] -- stay all hunt
        self.spawn_t = 0.5
        self.obstacles = self._make_obstacles()

    # -------------------------------------------------------------- setup
    def _make_obstacles(self):
        obs = []
        kinds = list(OBSTACLE_SIZE)
        for _ in range(self.rng.randint(5, 8)):
            kind = self.rng.choice(kinds)
            w, h = OBSTACLE_SIZE[kind]
            x = self.rng.uniform(self.x0 + 6, self.x1 - 6 - w)
            y = self.rng.uniform(self.y0 + 4, self.y1 - h)
            if abs(x - self.hx) < 32 and abs(y - self.hy) < 28:
                continue                          # keep the hunter's start clear
            obs.append(Obstacle(kind, x, y, w, h))
        return obs

    def _pick_species(self):
        # plains: buffalo, buck, deer, rabbit.  Mountains: those plus bear and squirrel.
        names = [n for n, s in SPECIES.items()
                 if self.mountains or s["terrain"] == "any"]
        weights = [SPECIES[n]["weight"] for n in names]
        return self.rng.choices(names, weights)[0]

    def _spawn(self):
        name = self._pick_species()
        s = SPECIES[name]
        speed = self.rng.uniform(*s["speed"])
        from_left = self.rng.random() < 0.5
        vx = speed if from_left else -speed
        x = self.x0 - s["w"] if from_left else self.x1
        y = self.rng.uniform(self.y0 + 2, self.y1 - s["h"])
        value = self.rng.randint(*s["value"])
        self.animals.append(Animal(name, x, y, vx, s["w"], s["h"], value))

    def face(self, direction):
        """Turn to look a new way (arrow / WASD). Does not move him."""
        self.facing = direction

    # ------------------------------------------------------- per-frame update
    def update(self, dt, held):
        if self.done:
            return
        self.time_left -= dt
        self.reload = max(0.0, self.reload - dt)
        self.flash = max(0.0, self.flash - dt)
        self._move_hunter(dt, bool(held & WALK_KEYS))
        self._move_bullets(dt)
        self._move_animals(dt)
        self.spawn_t -= dt
        if self.spawn_t <= 0 and len(self.animals) < MAX_ANIMALS:
            self._spawn()
            self.spawn_t = self.rng.uniform(0.6, 1.7)
        if self.time_left <= 0 or (self.ammo <= 0 and not self.bullets):
            self.done = True

    def _move_hunter(self, dt, walking):
        self.moving = walking
        if not walking:
            return
        dx = -1 if self.facing == "left" else 1 if self.facing == "right" else 0
        dy = -1 if self.facing == "up" else 1 if self.facing == "down" else 0
        step = HUNTER_SPEED * dt
        self.hx = min(self.x1, max(self.x0, self.hx + dx * step))
        self.hy = min(self.y1, max(self.y0, self.hy + dy * step))
        self.walk += dt * 8

    def _move_bullets(self, dt):
        alive = []
        for b in self.bullets:
            b.x += b.vx * dt
            b.y += b.vy * dt
            if not (self.x0 - 6 <= b.x <= self.x1 + 6 and self.y0 - 8 <= b.y <= self.y1 + 6):
                continue
            if self._blocked(b.x, b.y):
                continue
            hit = self._hit_animal(b.x, b.y)
            if hit is not None:
                self.bagged += hit.value
                self.kills += 1
                self.flash = 0.18
                self.carcasses.append([hit.species, hit.facing, hit.x, hit.y])
                self.animals.remove(hit)
                continue
            alive.append(b)
        self.bullets = alive

    def _move_animals(self, dt):
        keep = []
        for a in self.animals:
            a.x += a.vx * dt
            if self._hits_boulder(a):            # can't walk through a big boulder -> turn back
                a.x -= a.vx * dt
                a.vx = -a.vx
                a.facing = "right" if a.vx > 0 else "left"
            if a.vx > 0 and a.x > self.x1 + 4:
                continue
            if a.vx < 0 and a.x + a.w < self.x0 - 4:
                continue
            keep.append(a)
        self.animals = keep

    def _hits_boulder(self, a):
        for o in self.obstacles:
            if o.kind not in ANIMAL_SOLID:
                continue
            if a.x < o.x + o.w and a.x + a.w > o.x and a.y < o.y + o.h and a.y + a.h > o.y:
                return True
        return False

    def _hit_animal(self, x, y):
        for a in self.animals:
            if a.x <= x <= a.x + a.w and a.y <= y <= a.y + a.h:
                return a
        return None

    def _blocked(self, x, y):
        """A tree/rock stops a bullet -- only its solid lower part, so grazing the
        canopy still lets a shot through (and animals can be safe behind cover)."""
        for o in self.obstacles:
            if o.x <= x <= o.x + o.w and o.y + o.h * 0.45 <= y <= o.y + o.h:
                return True
        return False

    def shoot(self):
        if self.done or self.reload > 0 or self.ammo <= 0:
            return
        self.ammo -= 1
        self.reload = RELOAD
        vx = (-1 if self.facing == "left" else 1 if self.facing == "right" else 0) * BULLET_SPEED
        vy = (-1 if self.facing == "up" else 1 if self.facing == "down" else 0) * BULLET_SPEED
        ox = 5 if self.facing == "right" else -5 if self.facing == "left" else 2 if self.facing == "up" else -5
        oy = 8 if self.facing == "down" else -8 if self.facing == "up" else -9 if self.facing == "left" else -5
        self.bullets.append(Bullet(self.hx + ox, self.hy + oy, vx, vy))

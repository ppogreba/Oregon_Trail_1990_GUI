"""The Oregon Trail Deluxe - game engine (UI-agnostic).

Drives all recovered rules: setup, Matt's store & fort stores, day-by-day travel with
events, river crossings, forks, health/rations/pace, and Hall-of-Fame scoring. The
tkinter Deluxe UI (gui.py) calls these methods and renders results.

Written without decorators: plain classes, a normal constructor for setup, and regular
methods (cash(), here(), alive_members(), health()) in place of properties.
"""
from __future__ import annotations
import random
from datetime import date, timedelta

from . import data as D
from .content import DIALOGS


class Member:
    def __init__(self, name, alive=True, affliction=None):
        self.name = name
        self.alive = alive
        self.affliction = affliction        # e.g. "a broken leg", or a disease


class Game:
    def __init__(self, profession_key="banker", names=None, month="March"):
        # party / profession
        self.profession = next(p for p in D.PROFESSIONS if p["key"] == profession_key)
        self.rng = random.Random()
        names = names or ["Ma", "Pa", "Kid1", "Kid2", "Kid3"]
        self.members = [Member(n) for n in names[:D.PARTY_SIZE]]
        while len(self.members) < D.PARTY_SIZE:
            self.members.append(Member(f"Member{len(self.members) + 1}"))
        # resources
        self.cash_cents = round(self.profession["cash"] * 100)
        self.food = 0                       # pounds
        self.oxen = 0                       # head of oxen (2 per yoke)
        self.clothing = 0                   # sets
        self.bullets = 0
        self.parts = {"wheel": 0, "axle": 0, "tongue": 0}
        # position / time
        self.landmark = 0                   # index into D.LANDMARKS (current/last-passed)
        self.seg_miles = 0                  # miles travelled into the current segment
        self.total_miles = 0
        self.date = date(D.START_YEAR, 3 + D.MONTHS.index(month), 1)
        # settings / condition
        self.weather = "cold" if month in ("March", "April") else "warm"
        self.pace = "steady"
        self.rations = "filling"
        self.health_val = 0.0               # 0 = perfect; higher = worse
        self.finished = False
        self.outcome = None                 # "arrived" | "everyone died" | "no oxen"
        # route bookkeeping
        self.skip = set()                   # landmark indices bypassed by a fork
        self.miles_override = {}            # landmark idx -> miles to next
        self.route = {}                     # fork name -> chosen option
        self.crossed = set()                # river landmark indices already crossed
        self.forked = set()                 # fork landmark indices already resolved

    # --------------------------------------------------------------- economy
    def cash(self):
        return self.cash_cents / 100

    def here(self):
        return D.LANDMARKS[self.landmark]

    def seg_target(self):
        """Miles from the current landmark to the next (honouring fork overrides)."""
        return self.miles_override.get(self.landmark, self.here()["miles"])

    def trail_total(self):
        total, i = 0, 0
        while i < len(D.LANDMARKS) - 1:
            if i not in self.skip:
                total += self.miles_override.get(i, D.LANDMARKS[i]["miles"])
            i += 1
        return total

    def store_prices(self):
        """Per-unit prices at the current landmark (None if no store here)."""
        here = self.here()
        if self.landmark != 0 and here["kind"] != D.FORT:
            return None
        f = D.price_factor(here["name"])
        return {k: round(v * f, 2) for k, v in D.BASE_PRICES.items()}

    def buy(self, item, qty):
        """Buy qty units of item. Returns (ok, message)."""
        prices = self.store_prices()
        if prices is None:
            return False, "There is no store here."
        unit = prices[item]
        cost = round(unit * qty * 100)
        if cost > self.cash_cents:
            return False, "You cannot afford that."
        # limit checks
        if item == "oxen" and self.oxen + qty > D.MAX_OXEN:
            return False, f"You may only take {D.MAX_OXEN} oxen."
        if item == "food" and self.food + qty > D.MAX_FOOD:
            return False, f"Your wagon may only carry {D.MAX_FOOD} pounds of food."
        if item in self.parts and self.parts[item] + qty > D.MAX_SPARE_EACH:
            return False, f"Your wagon may only carry {D.MAX_SPARE_EACH}."
        self.cash_cents -= cost
        if item == "oxen":
            self.oxen += qty
        elif item == "food":
            self.food += qty
        elif item == "clothing":
            self.clothing += qty
        elif item == "ammunition":
            self.bullets += qty * D.BULLETS_PER_BOX
        elif item in self.parts:
            self.parts[item] += qty
        return True, "Purchased."

    # ------------------------------------------------------------- condition
    def alive_members(self):
        return [m for m in self.members if m.alive]

    def health(self):
        """Map the numeric health accumulator to a Deluxe health level."""
        v = self.health_val
        if v < 40:
            return "good"
        if v < 85:
            return "fair"
        if v < 130:
            return "poor"
        return "very poor"

    # ---------------------------------------------------------------- travel
    def _daily_miles(self):
        base = D.PACE_MILES[self.pace]
        zone = self.here().get("zone", 12)
        miles = base * D.TERRAIN_FACTOR.get(zone, 1.0)
        # fewer than a full team slows you; sick oxen etc. (approx)
        miles *= min(1.0, self.oxen / 6.0) if self.oxen else 0.0
        miles *= self.rng.uniform(0.85, 1.15)
        return max(0, int(round(miles)))

    def _consume_food(self):
        need = len(self.alive_members()) * D.RATION_LBS[self.rations]
        if self.food >= need:
            self.food -= need
            return 0
        short = need - self.food
        self.food = 0
        return short          # people go hungry -> health hit

    def _health_step(self, hungry_short):
        stress = {"steady": 0.5, "strenuous": 2.0, "grueling": 4.0}[self.pace]
        stress += {"filling": 0.0, "meager": 1.5, "bare bones": 3.0}[self.rations]
        if self.weather in ("very cold", "very hot", "very snowy", "very rainy"):
            stress += 2.0
        if self.clothing < len(self.alive_members()) and \
                self.weather in ("cold", "very cold", "snowy", "very snowy"):
            stress += 2.0
        if hungry_short:
            stress += 4.0
        # afflicted/sick members raise party stress
        stress += sum(1.5 for m in self.alive_members() if m.affliction)
        # baseline recovery when travelling with decent conditions
        self.health_val = min(160.0, max(0.0, self.health_val + stress - 3.2))

    def rest(self, days):
        days = max(0, min(days, D.MAX_REST_DAYS))
        for _ in range(days):
            self.date += timedelta(days=1)
            self._consume_food()
            self.health_val = max(0.0, self.health_val - 6.0)
            for m in self.alive_members():
                if m.affliction and self.rng.random() < 0.35:
                    m.affliction = None      # recover
        return f"You rested {days} day{'s' if days != 1 else ''}."

    def travel_one_day(self):
        """Advance one day. Returns list of message strings (events)."""
        msgs = []
        if self.finished:
            return msgs
        if self.oxen <= 0:
            self.finished = True
            self.outcome = "no oxen"
            return ["You have no oxen to pull your wagon."]
        self.date += timedelta(days=1)
        miles = self._daily_miles()
        # don't overshoot the next landmark
        remaining = self.seg_target() - self.seg_miles
        if self.here()["kind"] != D.END and miles >= remaining:
            miles = remaining
        self.seg_miles += miles
        self.total_miles += miles
        hungry = self._consume_food()
        if hungry:
            msgs.append("There is not enough food; the party goes hungry.")
        self._health_step(hungry)
        # afflictions/illness can heal over time on the trail
        for m in self.alive_members():
            if m.affliction and self.rng.random() < 0.09:
                m.affliction = None
        self._weather_step()
        # random trail event
        ev = self._maybe_event()
        if ev:
            msgs.append(ev)
        # deaths
        msgs += self._check_deaths()
        # reached a landmark?
        if self.here()["kind"] != D.END and self.seg_miles >= self.seg_target():
            self.landmark += 1
            while self.landmark in self.skip:
                self.landmark += 1
            self.seg_miles = 0
            msgs.append(f"You are now at {self.here()['name']}.")
            if self.here()["kind"] == D.END:
                self.finished = True
                self.outcome = "arrived"
        return msgs

    def _weather_step(self):
        if self.rng.random() < 0.25:
            self.weather = self.rng.choice(D.WEATHER)

    # ----------------------------------------------------------------- events
    def _maybe_event(self):
        if self.rng.random() > 0.13:      # [tune] ~13% chance/day of an event
            return None
        roll = self.rng.random()
        m = self.rng.choice(self.alive_members())
        if roll < 0.14:
            if self.rng.random() < 0.4 and self.food > 20:
                lost = self.rng.randint(10, 40)
                self.food = max(0, self.food - lost)
                return f"A thief comes during the night and steals {lost} pounds of food."
            lost = min(self.clothing, self.rng.randint(1, 3))
            if lost:
                self.clothing -= lost
                return f"A thief comes during the night and steals {lost} sets of clothing."
        if roll < 0.24:
            self.food += self.rng.randint(5, 20)
            return "Find wild fruit."
        if roll < 0.36:
            d = self.rng.randint(1, 3)
            self.date += timedelta(days=d)
            return f"Wrong trail.  Lose {d} day{'s' if d != 1 else ''}."
        if roll < 0.46:
            self.date += timedelta(days=2)
            return "Ox wanders off.  Lose 2 days."
        if roll < 0.58:
            m.affliction = self.rng.choice(D.AFFLICTIONS)
            self.health_val += 8
            return f"{m.name} has {m.affliction}."
        if roll < 0.70:
            m.affliction = self.rng.choice(D.DISEASES)
            self.health_val += 12
            return f"{m.name} has {m.affliction}."
        if roll < 0.80:
            part = self.rng.choice(list(self.parts))
            if self.parts[part] > 0:
                self.parts[part] -= 1
                return f"Broken wagon {part}.  You were able to repair it."
            self.date += timedelta(days=self.rng.randint(1, 3))
            return f"Broken wagon {part}.  You must replace it with a spare part."
        if roll < 0.88:
            lost = min(self.food, self.rng.randint(10, 40))
            self.food -= lost
            return f"A fire in the wagon results in the loss of {lost} pounds of food."
        return "You pass a gravesite."

    def _check_deaths(self):
        msgs = []
        if self.health() == "very poor":
            for m in self.alive_members():
                if m.affliction and self.rng.random() < 0.04:
                    m.alive = False
                    msgs.append(f"{m.name} has died.")
        if not self.alive_members():
            self.finished = True
            self.outcome = "everyone died"
            msgs.append("Everyone in the party has died.")
        return msgs

    # ------------------------------------------------------------ river/fork
    def river_options(self):
        here = self.here()
        opts = ["attempt to ford the river", "caulk the wagon and float it across"]
        if here.get("ferry"):
            opts.append("take a ferry across")
        if here.get("guide"):
            opts.append("hire an Indian to help")
        opts += ["wait to see if conditions improve", "get more information"]
        return opts

    def river_state(self):
        width = self.rng.randint(100, 1000)
        depth = round(self.rng.uniform(1.5, 8.0), 1)
        return width, depth

    def cross_river(self, method, depth):
        """method: 'ford'|'caulk'|'ferry'|'guide'. Returns message."""
        here = self.here()
        if method == "guide" and here.get("guide"):
            if self.clothing >= D.SNAKE_GUIDE_CLOTHING:
                self.clothing -= D.SNAKE_GUIDE_CLOTHING
                return "The guide takes your wagon safely across."
            return "You cannot afford the guide's price."
        if method == "ferry" and here.get("ferry"):
            self.cash_cents -= 500
            return "You take the ferry across."
        risk = 0.05
        if method == "ford":
            risk = 0.1 + max(0, depth - D.FORD_SAFE_DEPTH) * 0.18
        elif method == "caulk":
            risk = 0.08 + max(0, depth - 4.0) * 0.06
        if self.rng.random() < risk:
            lost = self.rng.randint(20, 80)
            self.food = max(0, self.food - lost)
            self.date += timedelta(days=1)
            return "Your wagon tips in the river.  You lose supplies and a day."
        return "You made the crossing successfully."

    # ------------------------------------------------------- talk / hunt / fork
    def talk_to_people(self):
        """[bin] Pick a trail-appropriate advice record from DIALOGS.REC."""
        total = self.trail_total() or 1
        frac = min(0.999, self.total_miles / total)
        idx = int(frac * len(DIALOGS))
        lo, hi = max(0, idx - 1), min(len(DIALOGS) - 1, idx + 1)
        rec = DIALOGS[self.rng.randint(lo, hi)]
        return rec["speaker"], rec["advice"]

    def finish_hunt(self, pounds_shot):
        """Apply the result of the interactive hunting minigame (gui.py).

        The GUI already decremented bullets shot-by-shot; here we just carry the meat
        back (classic ~100 lb wagon cap) and spend the day the hunt took.
        """
        carried = min(100, pounds_shot)
        self.food = min(D.MAX_FOOD, self.food + carried)
        self.date += timedelta(days=1)
        if carried <= 0:
            return "You were unable to shoot any game."
        return (f"You shot {pounds_shot} pounds of food, but could only "
                f"carry {carried} pounds back to the wagon.")

    def fork_options(self):
        key = self.here().get("fork")
        return D.FORKS[key]["options"] if key else None

    def choose_fork(self, choice_index):
        """Resolve a trail fork. Returns a message."""
        key = self.here().get("fork")
        self.forked.add(self.landmark)      # so _continue() won't re-trigger this fork forever
        if key == "south_pass":
            if choice_index == 0:               # Sublette Cutoff -> Green River
                self.skip.add(8)                # bypass Fort Bridger
                self.miles_override[7] = 57
                self.route[key] = "Green River"
                return "You take the Sublette Cutoff toward the Green River."
            self.skip.add(9)                    # bypass Green River crossing
            self.miles_override[7] = 125
            self.route[key] = "Fort Bridger"
            return "You head for Fort Bridger."
        if key == "the_dalles":
            if choice_index == 0:
                self.route[key] = "Columbia"
                return "You will float down the Columbia River."
            self.route[key] = "Barlow"
            self.cash_cents -= 900              # [bin] Barlow toll prompt (~$9 shown)
            return "You pay the toll and take the Barlow Road."
        return ""

    # ---------------------------------------------------------------- scoring
    def score(self):
        pts = 0
        health = self.health()
        for _ in self.alive_members():
            pts += D.SCORE_HEALTH[health]
        pts += 1 * D.SCORE_RESOURCE["wagon"]
        pts += self.oxen * D.SCORE_RESOURCE["ox"]
        pts += sum(self.parts.values()) * D.SCORE_RESOURCE["spare_part"]
        pts += self.clothing * D.SCORE_RESOURCE["clothing"]
        pts += (self.bullets // 50) * D.SCORE_RESOURCE["bullets_per_50"]
        pts += (self.food // 25) * D.SCORE_RESOURCE["food_per_25"]
        pts += int(self.cash() // 5) * D.SCORE_RESOURCE["cash_per_5"]
        return pts * self.profession["score_mult"]

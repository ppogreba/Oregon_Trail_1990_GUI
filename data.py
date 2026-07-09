"""Recovered game data for The Oregon Trail Deluxe (1990).

Provenance tags:
  [bin]  = read directly from the unpacked OREGON.EXE (claude/OREGON_unpacked.img)
  [obs]  = observed live in DOSBox-X during a real playthrough
  [tune] = derived/approximate; matches observations but not byte-exact yet
Full notes: claude/DATA_TABLES.md
"""

# --- Landmarks / trail -------------------------------------------------------
# kind: town | river | fort | rock | pass | valley | end
# miles: distance to the NEXT landmark on the MAIN route
# zone:  grazing/terrain zone byte [bin] (20 = eastern plains, 12 = mountains)
TOWN, RIVER, FORT, ROCK, PASS, VALLEY, END = "town river fort rock pass valley end".split()

# [bin] landmark table @ image 0x22ba7 (18 fixed 37-byte records); [obs] mileages verified.
LANDMARKS = [
    dict(name="Independence",                kind=TOWN,   miles=102, zone=20),
    dict(name="the Kansas River crossing",   kind=RIVER,  miles=83,  zone=20, ferry=True),
    dict(name="the Big Blue River crossing", kind=RIVER,  miles=119, zone=20, ferry=False),
    dict(name="Fort Kearney",                kind=FORT,   miles=250, zone=20),
    dict(name="Chimney Rock",                kind=ROCK,   miles=86,  zone=20),
    dict(name="Fort Laramie",                kind=FORT,   miles=190, zone=12),
    dict(name="Independence Rock",           kind=ROCK,   miles=102, zone=12),
    dict(name="South Pass",                  kind=PASS,   miles=125, zone=12, fork="south_pass"),
    dict(name="Fort Bridger",                kind=FORT,   miles=162, zone=12),
    dict(name="Green River crossing",        kind=RIVER,  miles=144, zone=12, ferry=True),
    dict(name="Soda Springs",                kind=ROCK,   miles=57,  zone=12),
    dict(name="Fort Hall",                   kind=FORT,   miles=182, zone=12),
    dict(name="the Snake River crossing",    kind=RIVER,  miles=114, zone=12, guide=True),
    dict(name="Fort Boise",                  kind=FORT,   miles=160, zone=12),
    dict(name="the Blue Mountains",          kind=PASS,   miles=55,  zone=12),  # fork in orig; branches not yet mapped
    dict(name="Fort Walla Walla",            kind=FORT,   miles=120, zone=12),
    dict(name="The Dalles",                  kind=ROCK,   miles=100, zone=12, fork="the_dalles"),
    dict(name="the Willamette Valley",       kind=END,    miles=0,   zone=12),
]

# [obs] Forks. South Pass: Fort Bridger branch = 125 mi (observed); the Sublette Cutoff to
# Green River = 57 mi [bin] and rejoins ahead. (Blue Mtns / Dalles branches modelled simply.)
FORKS = {
    "south_pass": dict(
        prompt="The trail divides here.",
        options=["head for Green River crossing", "head for Fort Bridger", "see the map"],
    ),
    "the_dalles": dict(
        prompt="The trail divides here.",
        options=["float down the Columbia River", "take the Barlow Toll Road", "see the map"],
    ),
}

# --- Store / economy ---------------------------------------------------------
# [obs] Matt's General Store, Independence base prices (dollars). Money handled in cents.
BASE_PRICES = {
    "oxen": 20.00,       # per OX (Matt's sells per YOKE=2 -> $40/yoke); forts sell per ox
    "food": 0.20,        # per pound
    "clothing": 10.00,   # per set
    "ammunition": 2.00,  # per box of 20 bullets
    "wheel": 10.00, "axle": 10.00, "tongue": 10.00,  # spare parts, each
}
BULLETS_PER_BOX = 20     # [obs]
OXEN_PER_YOKE = 2        # [obs]

# [obs] Fort price factor rises +0.25 per fort, west to east. Verified at 5 stores:
# Independence 1.0, Laramie 1.5, Bridger 1.75, Hall 2.0, Boise 2.25 (Kearney 1.25, Walla 2.5 by rule).
FORT_NUMBER = {  # store's ordinal along the trail (Independence = 0 = base)
    "Fort Kearney": 1, "Fort Laramie": 2, "Fort Bridger": 3,
    "Fort Hall": 4, "Fort Boise": 5, "Fort Walla Walla": 6,
}

def price_factor(store_name):
    """[obs] factor = 1.0 + 0.25 * fort_number (Independence -> 1.0)."""
    return 1.0 + 0.25 * FORT_NUMBER.get(store_name, 0)

# [obs] purchase limits & shopkeeper recommendations
MAX_OXEN = 20            # [bin] "You may only take 20 oxen"
MAX_FOOD = 2000          # [bin] "only carry 2000 pounds of food"
MAX_SPARE_EACH = 3       # [bin] "only carry 3 <part>"
REC_FOOD_PER_PERSON = 200
REC_OXEN_YOKE = 3
REC_CLOTHING_PER_PERSON = 2

# --- Professions -------------------------------------------------------------
# [obs] banker $1600 confirmed on screen (money in cents); carpenter/farmer folklore [tune].
PROFESSIONS = [
    dict(key="banker",    label="banker from Boston",    cash=1600.00, score_mult=1),
    dict(key="carpenter", label="carpenter from Ohio",   cash=800.00,  score_mult=2),
    dict(key="farmer",    label="farmer from Illinois",  cash=400.00,  score_mult=3),
]

# --- Enumerations ([bin] DGROUP length-prefixed tables @ ~0x22f98) -----------
WEATHER  = ["very cold", "cold", "cool", "warm", "hot", "very hot",
            "rainy", "snowy", "very rainy", "very snowy"]
HEALTH   = ["good", "fair", "poor", "very poor"]              # index 0..3
PACE     = ["steady", "strenuous", "grueling"]
RATIONS  = ["filling", "meager", "bare bones"]
DISEASES = ["typhoid", "cholera", "measles", "dysentery", "a fever"]
AFFLICTIONS = ["a snakebite", "a broken arm", "a broken leg", "exhaustion"]  # event-driven

# [bin] scoring "The Oregon Top Ten"
SCORE_HEALTH = {"good": 500, "fair": 400, "poor": 300, "very poor": 200}
SCORE_RESOURCE = {  # points per unit brought safely to Oregon
    "wagon": 50, "ox": 4, "spare_part": 2, "clothing": 2,
    "bullets_per_50": 1, "food_per_25": 1, "cash_per_5": 1,
}

# --- Time / pace / rations model ---------------------------------------------
MONTHS = ["March", "April", "May", "June", "July"]      # [bin] departure choices
START_YEAR = 1848                                        # [bin]

# [tune] food eaten per person per day by ration level (obs: ~12-15/day for 5 at filling)
RATION_LBS = {"filling": 3, "meager": 2, "bare bones": 1}

# [tune] base miles/day per pace on good terrain; multiplied by a terrain factor.
# obs: steady ~13-18 on plains, ~10-12 in mountains.
PACE_MILES = {"steady": 18, "strenuous": 24, "grueling": 30}
TERRAIN_FACTOR = {20: 1.0, 12: 0.62}   # zone byte -> mileage multiplier [tune]

MAX_REST_DAYS = 9        # [bin] "0-9"
PARTY_SIZE = 5           # leader + 4 [bin]

# [obs] river crossing: Snake River Shoshoni guide costs 2 sets of clothing
SNAKE_GUIDE_CLOTHING = 2
FORD_SAFE_DEPTH = 2.5    # feet; deeper risks swamping (classic threshold) [tune]

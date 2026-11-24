# DeskCat

A tiny animated cat companion that wanders your screen while you work.
Built for Mac and Windows with PyQt6 - a real vector-drawn cat with a
truly transparent window (no white box).

**Windows download:** [DeskCat.exe](https://github.com/shahirislam/DeskCat/releases/latest/download/DeskCat.exe).
One file, nothing to install, just double-click it. The first time, Windows
may ask you to click "More info" then "Run anyway".

## What it does

- A small cat strolls around the screen: legs walk, tail swishes, it blinks,
  breathes, and sits down to look around.
- It walks on gentle invisible hills: a little uphill is fine, downhill is
  easier, so over time it drifts toward the bottom of the screen.
- To go a long way up it chews gum, blows a bubble (the first one always
  pops), then floats up holding it. Small, medium and huge bubbles carry it
  about a quarter, half, or nearly the whole screen. At the top the bubble
  pops and the cat lands on its feet.
- To come a long way down it either parachutes under a small bubble, or
  crouches and jumps to a lower spot.
- Sometimes a bubble bursts halfway (going up or parachuting down) and the
  cat drops all the way to the bottom of the screen, landing a bit
  embarrassed.
- Every 2 to 4 minutes a bowl of food pops up at a random spot. The cat notices,
  makes its own way there (walking if it is close, by bubble if it is high
  up, by parachute or jump if it is below), eats until the bowl is empty,
  then sits down content while the bowl fades away. Clicks pass straight
  through the bowl. Scare the cat off mid-meal and it comes back to finish.
- Half a minute to two minutes after a meal it needs the toilet. Usually a litter
  box appears at a random spot: the cat travels there, squats with a very
  strained face, scratches litter over it and walks off as the box fades.
  Up to about two times in five it has an accident right where it stands instead
  and slinks away embarrassed. Click the poop to clean it up (it sparkles
  and vanishes); left alone it fades by itself after 10 minutes.
- It has a life of its own:
  - **Naps:** every 6 to 12 minutes it yawns, curls up and sleeps for about
    a minute with little z's drifting up. Between 22:00 and 07:00 naps last
    3 to 6 minutes. Click a sleeping cat and it wakes up grumpy and glares
    at you (click again to shoo it). Meals and toilet trips wait until it
    wakes; an overdue bubble ride wakes it.
  - **Washing:** it sits and licks a paw after a meal, after an accident,
    usually after the litter box, and now and then in between.
  - **Stretch and yawn:** after every nap, and sometimes after sitting.
  - **Zoomies:** every 10 to 25 minutes, and often straight after the litter
    box, it tears back and forth across the screen a few times.
- Click it and it jumps, then dashes to the far side of the screen. Click it
  mid-flight and the bubble pops first.
- Every 25 minutes it pops up big in the middle of the screen to remind you
  to take a break. Click it (or wait a few seconds) and it goes back to
  wandering.
- Right-click the cat to quit.

## Install

Needs Python 3.10+ and PyQt6 (one-time install):

Mac:

```
python3 -m pip install --user PyQt6
```

Windows: nothing to install by hand — just double-click `run_windows.bat`.
It installs Python and PyQt6 automatically the first time (needs internet).

(Or install from requirements.txt: `pip install -r requirements.txt`.
If pip complains the environment is externally managed, use a venv:
`python3 -m venv .venv`, activate it, then `pip install PyQt6`.)

## Run

Mac, from a terminal in this folder:

```
python3 deskcat.py
```

Windows: double-click `run_windows.bat` (it installs Python and PyQt6 first if needed),
or from a terminal:

```
python deskcat.py
```

Quick test of the break reminder (pops up after ~20 seconds):

```
python3 deskcat.py --demo
```

Quick test of the bubble flight (starts ~3 seconds after launch):

```
python3 deskcat.py --bubble
python3 deskcat.py --bubble=huge     (or small, medium)
python3 deskcat.py --bubble=burst    (bubble bursts, cat falls to the bottom)
python3 deskcat.py --bubble=down     (parachute down from the top)
python3 deskcat.py --bubble=jump     (jump down from the top)
```

Quick test of mealtime (a bowl appears ~3 seconds after launch):

```
python3 deskcat.py --food
```

Quick test of the toilet trip (~3 seconds after launch):

```
python3 deskcat.py --poop            # litter box or accident, at random
python3 deskcat.py --poop=box        # always the litter box
python3 deskcat.py --poop=accident   # always an accident
```

Quick test of a nap, a wash, a stretch or the zoomies (~3 seconds after launch):

```
python3 deskcat.py --nap
python3 deskcat.py --groom
python3 deskcat.py --stretch
python3 deskcat.py --zoomies
```

Run the tests (needs `pip install pytest`):

```
python3 -m pytest tests -q
```

## Tweak it

Open `deskcat.py` and change the settings at the top:

- `BREAK_MINUTES` - how often the break reminder appears
- `WALK_SPEED` / `DASH_SPEED` - how fast it strolls and runs
- `HILL_UP_MAX` / `HILL_DOWN_MAX` / `HILL_SLOPE` - how far and how steeply
  it will walk up or down
- `BUBBLE_CHANCE` - how often a walk turns into a bubble flight (0 = never)
- `BUBBLE_MAX_MINUTES` - the longest it will go without a flight (0 = no limit)
- `EARLY_POP_CHANCE` - how often a bubble bursts and drops the cat to the bottom
- `FLOAT_SPEED`, `BUBBLE_SIZES` - the flight itself
- `DESCENT_CHANCE` - how often it parachutes or jumps down (0 = never)
- `DRIFT_SPEED`, `JUMP_MIN` / `JUMP_MAX` - the trips down
- `MEAL_MIN_MINUTES` / `MEAL_MAX_MINUTES` - how long between meals
- `EAT_SECONDS`, `TROT_SPEED` - how long a meal takes, how fast it hurries there
- `POOP_MIN_MINUTES` / `POOP_MAX_MINUTES` - how long after a meal it needs the toilet
- `ACCIDENT_CHANCE` - how often it misses the litter box (0 = never)
- `POOP_STAY_MINUTES` - how long an uncleaned poop stays on screen
- `NAP_MIN_MINUTES` / `NAP_MAX_MINUTES` - awake time between naps
- `NAP_SECONDS`, `NIGHT_NAP_SECONDS` - how long naps last by day and by night
- `NIGHT_START`, `NIGHT_END` - which hours count as night
- `ZOOM_MIN_MINUTES` / `ZOOM_MAX_MINUTES`, `ZOOM_AFTER_BOX` - how often it gets the zoomies
- `GROOM_CHANCE`, `YAWN_CHANCE` - how often it washes or stretches on a whim
- Colors (`BODY`, `BELLY`, `BUBBLE`, ...) - give the cat a new coat

## Ideas for later

- More bubble surprises: double bubble, a gust of wind, a passing bird,
  heart-shaped or rainbow bubbles, a squeak
- Dog mode (or a choice of pet)
- Sleeping, stretching, chasing the cursor
- Click-through transparency (mask the window to the cat's shape)
- Pomodoro timer display
- Packaged app (no Python needed) via PyInstaller

## Sharing it as a single .exe (Windows)

On a Windows PC, double-click `build_windows.bat`. It builds `dist\DeskCat.exe`
with PyInstaller: one file with Python, PyQt6 and the meow sound inside, so
friends just double-click it. A Windows .exe can only be built on Windows.
The file is unsigned, so Windows SmartScreen may ask them to click
"More info" then "Run anyway" the first time.

To publish a new version, push a tag (`git tag v1.1.0 && git push origin v1.1.0`);
GitHub builds the exe and attaches it to a release.

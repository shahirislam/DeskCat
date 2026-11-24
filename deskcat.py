#!/usr/bin/env python3
"""
DeskCat v2 - a tiny animated cat companion that wanders your screen.

- A hand-drawn vector cat that actually walks: legs move, tail swishes,
  it blinks, breathes, and sits down to look around.
- It walks on gentle invisible hills: a little uphill is fine, but for a
  long climb it chews gum, blows a bubble and floats up with it.
- To come a long way down it either parachutes under a small bubble or
  simply jumps. Sometimes a bubble bursts and it drops to the bottom.
- At mealtimes a bowl of food appears somewhere on screen and the cat
  makes its own way there (on foot, by bubble, parachute or jump) to eat.
- A few minutes after eating it needs the toilet: a litter box appears and
  it goes there. Now and then it has an accident on your desktop instead;
  click the poop to clean it up.
- It has a life of its own: it naps curled up (longer at night), washes
  its face, stretches and yawns, and now and then gets the zoomies.
- Click it and it jumps, then dashes to the far side of the screen.
- Every so often it pops up big to remind you to take a break.
- Right-click the cat to quit.

Uses PyQt6 for a truly transparent window (no white box) on macOS and Windows.

Install once:
    python3 -m pip install --user PyQt6      (Mac)
    (Windows: automatic - just double-click run_windows.bat)

Run:
    python3 deskcat.py            (Mac)
    double-click run_windows.bat  (Windows - installs Python + PyQt6 if needed)
    python3 deskcat.py --demo     (break reminder after ~20 seconds, for testing)
    python3 deskcat.py --bubble   (bubble flight after ~3 seconds, for testing;
                                   also --bubble=small|medium|huge|burst,
                                   --bubble=down (parachute), --bubble=jump)
    python3 deskcat.py --food     (a meal after ~3 seconds, for testing)
    python3 deskcat.py --poop     (a toilet trip after ~3 seconds, for testing;
                                   also --poop=box, --poop=accident)
    python3 deskcat.py --nap      (also --groom, --stretch, --zoomies: that
                                   behaviour after ~3 seconds, for testing)
"""

import logging
import math
import os
import random
import subprocess
import sys
import time

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer

# Where things live. Run as a script, everything is next to this file. Built
# into DeskCat.exe (see build_windows.bat), the sound is unpacked to a
# temporary folder and the log goes next to the .exe.
FROZEN = getattr(sys, "frozen", False)
HERE = os.path.dirname(os.path.abspath(__file__))
RESOURCE_DIR = getattr(sys, "_MEIPASS", HERE) if FROZEN else HERE
APP_DIR = os.path.dirname(os.path.abspath(sys.executable)) if FROZEN else HERE


def _log_path():
    """The log next to the app, or in the user's own folder if that is read-only."""
    home = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    for folder in (APP_DIR, os.path.join(home, "DeskCat")):
        try:
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, "deskcat.log")
            with open(path, "a"):
                pass
            return path
        except OSError:
            continue
    return os.devnull


# Log file, so we can always check what the cat did.
LOG_PATH = _log_path()
logging.basicConfig(
    filename=LOG_PATH, level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("deskcat")
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QApplication, QWidget

# ---- Settings (tweak these!) ----
BREAK_MINUTES = 25     # minutes of work between break reminders
BREAK_SECONDS = 12     # how long the big break cat stays on screen
WALK_SPEED = 1.7       # pixels per tick while strolling
DASH_SPEED = 11.0      # pixels per tick while running away
TICK_MS = 33           # animation refresh rate (~30 fps)

# Invisible hills: every walk is mostly sideways.
HILL_UP_MAX = 60       # most pixels the cat will climb in one walk
HILL_DOWN_MAX = 180    # most pixels it will descend in one walk
HILL_SLOPE = 0.2       # steepest slope it will walk (height / sideways distance)
TOP_MARGIN = 40        # the cat never walks higher than this

# Bubble gum flight: how the cat goes a long way up.
BUBBLE_CHANCE = 0.18     # chance a "let's go somewhere" becomes a bubble flight
BUBBLE_MAX_MINUTES = 8   # never go longer than this without a flight (0 = no limit)
EARLY_POP_CHANCE = 0.20  # chance a bubble bursts halfway: the cat falls to the bottom
FLOAT_SPEED = 2.0        # pixels per tick while floating up
POP_DROP = 50            # pixels the cat falls after the pop
BUBBLE_MIN_ROOM = 150    # needs this much space above to bother

# Coming a long way down: a parachute bubble, or a confident jump.
DESCENT_CHANCE = 0.16    # chance a "let's go somewhere" becomes a trip down
DESCENT_MIN_ROOM = 150   # needs this much space below to bother
PARACHUTE_MIN_ROOM = 300 # below this it just jumps
PARACHUTE_R = 22         # radius of the little parachute bubble
DRIFT_SPEED = 1.5        # pixels per tick while parachuting down
JUMP_MIN, JUMP_MAX = 150, 350  # how far down a jump goes
LEAP_RISE = 30           # how high the jump arcs before dropping
LEAP_SPEED_X = 150       # sideways pixels per second while jumping
FALL_G = 1100.0          # gravity for falls and jumps, pixels per second^2
# name: (bubble radius, how far it rises as a fraction of the screen height)
BUBBLE_SIZES = {"small": (26, 0.25), "medium": (34, 0.5), "huge": (44, 1.0)}
# While the big bubble is out the window grows by BIG_DX on each side and
# BIG_DY upward (the cat's feet stay where they are).
BIG_DX, BIG_DY = 20, 85

# Mealtimes: a bowl appears at a random spot and the cat goes to eat.
MEAL_MIN_MINUTES, MEAL_MAX_MINUTES = 2, 4   # wait between meals (random in range)
EAT_SECONDS = 7        # how long it takes to empty the bowl
TROT_SPEED = 3.0       # pixels per tick when hurrying to the bowl
MEAL_TIMEOUT = 420     # seconds before an unreached bowl is taken away
EAT_REACH = 58         # how far in front of the cat the bowl sits while eating
GROUND = 99            # the cat's feet are this far below the top of its window

# Toilet: a few minutes after a meal the cat needs to go.
POOP_MIN_MINUTES, POOP_MAX_MINUTES = 0.5, 2   # wait after a meal (random in range)
ACCIDENT_CHANCE = 0.4   # chance it goes on your desktop instead of the litter box
SQUAT_SECONDS = 3.0      # how long the business takes
COVER_SECONDS = 1.6      # scratching litter over it afterwards
SHAME_SECONDS = 1.4      # looking embarrassed after an accident
POOP_STAY_MINUTES = 10   # an uncleaned poop fades by itself after this long
POOP_BEHIND = 46         # how far behind the cat's middle an accident lands

# A life of its own: naps, grooming, stretching and zoomies.
NAP_MIN_MINUTES, NAP_MAX_MINUTES = 6, 12    # awake time between naps
NAP_SECONDS = (40, 90)           # how long a daytime nap lasts (random in range)
NIGHT_NAP_SECONDS = (180, 360)   # naps are longer at night
NIGHT_START, NIGHT_END = 22, 7   # night runs from 22:00 to 07:00
ZOOM_MIN_MINUTES, ZOOM_MAX_MINUTES = 10, 25  # time between fits of the zoomies
ZOOM_SPEED = 13.0        # pixels per tick while zooming
ZOOM_AFTER_BOX = 0.35    # chance of zoomies straight after the litter box
GROOM_CHANCE = 0.1       # chance a "look around" becomes a wash instead
YAWN_CHANCE = 0.1        # chance of a stretch and yawn after sitting
GROOM_SECONDS = 4.0
STRETCH_SECONDS = 1.8
GRUMPY_SECONDS = 1.8     # glaring at you after being woken
YAWN_SECONDS = 1.1       # the yawn before curling up


# The bowl, litter box and poops are extra windows. On Windows a plain window
# gets its own taskbar button, so there they are "tool" windows, which don't.
# (Not on macOS: a tool window there hides whenever you switch apps.)
PROP_WINDOW = (Qt.WindowType.Tool if sys.platform.startswith("win")
               else Qt.WindowType.Widget)


def is_night():
    hour = time.localtime().tm_hour
    return hour >= NIGHT_START or hour < NIGHT_END

# Seconds each step of the flight lasts ("float" lasts until it arrives).
STAGE_SECS = {
    "look": 1.5, "chew1": 1.6, "blow1": 0.9, "pop1": 0.3, "annoyed": 0.9,
    "chew2": 1.1, "blow2": 2.2, "lift": 0.6, "shrink": 1.0, "poke": 0.5,
    "pop2": 0.25, "panic": 0.5, "land": 0.25, "shake": 0.7, "blush": 1.2,
    "crouch": 0.55, "release": 0.7,
}
NEXT_STAGE = {
    "look": "chew1", "chew1": "blow1", "blow1": "pop1", "pop1": "annoyed",
    "annoyed": "chew2", "chew2": "blow2", "blow2": "lift", "lift": "float",
    "shrink": "poke", "poke": "pop2", "panic": "fall", "fall": "land",
    "crouch": "leap", "leap": "land",
}
GROUND_STAGES = ("look", "chew1", "blow1", "pop1", "annoyed", "chew2",
                 "blow2", "land", "shake", "blush", "crouch", "release")

BODY = QColor("#F7F5F0")       # soft white fur
BODY_DARK = QColor("#C9C9C4")  # faint grey markings
BELLY = QColor("#FFFFFF")
PINK = QColor("#F4A7B9")
OUTLINE = QColor("#8A8A86")    # soft grey outline so the white fur reads
DARK = QColor("#2B2B2B")
EYE = QColor("#5E9C7A")        # gentle green eyes
BUBBLE = QColor(247, 150, 185, 205)   # bubble gum, slightly see-through
BUBBLE_EDGE = QColor("#D9628F")
BOWL = QColor("#6FA8DC")          # the food bowl
BOWL_EDGE = QColor("#4A7FB0")
BOWL_INSIDE = QColor("#3F6C96")
FOOD = QColor("#B0763A")          # kibble
FOOD_DARK = QColor("#8A5626")
POOP = QColor("#8B5A2B")
POOP_DARK = QColor("#5C3A17")
STINK = QColor(126, 150, 84, 190)
TRAY = QColor("#9DB4A8")          # the litter box
TRAY_EDGE = QColor("#6E8A7C")
LITTER = QColor("#E2D4AE")
LITTER_DARK = QColor("#BFAE84")


def hill_target_y(y, dx, y_min, y_max, rng=random):
    """Height to walk to when moving dx pixels sideways from height y.

    Screen y grows downward, so "up" is a smaller y. Uphill is limited more
    than downhill, and the slope cap keeps short walks nearly level.
    """
    reach = HILL_SLOPE * abs(dx)
    up = min(HILL_UP_MAX, reach)
    down = min(HILL_DOWN_MAX, reach)
    return min(y_max, max(y_min, y + rng.uniform(-up, down)))


def flight_top_y(y, size, screen_h, top=0):
    """Height at which a bubble of this size pops, starting from height y.

    top is the highest usable pixel row (below the macOS menu bar); the
    enlarged window must stay under it or the system pushes it back down.
    """
    rise = BUBBLE_SIZES[size][1] * screen_h
    return max(float(top + BIG_DY), y - rise)


def mouth_bubble_pos(r):
    """Centre of a bubble of radius r being blown by the sitting cat."""
    return 19 + 0.5 * r, -21 - 0.8 * r


def hang_bubble_pos(r):
    """Centre of a bubble of radius r the cat is hanging from."""
    return 6.0, -50 - 0.85 * r


def _ease(k):
    k = min(1.0, max(0.0, k))
    return k * k * (3 - 2 * k)


# Meow sound: a short real cat meow (CC0, BigSoundBank) shipped next to
# this script. Played softly, only now and then.
MEOW_PATH = os.path.join(RESOURCE_DIR, "meow.wav")
_last_meow_at = 0.0


def play_meow():
    """Play the meow sound once, quietly. Never raises."""
    global _last_meow_at
    now = time.monotonic()
    if now - _last_meow_at < 4.0:
        return  # don't stack meows on top of each other
    _last_meow_at = now
    try:
        if not os.path.exists(MEOW_PATH):
            log.warning("Meow file missing: %s", MEOW_PATH)
            return
        if sys.platform == "darwin":
            subprocess.Popen(["afplay", "-v", "0.5", MEOW_PATH],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform.startswith("win"):
            import winsound
            winsound.PlaySound(MEOW_PATH,
                               winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        log.exception("Could not play meow")


def _draw_bubble(p, bx, by, r, wobble=0.0):
    """A pink gum bubble centred at (bx, by); wobble makes it jelly-like."""
    if r <= 0.5:
        return
    w = 0.04 * math.sin(wobble)
    p.setPen(QPen(BUBBLE_EDGE, 1.5))
    p.setBrush(BUBBLE)
    p.drawEllipse(QPointF(bx, by), r * (1 + w), r * (1 - w))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, 170))
    p.drawEllipse(QPointF(bx - 0.4 * r, by - 0.45 * r), 0.26 * r, 0.16 * r)
    p.drawEllipse(QPointF(bx - 0.62 * r, by - 0.12 * r), 0.07 * r, 0.07 * r)


def _draw_pop(p, bx, by, r, k):
    """Burst lines and gum bits where a bubble just popped. k runs 0..1."""
    alpha = int(255 * (1 - min(1.0, max(0.0, k))))
    edge = QColor(BUBBLE_EDGE)
    edge.setAlpha(alpha)
    pen = QPen(edge, 2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    r1 = r * (0.7 + 0.5 * k)
    r2 = r1 + max(4.0, r * 0.3)
    for i in range(8):
        a = i * math.pi / 4 + 0.3
        p.drawLine(QPointF(bx + math.cos(a) * r1, by + math.sin(a) * r1),
                   QPointF(bx + math.cos(a) * r2, by + math.sin(a) * r2))
    bit = QColor(BUBBLE)
    bit.setAlpha(alpha)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(bit)
    rb = r * (0.4 + 0.8 * k)
    for i in range(5):
        a = i * 2 * math.pi / 5 + 1.0
        p.drawEllipse(QPointF(bx + math.cos(a) * rb, by + math.sin(a) * rb),
                      1.5 + r * 0.05, 1.5 + r * 0.05)


def _limb(p, x1, y1, x2, y2, w):
    """A soft outlined limb drawn as a thick rounded stroke."""
    path = QPainterPath(QPointF(x1, y1))
    path.lineTo(QPointF(x2, y2))
    pen = QPen(OUTLINE, w + 4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(pen)
    p.drawPath(path)
    pen.setColor(BODY)
    pen.setWidthF(w)
    p.setPen(pen)
    p.drawPath(path)


def _draw_head(p, hx, hy, r, blink=False, scared=False, fx=None):
    """Draw the head centred at (hx, hy) with radius r, facing right.

    fx is an optional dict of extra expressions: chew (phase), annoyed,
    blush, look ((dx, dy) pupil offset), o_mouth, gum_on_nose, strain
    (a running time in seconds: eyes squeezed shut, sweat drop), asleep,
    yawn (0..1 how wide), lick (a running time in seconds).
    """
    fx = fx or {}
    p.save()
    p.translate(hx, hy)
    p.scale(r / 17.0, r / 17.0)

    pen = QPen(OUTLINE, 2)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

    # Ears (behind the head circle).
    p.setBrush(BODY)
    p.setPen(pen)
    p.drawPolygon(QPolygonF([QPointF(-12, -8), QPointF(-6, -26), QPointF(4, -13)]))
    p.drawPolygon(QPolygonF([QPointF(4, -13), QPointF(14, -26), QPointF(18, -8)]))
    p.setBrush(PINK)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawPolygon(QPolygonF([QPointF(-8, -11), QPointF(-5, -20), QPointF(1, -13)]))
    p.drawPolygon(QPolygonF([QPointF(7, -13), QPointF(13, -20), QPointF(15, -11)]))

    # Head.
    p.setBrush(BODY)
    p.setPen(pen)
    p.drawEllipse(QRectF(-17, -17, 34, 34))

    # Head stripes.
    p.setPen(QPen(BODY_DARK, 2))
    p.drawLine(QPointF(-4, -15), QPointF(-6, -9))
    p.drawLine(QPointF(2, -16), QPointF(2, -10))
    p.drawLine(QPointF(8, -15), QPointF(10, -9))

    # Eyes.
    if fx.get("strain"):
        # Squeezed shut with effort: > <, plus a bead of sweat.
        p.setPen(QPen(DARK, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolyline(QPolygonF([QPointF(-8, -7.5), QPointF(-2, -4), QPointF(-8, -0.5)]))
        p.drawPolyline(QPolygonF([QPointF(13, -7.5), QPointF(7, -4), QPointF(13, -0.5)]))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(140, 200, 240, 230))
        sy = -13 + 5 * (fx["strain"] % 1.0)
        drop = QPainterPath(QPointF(-15, sy - 4))
        drop.quadTo(QPointF(-18.5, sy + 2), QPointF(-15, sy + 2.5))
        drop.quadTo(QPointF(-11.5, sy + 2), QPointF(-15, sy - 4))
        p.drawPath(drop)
    elif fx.get("asleep"):
        # Peacefully closed: two little downward curves.
        p.setPen(QPen(DARK, 1.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for ex in (-7, 6):
            lid = QPainterPath(QPointF(ex, -4.5))
            lid.quadTo(QPointF(ex + 3, -1.5), QPointF(ex + 6, -4.5))
            p.drawPath(lid)
    elif blink:
        p.setPen(QPen(DARK, 2))
        p.drawLine(QPointF(-7, -4), QPointF(-1, -4))
        p.drawLine(QPointF(6, -4), QPointF(12, -4))
    else:
        # Green irises with dark pupils, so the eyes look alive.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(EYE)
        es = 9 if scared else 8
        p.drawEllipse(QRectF(-8, -8, es, es))
        p.drawEllipse(QRectF(5, -8, es, es))
        p.setBrush(DARK)
        ps = 5 if scared else 4
        lx, ly = fx.get("look", (0.0, 0.0))
        p.drawEllipse(QRectF(-6 + lx, -6 + ly, ps, ps))
        p.drawEllipse(QRectF(7 + lx, -6 + ly, ps, ps))
        p.setBrush(QColor(255, 255, 255))
        p.drawEllipse(QRectF(-5 + lx, -6 + ly, 2, 2))
        p.drawEllipse(QRectF(8 + lx, -6 + ly, 2, 2))
        if fx.get("annoyed"):
            # Half-closed lids and a flat, unimpressed brow line.
            p.setBrush(BODY)
            p.drawRect(QRectF(-9, -9.5, 10, 4.5))
            p.drawRect(QRectF(4, -9.5, 10, 4.5))
            p.setPen(QPen(DARK, 1.6))
            p.drawLine(QPointF(-9, -6.5), QPointF(0.5, -4.5))
            p.drawLine(QPointF(4.5, -4.5), QPointF(14, -6.5))

    # Cheeks: a blush, or a puff that pulses while chewing.
    chew = fx.get("chew")
    if chew is not None or fx.get("blush"):
        puff = abs(math.sin(chew)) if chew is not None else 0.6
        tint = QColor(PINK)
        tint.setAlpha(150 if fx.get("blush") else 120)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(tint)
        p.drawEllipse(QPointF(7, 7), 4 + 2.5 * puff, 3 + 2 * puff)
        if fx.get("blush"):
            p.drawEllipse(QPointF(-8, 6), 4, 3)

    # Nose + mouth.
    p.setBrush(PINK)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawPolygon(QPolygonF([QPointF(12, 4), QPointF(18, 4), QPointF(15, 8)]))
    p.setPen(QPen(DARK, 1.2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    if fx.get("yawn"):
        # Wide open, tongue showing.
        y = fx["yawn"]
        p.setBrush(QColor("#7A2E3A"))
        p.drawEllipse(QPointF(14.5, 10 + 2 * y), 2 + 2.2 * y, 1.5 + 4 * y)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(PINK)
        p.drawEllipse(QPointF(14.5, 11.5 + 4 * y), 1.2 + 1.2 * y, 0.6 + 1.6 * y)
    elif fx.get("lick"):
        # Little tongue flicking out at the paw.
        p.drawLine(QPointF(15, 8), QPointF(12, 11))
        p.drawLine(QPointF(15, 8), QPointF(18, 11))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#EE7E97"))
        out = 0.5 + 0.5 * math.sin(fx["lick"] * 11)
        p.drawEllipse(QPointF(15.5, 11.5 + 1.5 * out), 2.0, 1.4 + 1.8 * out)
    elif scared or fx.get("o_mouth"):
        p.drawEllipse(QRectF(13, 9, 4, 5))
    elif fx.get("strain"):
        # Teeth-gritted wobbly line.
        m = QPainterPath(QPointF(10.5, 11))
        m.quadTo(QPointF(12, 9.5), QPointF(13.5, 11))
        m.quadTo(QPointF(15, 12.5), QPointF(16.5, 11))
        m.quadTo(QPointF(18, 9.5), QPointF(19.5, 11))
        p.drawPath(m)
    else:
        jaw = 1.5 * abs(math.sin(chew)) if chew is not None else 0.0
        p.drawLine(QPointF(15, 8), QPointF(12, 11 + jaw))
        p.drawLine(QPointF(15, 8), QPointF(18, 11 + jaw))
    if fx.get("gum_on_nose"):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(BUBBLE)
        p.drawEllipse(QPointF(15.5, 6), 4.5, 3.2)
        p.drawEllipse(QPointF(11, 9), 2, 1.6)

    # Whiskers.
    p.setPen(QPen(QColor(120, 120, 120), 1))
    for wy, dx in ((2, 14), (6, 15), (10, 14)):
        p.drawLine(QPointF(14, wy), QPointF(14 + dx, wy - 3))
        p.drawLine(QPointF(-12, wy), QPointF(-12 - dx, wy - 3))

    p.restore()


def _draw_hang(p, pen, tail_phase, blink, scared, fx):
    """The cat dangling from its bubble: front paws up, hind legs loose."""
    bubble = fx.get("bubble")            # (x, y, radius) or None
    kick = fx.get("kick", 0.0)
    if bubble:
        bx, by, r = bubble
        paws = [(bx - 0.72 * r, by + 0.69 * r), (bx + 0.72 * r, by + 0.69 * r)]
        poke = fx.get("poke", 0.0)
        if poke:
            tx, ty = bx + 0.25 * r, by + 0.45 * r
            paws[1] = (paws[1][0] + (tx - paws[1][0]) * poke,
                       paws[1][1] + (ty - paws[1][1]) * poke)
        # While grabbing on, the paws travel from the cat's sides to the bubble.
        reach = fx.get("reach", 1.0)
        rest = ((-13, 12), (15, 12))
        paws = [(rx + (px - rx) * reach, ry + (py - ry) * reach)
                for (px, py), (rx, ry) in zip(paws, rest)]
        # Swing like a pendulum from the bubble.
        p.translate(bx, by)
        p.rotate(fx.get("tilt", 0.0))
        p.translate(-bx, -by)
    else:
        # No bubble any more: paws flail in the air.
        wave = math.sin(fx.get("flail", 0.0)) * 7
        paws = [(-24 + wave, -50 - wave * 0.5), (34 - wave, -50 + wave * 0.5)]

    # Tail hangs down and steers like a little rudder.
    swing = math.sin(tail_phase * 1.6) * 9
    tail_pen = QPen(OUTLINE, 7)
    tail_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(tail_pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath(QPointF(-12, 20))
    path.quadTo(QPointF(-34, 26), QPointF(-30 + swing, 46))
    p.drawPath(path)
    tail_pen.setColor(BODY)
    tail_pen.setWidth(5)
    p.setPen(tail_pen)
    p.drawPath(path)

    # Hind legs dangle; now and then they kick.
    for i, lx in enumerate((-6, 9)):
        side = 1 if i else -1
        dangle = math.sin(tail_phase * 1.3 + i * math.pi) * 2
        fx_x = lx + dangle + side * kick * 7
        fy = 39 - abs(kick) * 5
        _limb(p, lx, 22, fx_x, fy, 7)
        p.setBrush(BODY)
        p.setPen(pen)
        p.drawEllipse(QPointF(fx_x + 1.5, fy + 1), 6, 3.8)

    # Arms reach up to the bubble (drawn first so they sit behind the head).
    _limb(p, -9, -9, paws[0][0], paws[0][1], 6)
    _limb(p, 11, -9, paws[1][0], paws[1][1], 6)

    # Stretched, upright body.
    torso = QPainterPath(QPointF(-12, -16))
    torso.quadTo(QPointF(-17, 0), QPointF(-15, 14))
    torso.quadTo(QPointF(-15, 27), QPointF(-4, 28))
    torso.lineTo(QPointF(9, 28))
    torso.quadTo(QPointF(20, 27), QPointF(19, 14))
    torso.quadTo(QPointF(20, 0), QPointF(12, -16))
    torso.quadTo(QPointF(0, -21), QPointF(-12, -16))
    torso.closeSubpath()
    p.setBrush(BODY)
    p.setPen(pen)
    p.drawPath(torso)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(BELLY)
    p.drawEllipse(QRectF(-7, -4, 20, 28))

    if bubble:
        _draw_bubble(p, bx, by, r, fx.get("wobble", 0.0))
    _draw_head(p, 4, -30, 16, blink=blink, scared=scared, fx=fx)

    # Paws on top of the bubble so the grip reads clearly.
    p.setBrush(BODY)
    p.setPen(pen)
    for px, py in paws:
        p.drawEllipse(QPointF(px, py), 5, 4.2)

    pop = fx.get("pop")
    if pop:
        _draw_pop(p, *pop)


def _draw_curl(p, pen, breathe, fx):
    """Asleep in a ball: a rounded lump, head tucked in, tail wrapped round."""
    rise = 1.0 + 0.045 * math.sin(breathe)     # slow, deep breathing
    h = 36 * rise
    p.setBrush(BODY)
    p.setPen(pen)
    p.drawEllipse(QRectF(-38, 33 - h, 70, h))
    # Haunch.
    p.setPen(QPen(OUTLINE, 1.6))
    p.setBrush(Qt.BrushStyle.NoBrush)
    hip = QPainterPath(QPointF(-30, 30))
    hip.quadTo(QPointF(-33, 10), QPointF(-14, 9 - (h - 36)))
    p.drawPath(hip)
    # Faint back markings.
    p.setPen(QPen(BODY_DARK, 2.5))
    for sx in (-16, -5, 6):
        p.drawLine(QPointF(sx, 35 - h), QPointF(sx - 2, 43 - h))
    # Head resting low at the front, tipped down a little.
    p.save()
    p.translate(21, 17 - (h - 36) * 0.3)
    p.rotate(14)
    _draw_head(p, 0, 0, 15, fx=dict(fx, asleep=True))
    p.restore()
    # Tail wrapped round the front, tip under the chin.
    tail_pen = QPen(OUTLINE, 7)
    tail_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(tail_pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath(QPointF(-34, 22))
    path.quadTo(QPointF(-30, 37), QPointF(-4, 32))
    path.quadTo(QPointF(8, 31), QPointF(14, 31.5))
    p.drawPath(path)
    tail_pen.setColor(BODY)
    tail_pen.setWidth(5)
    p.setPen(tail_pen)
    p.drawPath(path)


def draw_cat(p, cx, cy, scale, facing, pose, walk_phase, tail_phase,
             blink=False, breathe=0.0, moving=False, scared=False,
             shadow=True, fx=None):
    """Draw the whole cat centred at (cx, cy). facing: 1 = right, -1 = left.

    pose: "walk" (on all fours), "sit", "hang" (dangling from a bubble)
    or "curl" (asleep in a ball).
    fx: optional dict of extras used by the bubble flight (see _draw_head
    and _draw_hang), plus bubble/pop for the sitting cat, squash, tilt
    and splay for the cat on all fours.
    """
    fx = fx or {}
    p.save()
    p.translate(cx, cy)
    p.scale(facing * scale, scale)

    pen = QPen(OUTLINE, 2)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    sway = math.sin(tail_phase) * 6

    # Soft shadow on the ground.
    if shadow:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 45))
        p.drawEllipse(QRectF(-38, 34, 76, 10))

    if pose == "hang":
        _draw_hang(p, pen, tail_phase, blink, scared, fx)
        p.restore()
        return
    if pose == "curl":
        _draw_curl(p, pen, breathe, fx)
        p.restore()
        return

    # Landing squash (feet stay planted) and the after-landing shake.
    squash = fx.get("squash", 1.0)
    if squash != 1.0:
        p.translate(0, 33)
        p.scale(1 + (1 - squash) * 0.6, squash)
        p.translate(0, -33)
    if fx.get("tilt"):
        p.rotate(fx["tilt"])

    if pose == "sit":
        # Tail curled around the base.
        tail_pen = QPen(OUTLINE, 7)
        tail_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(tail_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        if fx.get("tail_up"):
            # Squatting: tail held stiffly up and out of the way.
            path = QPainterPath(QPointF(-18, 22))
            path.quadTo(QPointF(-42, 16), QPointF(-37 + sway * 0.25, -14))
        else:
            path = QPainterPath(QPointF(-16, 24))
            path.quadTo(QPointF(0, 38 + sway * 0.3), QPointF(19, 27))
        p.drawPath(path)
        tail_pen.setColor(BODY)
        tail_pen.setWidth(5)
        p.setPen(tail_pen)
        p.drawPath(path)

        # Upright body: a tapered silhouette — narrow chest, wide base,
        # haunches bulging at the sides like a real sitting cat.
        torso = QPainterPath(QPointF(-14, -16))
        torso.quadTo(QPointF(-20, 2), QPointF(-24, 18))    # left side
        torso.quadTo(QPointF(-25, 30), QPointF(-12, 33))   # left haunch
        torso.lineTo(QPointF(16, 33))                      # base
        torso.quadTo(QPointF(26, 30), QPointF(24, 16))     # right haunch
        torso.quadTo(QPointF(20, 0), QPointF(12, -16))     # right side
        torso.quadTo(QPointF(0, -22), QPointF(-14, -16))   # shoulders
        torso.closeSubpath()
        p.setBrush(BODY)
        p.setPen(pen)
        p.drawPath(torso)

        # Chest and belly patch.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(BELLY)
        p.drawEllipse(QRectF(-9, -2, 22, 30))

        # Front legs, straight down with paws at the base.
        p.setBrush(BODY)
        p.setPen(pen)
        p.drawRoundedRect(QRectF(-2, 8, 8, 22), 4, 4)
        p.drawRoundedRect(QRectF(-4, 27, 12, 6), 3, 3)
        hx, hy = fx.get("head", (0.0, 0.0))
        if fx.get("lick") is None:
            p.drawRoundedRect(QRectF(10, 8, 8, 22), 4, 4)
            p.drawRoundedRect(QRectF(8, 27, 12, 6), 3, 3)
            _draw_head(p, 4 + hx, -30 + hy, 16, blink=blink, scared=scared, fx=fx)
        else:
            # Washing: one front paw lifted to the mouth, rubbing up and down.
            _draw_head(p, 4 + hx, -30 + hy, 16, blink=blink, scared=scared, fx=fx)
            rub = math.sin(fx["lick"] * 11)
            px, py = 23 + hx * 0.5, -14 + hy + 2.5 * rub
            _limb(p, 15, 6, px, py, 7)
            p.setBrush(BODY)
            p.setPen(pen)
            p.drawEllipse(QPointF(px, py - 1), 5.5, 4.5)
    else:
        # Tail, swaying behind the body.
        tail_pen = QPen(OUTLINE, 7)
        tail_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(tail_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath(QPointF(-32, 8))
        path.quadTo(QPointF(-54, -2), QPointF(-50 + sway, -30))
        p.drawPath(path)
        tail_pen.setColor(BODY)
        tail_pen.setWidth(5)
        p.setPen(tail_pen)
        p.drawPath(path)

        # Legs: slim, with paws. Diagonal gait — opposite corners step
        # together, the way a real cat walks. Drawn before the body so
        # the tops tuck under it cleanly.
        for i, lx in enumerate((-26, -14, 14, 26)):
            if moving:
                phase = walk_phase + (math.pi if i % 2 else 0)
                swing = math.sin(phase) * 4
                lift = max(0.0, math.cos(phase)) * 3
            elif fx.get("splay"):
                swing, lift = (-6.0, -2.5, 2.5, 6.0)[i], 0.0
            elif fx.get("stretch") and i >= 2:
                # Front legs slide out flat along the ground.
                st = fx["stretch"]
                px = lx + 4 + 20 * st
                _limb(p, lx, 14 + 9 * st, px, 29 - 2 * (1 - st), 5)
                p.setBrush(BODY)
                p.setPen(pen)
                p.drawRoundedRect(QRectF(px - 4, 27, 11, 6), 3, 3)
                continue
            else:
                swing, lift = 0.0, 0.0
            p.setBrush(BODY)
            p.setPen(pen)
            p.drawRoundedRect(QRectF(lx - 3 + swing, 12 - lift, 6, 18), 3, 3)
            p.drawRoundedRect(QRectF(lx - 5 + swing, 27 - lift, 10, 6), 3, 3)

        # Body (breathes gently): one smooth silhouette — arched back,
        # rounded rump, chest at the front, haunch at the back.
        stretch = fx.get("stretch", 0.0)
        if stretch:
            # Chest down, rump up: everything tips forward about the hips.
            p.save()
            p.translate(-20, 12 - 6 * stretch)
            p.rotate(17 * stretch)
            p.translate(20, -12)
        squash = 1.0 + 0.02 * math.sin(breathe)
        body = QPainterPath(QPointF(-30, 22))
        body.quadTo(QPointF(-40, 12), QPointF(-40, -2))            # rump
        body.quadTo(QPointF(-38, -18), QPointF(-8, -22 * squash))  # back
        body.quadTo(QPointF(12, -25 * squash), QPointF(30, -14))   # shoulders
        body.quadTo(QPointF(39, -6), QPointF(36, 6))               # chest
        body.quadTo(QPointF(34, 16), QPointF(28, 22))              # chest to leg
        body.quadTo(QPointF(10, 27), QPointF(-8, 25))              # belly
        body.quadTo(QPointF(-22, 30), QPointF(-30, 22))            # haunch
        body.closeSubpath()
        p.setBrush(BODY)
        p.setPen(pen)
        p.drawPath(body)

        # Soft belly patch.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(BELLY)
        p.drawEllipse(QRectF(-14, 6, 34, 15))

        # Faint back markings.
        p.setPen(QPen(BODY_DARK, 2.5))
        for sx in (-18, -4, 10):
            p.drawLine(QPointF(sx, -19), QPointF(sx - 3, -10))

        hx, hy = fx.get("head", (0.0, 0.0))   # lowered into the bowl to eat
        _draw_head(p, 30 + hx, -18 + hy, 17, blink=blink, scared=scared, fx=fx)
        if stretch:
            p.restore()

    if fx.get("bubble"):
        bx, by, r = fx["bubble"]
        _draw_bubble(p, bx, by, r, fx.get("wobble", 0.0))
    if fx.get("pop"):
        _draw_pop(p, *fx["pop"])

    p.restore()


class CatWidget(QWidget):
    W, H = 150, 120

    def __init__(self):
        super().__init__()
        # NOTE: no Qt.Tool here on purpose — on macOS a Tool window hides
        # itself whenever you click into another app, which made the cat vanish.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(self.W, self.H)

        screen = QApplication.primaryScreen().geometry()
        self.screen_w, self.screen_h = screen.width(), screen.height()
        # Rows at the top the system keeps for itself (the macOS menu bar).
        self.screen_top = max(0, QApplication.primaryScreen()
                              .availableGeometry().y() - screen.y())
        log.info("Cat started on %sx%s screen", self.screen_w, self.screen_h)
        self.x = random.randint(0, max(0, self.screen_w - self.W))
        self.y = random.randint(40, max(40, self.screen_h - self.H))
        self.target_x, self.target_y = self.x, self.y
        self.facing = 1 if random.random() < 0.5 else -1

        # idle | walk | sit | dash | bubble | eat | poop | sleep | act
        self.mode = "idle"
        self.idle_until = time.monotonic() + 1.0
        self.sit_until = 0.0
        self.hop_start = None
        self.scared_until = 0.0

        self.walk_phase = 0.0
        self.tail_phase = 0.0
        self.breathe_phase = 0.0
        self.next_blink = time.monotonic() + random.uniform(2, 5)
        self.next_meow = time.monotonic() + random.uniform(20, 60)
        self.blink_until = 0.0

        # Bubble flight state (only meaningful while mode == "bubble").
        self.stage = None          # which step of the flight we are in
        self.stage_t0 = 0.0
        self.bubble_size = "medium"
        self.bubble_r = 0
        self.flight_kind = "up"    # up (bubble) | down (parachute) | jump
        self.early = False         # the bubble bursts halfway
        self.floor_y = 0.0         # where the cat lands if the trip is cut short
        self.air_secs = 0.0        # how long the current fall or jump lasts
        self.leap_x0 = self.leap_vx = self.leap_v0 = 0.0
        self.land_squash = 0.16
        self.dash_after = False    # clicked in mid-air: dash once landed
        self.flight_start_y = 0.0
        self.pop_y = 0.0
        self.float_t0 = 0.0
        self.fall_from = self.fall_to = 0.0
        self.look_facing = self.facing
        self.big = False           # window currently enlarged for the bubble
        self.last_flight_at = time.monotonic()
        self.sway = 0.0            # sideways drift while floating, in pixels
        self.tilt = 0.0            # lean while floating, in degrees

        # Mealtime state.
        avail = QApplication.primaryScreen().availableGeometry()
        self.avail_bottom = avail.y() + avail.height() - screen.y()
        self.bowl = None           # the BowlWindow while a meal is out
        self.bowl_cx = 0.0         # screen x of the middle of the bowl
        self.bowl_y = 0.0          # the cat's y when standing level with the bowl
        self.errand = None         # where it must go: food | litter | accident
        self.food_left = 0.0
        self.meal_deadline = 0.0
        self.notice_until = 0.0
        self.happy_until = 0.0
        if "--food" in sys.argv[1:]:
            self.next_meal_at = time.monotonic() + 3
        else:
            self.next_meal_at = time.monotonic() + random.uniform(90, 240)

        # Toilet state.
        self.poops_enabled = True  # a meal is followed by a toilet trip
        self.next_poop_at = float("inf")
        self.force_poop = None     # "box" or "accident" (test flag)
        self.litter = None         # the LitterWindow while one is out
        self.litter_cx = 0.0
        self.litter_y = 0.0
        self.litter_deadline = 0.0
        self.poop_stage = None     # squat | cover | shame (mode == "poop")
        self.poop_t0 = 0.0
        self.poops = []            # PoopWindows waiting to be cleaned up
        poop_arg = next((a for a in sys.argv[1:]
                         if a == "--poop" or a.startswith("--poop=")), None)
        if poop_arg:
            self.force_poop = poop_arg.partition("=")[2] or None
            self.next_poop_at = time.monotonic() + 3
            if self.force_poop == "accident":
                self.y = self.screen_h // 2   # clear of the Dock, so it can happen

        # A life of its own.
        self.lively = True         # naps, grooming, yawns and zoomies happen
        self.act = None            # groom | stretch | grumpy (mode == "act")
        self.act_t0 = self.act_secs = 0.0
        self.groom_next = False    # wash at the next free moment
        self.sleep_t0 = self.sleep_until = 0.0
        self.zoom_legs = 0         # runs left in the current fit of zoomies
        self.zoom_dir = 1
        self.next_nap_at = time.monotonic() + random.uniform(
            NAP_MIN_MINUTES, NAP_MAX_MINUTES) * 60
        self.next_zoom_at = time.monotonic() + random.uniform(
            ZOOM_MIN_MINUTES, ZOOM_MAX_MINUTES) * 60
        for flag in ("nap", "groom", "stretch", "zoomies"):
            if "--" + flag in sys.argv[1:]:
                QTimer.singleShot(3000, lambda f=flag: self._force_act(f))

        self.break_window = None
        bubble_arg = next((a for a in sys.argv[1:]
                           if a == "--bubble" or a.startswith("--bubble=")), None)
        if bubble_arg:
            # Test mode: start at the bottom and fly after a few seconds.
            choice = bubble_arg.partition("=")[2]
            if choice in ("down", "jump"):
                self.y = float(self.screen_top + TOP_MARGIN + 60)
            else:
                self.y = max(TOP_MARGIN, self.screen_h - self.H)
            QTimer.singleShot(3000, lambda: self._force_flight(choice))
        self.move(int(self.x), int(self.y))
        self._pick_target()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(TICK_MS)
        self._schedule_break(first=True)

    @property
    def hungry(self):
        return self.errand == "food"

    def _hill_y(self, target_x):
        """A height the cat can reach on foot when walking to target_x."""
        return hill_target_y(self.y, target_x - self.x, TOP_MARGIN,
                             max(TOP_MARGIN, self.screen_h - self.H))

    def _pick_target(self):
        self.target_x = random.randint(0, max(0, self.screen_w - self.W))
        self.target_y = self._hill_y(self.target_x)
        self.mode = "walk"

    # ---- bubble gum flight ----

    def _force_flight(self, choice=""):
        if self.mode == "bubble":
            return
        self.mode = "idle"
        if choice in ("down", "jump"):
            ok = self._start_descent(kind=choice, early=False)
        else:
            burst = choice in ("early", "burst")
            size = choice if choice in BUBBLE_SIZES else ("huge" if burst else None)
            ok = self._start_flight(size=size, early=burst)
        if not ok:
            log.info("Test trip skipped: not enough room")

    def _start_flight(self, size=None, early=None, to_y=None):
        """Begin the chew-blow-float routine. False if it can't happen now.

        to_y: land exactly at this height (used to reach the food bowl).
        """
        ceiling = self.screen_top + BIG_DY
        if self.mode == "bubble":
            return False
        if to_y is None:
            if self.y - ceiling < BUBBLE_MIN_ROOM:
                return False
        else:
            if not (ceiling <= to_y - POP_DROP and to_y < self.y):
                return False
            rise = (self.y - to_y) / self.screen_h
            size = "small" if rise < 0.3 else "medium" if rise < 0.6 else "huge"
        now = time.monotonic()
        self.last_flight_at = now
        self.bubble_size = size or random.choice(list(BUBBLE_SIZES))
        self.bubble_r = BUBBLE_SIZES[self.bubble_size][0]
        self.early = (random.random() < EARLY_POP_CHANCE) if early is None else early
        self.dash_after = False
        self.flight_kind = "up"
        self.flight_start_y = self.floor_y = self.y
        if to_y is None:
            top = flight_top_y(self.y, self.bubble_size, self.screen_h,
                               self.screen_top)
        else:
            top = to_y - POP_DROP   # pops just above, then the usual short drop
        self.pop_y = (self.y + top) / 2 if self.early else top
        self.look_facing = self.facing
        self.hop_start = None
        self.mode = "bubble"
        self._set_stage("look", now)
        log.info("Bubble flight: %s bubble%s", self.bubble_size,
                 " (will pop early)" if self.early else "")
        return True

    def _start_descent(self, kind=None, early=None, to_y=None):
        """Begin a long trip down: parachute bubble or jump. False if it can't.

        to_y: land exactly at this height (used to reach the food bowl).
        """
        bottom = max(TOP_MARGIN, self.screen_h - self.H)
        room = bottom - self.y
        if self.mode == "bubble":
            return False
        if to_y is None:
            if room < DESCENT_MIN_ROOM:
                return False
            if kind is None:
                kind = random.choice(("down", "jump"))
            if kind == "down" and room < PARACHUTE_MIN_ROOM:
                kind = "jump"
        else:
            if not (self.y < to_y <= bottom):
                return False
            kind = "down" if to_y - self.y >= PARACHUTE_MIN_ROOM else "jump"
        now = time.monotonic()
        self.flight_kind = kind
        self.dash_after = False
        self.flight_start_y = self.y
        if kind == "down":
            drop = random.uniform(0.5, 1.0) * room
            self.bubble_size, self.bubble_r = "parachute", PARACHUTE_R
            self.early = (random.random() < EARLY_POP_CHANCE) if early is None else early
        else:
            drop = min(room, random.uniform(JUMP_MIN, JUMP_MAX))
            self.early = False
        if to_y is not None:
            drop = to_y - self.y
        if kind == "jump":
            # Jump toward whichever side has space.
            side_room = (self.screen_w - self.W - self.x) if self.facing > 0 else self.x
            if side_room < 150:
                self.facing = -self.facing
        self.floor_y = self.y + drop
        self.pop_y = self.y + drop / 2 if self.early else self.floor_y
        self.look_facing = self.facing
        self.hop_start = None
        self.mode = "bubble"
        self._set_stage("look", now)
        log.info("Trip down: %s%s", "parachute" if kind == "down" else "jump",
                 " (bubble will burst)" if self.early else "")
        return True

    def _flight_overdue(self, now):
        return (BUBBLE_MAX_MINUTES > 0
                and now - self.last_flight_at >= BUBBLE_MAX_MINUTES * 60)

    def _set_big(self, flag):
        """Grow or shrink the window; the cat's feet stay where they are."""
        if flag == self.big:
            return
        self.big = flag
        if flag:
            self.setFixedSize(self.W + 2 * BIG_DX, self.H + BIG_DY)
        else:
            self.setFixedSize(self.W, self.H)
        self._place()  # same moment as the resize, so the cat never jumps

    def _set_stage(self, stage, now):
        self.stage = stage
        self.stage_t0 = now
        if stage == "blow2":
            self._set_big(True)
        elif stage in ("float", "drift"):
            self.float_t0 = now
        elif stage == "release":
            self._settle_sway()
        elif stage == "fall":
            # Keep the sideways drift, drop the lean, back to a small window.
            self._settle_sway()
            self._set_big(False)
            self.fall_from = self.y
            if self.early and not self.dash_after:
                # The bubble burst by itself: all the way to the bottom.
                self.fall_to = float(max(TOP_MARGIN, self.screen_h - self.H))
            else:
                self.fall_to = min(self.y + POP_DROP, self.floor_y)
            dist = max(0.0, self.fall_to - self.fall_from)
            self.air_secs = max(0.05, math.sqrt(2 * dist / FALL_G))
            self.land_squash = 0.16 if dist < 120 else 0.3
        elif stage == "leap":
            drop = self.floor_y - self.y
            rise = max(0.0, min(LEAP_RISE, self.y - self.screen_top))
            self.leap_v0 = math.sqrt(2 * FALL_G * rise)
            self.air_secs = (self.leap_v0 + math.sqrt(
                self.leap_v0 ** 2 + 2 * FALL_G * drop)) / FALL_G
            side_room = (self.screen_w - self.W - self.x) if self.facing > 0 else self.x
            reach = min(LEAP_SPEED_X * self.air_secs, max(0.0, side_room))
            self.leap_x0, self.fall_from = self.x, self.y
            self.leap_vx = self.facing * reach / self.air_secs
            self.land_squash = 0.26

    def _settle_sway(self):
        """Stop swaying where the cat currently is, without a jump."""
        self.x = min(max(0.0, self.x + self.sway),
                     float(max(0, self.screen_w - self.W)))
        self.sway = self.tilt = 0.0
        self._place()

    def _next_stage(self, stage):
        """What follows this stage: a stage name, "dash", or None when done."""
        kind = self.flight_kind
        if stage == "look" and kind == "jump":
            return "crouch"
        if stage == "chew1" and kind == "down":
            return "blow2"      # the parachute bubble works first time
        if stage == "lift" and kind == "down":
            return "drift"
        if stage == "pop2":
            return "panic" if (self.early and not self.dash_after) else "fall"
        if stage == "land":
            if self.dash_after:
                return "dash"
            if kind == "jump":
                return None     # a confident jump needs no recovery
            return "blush" if self.early else "shake"
        return NEXT_STAGE.get(stage)

    def _end_flight(self, now):
        self.stage = None
        self.sway = self.tilt = 0.0
        self._set_big(False)
        self.mode = "idle"
        self.idle_until = now + (0.3 if self.errand else random.uniform(1, 3))

    # ---- mealtime ----

    def _schedule_meal(self, now):
        self.next_meal_at = now + random.uniform(MEAL_MIN_MINUTES,
                                                 MEAL_MAX_MINUTES) * 60

    def _serve_meal(self, now):
        """A full bowl appears at a random spot the cat can get to."""
        lo = self.screen_top + BIG_DY + POP_DROP
        hi = max(lo, min(self.screen_h - self.H, self.avail_bottom - GROUND - 8))
        self.bowl_y = float(random.uniform(lo, hi))
        # Leave room for the cat to stand on either side of the bowl.
        edge = self.W + 20
        self.bowl_cx = float(random.uniform(edge, max(edge, self.screen_w - edge)))
        self.bowl = BowlWindow(self.bowl_cx, self.bowl_y + GROUND)
        self.bowl.show()
        self.raise_()   # the cat stays in front of its bowl
        self.food_left = 1.0
        self.errand = "food"
        self.meal_deadline = now + MEAL_TIMEOUT
        # Stop and notice it before setting off.
        if self.mode in ("walk", "sit"):
            self.mode = "idle"
        self.facing = 1 if self.bowl_cx > self.x + self.W / 2 else -1
        self.idle_until = self.notice_until = now + 0.9
        log.info("Meal served at x=%d y=%d", self.bowl_cx, self.bowl_y)

    def _go_errand(self, now):
        """Take the next step toward the bowl or the litter box."""
        if self.errand == "accident":
            if self._accident_ok():
                self._start_squat(now)
            else:
                self.errand = None   # nowhere sensible: hold it in
            return
        if self.errand == "food":
            cx, goal_y, reach = self.bowl_cx, self.bowl_y, EAT_REACH
        else:
            cx, goal_y, reach = self.litter_cx, self.litter_y, 0
        side = -1 if self.x + self.W / 2 < cx else 1
        stand_x = cx + side * reach - self.W / 2
        stand_x = min(max(0.0, stand_x), float(max(0, self.screen_w - self.W)))
        dx, dy = stand_x - self.x, goal_y - self.y
        if abs(dx) < 2 and abs(dy) < 2:
            if self.errand == "food":
                self.facing = -side
                self.mode = "eat"
                self.raise_()
            else:
                self._start_squat(now)
            return
        walkable = max(8.0, HILL_SLOPE * abs(dx))
        if -min(HILL_UP_MAX, walkable) <= dy <= min(HILL_DOWN_MAX, walkable):
            self.target_x, self.target_y = stand_x, goal_y
            self.mode = "walk"
            return
        if abs(dx) > 2:
            self.facing = 1 if dx > 0 else -1
        if dy < 0:
            ok = self._start_flight(to_y=goal_y)
        else:
            ok = self._start_descent(to_y=goal_y)
        if not ok:
            self._pick_target()   # wander a bit and try again

    def _end_meal(self, now, eaten):
        self.errand = None
        if self.bowl is not None:
            self.bowl.vanish(now)
        self._schedule_meal(now)
        if eaten:
            # Full and content: sit down for a moment.
            self.mode = "sit"
            self.sit_until = now + random.uniform(3, 5)
            self.happy_until = now + 1.6
            play_meow()
            self.groom_next = self.lively
            if self.poops_enabled:
                self.next_poop_at = now + random.uniform(
                    POOP_MIN_MINUTES, POOP_MAX_MINUTES) * 60
            log.info("Meal finished")
        else:
            log.info("Meal taken away: the cat never got there")

    def _tick_meal(self, now):
        if self.bowl is not None and not self.bowl.tick(now):
            self.bowl.close()
            self.bowl.deleteLater()
            self.bowl = None
        if (self.errand is None and self.bowl is None and now >= self.next_meal_at
                and self.mode in ("idle", "walk", "sit")):
            self._serve_meal(now)
        elif (self.hungry and now >= self.meal_deadline
              and self.mode in ("idle", "walk", "sit")):
            self._end_meal(now, eaten=False)

    # ---- a life of its own ----

    def _force_act(self, name):
        """Test flags: do this now, if the cat is free."""
        now = time.monotonic()
        if self.mode not in ("idle", "walk", "sit") or self.errand:
            log.info("Test %s skipped: the cat is busy", name)
        elif name == "nap":
            self._start_nap(now)
        elif name == "zoomies":
            self._start_zoom(now)
        else:
            self._start_act(name, now)

    def _start_act(self, name, now):
        self.mode = "act"
        self.act, self.act_t0 = name, now
        self.act_secs = {"groom": GROOM_SECONDS, "stretch": STRETCH_SECONDS,
                         "grumpy": GRUMPY_SECONDS}[name]
        if name == "groom":
            self.groom_next = False
            self.act_secs *= random.uniform(0.8, 1.3)

    def _start_nap(self, now):
        lo, hi = NIGHT_NAP_SECONDS if is_night() else NAP_SECONDS
        self.mode = "sleep"
        self.sleep_t0 = now
        self.sleep_until = now + YAWN_SECONDS + random.uniform(lo, hi)
        log.info("Nap: %d seconds", self.sleep_until - now)

    def _end_nap(self, now, grumpy):
        self.next_nap_at = now + random.uniform(NAP_MIN_MINUTES,
                                                NAP_MAX_MINUTES) * 60
        if grumpy:
            self._start_act("grumpy", now)
            play_meow()
        else:
            self._start_act("stretch", now)

    def _start_zoom(self, now):
        self.next_zoom_at = now + random.uniform(ZOOM_MIN_MINUTES,
                                                 ZOOM_MAX_MINUTES) * 60
        self.zoom_legs = random.randint(3, 5)
        right = self.screen_w - self.W - self.x
        self.zoom_dir = 1 if right >= self.x else -1
        self._zoom_leg()
        log.info("Zoomies: %d runs", self.zoom_legs)

    def _zoom_leg(self):
        """Next run of the zoomies: flat out the other way, on one level."""
        room = (self.screen_w - self.W - self.x) if self.zoom_dir > 0 else self.x
        if room < 150:
            self.zoom_dir = -self.zoom_dir
            room = (self.screen_w - self.W - self.x) if self.zoom_dir > 0 else self.x
        run = min(max(0.0, room), random.uniform(450, 900))
        self.target_x = self.x + self.zoom_dir * run
        self.target_y = self.y
        self.zoom_dir = -self.zoom_dir
        self.mode = "dash"

    # ---- toilet ----

    def _accident_ok(self):
        """An accident here would stay visible (not hidden behind the Dock)."""
        return self.y + GROUND <= self.avail_bottom - 8

    def _need_toilet(self, now):
        """Nature calls: usually the litter box, now and then an accident."""
        choice, self.force_poop = self.force_poop, None
        self.next_poop_at = float("inf")
        if choice == "accident":
            accident = True
        elif choice == "box":
            accident = False
        else:
            accident = random.random() < ACCIDENT_CHANCE
        if accident and self._accident_ok():
            self.errand = "accident"
            if self.mode in ("walk", "sit"):
                self.mode = "idle"
            self.idle_until = now + 0.4
            log.info("Toilet: an accident is coming")
        else:
            self._serve_litter(now)

    def _serve_litter(self, now):
        """A litter box appears at a random spot the cat can get to."""
        lo = self.screen_top + BIG_DY + POP_DROP
        hi = max(lo, min(self.screen_h - self.H, self.avail_bottom - GROUND - 8))
        self.litter_y = float(random.uniform(lo, hi))
        edge = self.W / 2 + 20
        self.litter_cx = float(random.uniform(edge, max(edge, self.screen_w - edge)))
        self.litter = LitterWindow(self.litter_cx, self.litter_y + GROUND)
        self.litter.show()
        self.errand = "litter"
        self.litter_deadline = now + MEAL_TIMEOUT
        if self.mode in ("walk", "sit"):
            self.mode = "idle"
        self.facing = 1 if self.litter_cx > self.x + self.W / 2 else -1
        self.idle_until = self.notice_until = now + 0.9
        log.info("Litter box at x=%d y=%d", self.litter_cx, self.litter_y)

    def _start_squat(self, now):
        self.mode = "poop"
        self.poop_stage = "squat"
        self.poop_t0 = now
        if self.errand == "litter":
            self.litter.raise_()   # the tray's front wall hides the cat's feet
        else:
            # Face the side with room to slink away afterwards.
            ahead = (self.screen_w - self.W - self.x) if self.facing > 0 else self.x
            if ahead < 250:
                self.facing = -self.facing

    def _tick_poop_mode(self, now):
        t = now - self.poop_t0
        if self.poop_stage == "squat" and t >= SQUAT_SECONDS:
            self.poop_t0 = now
            if self.errand == "litter":
                # Done: turn round and scratch litter over it.
                self.poop_stage = "cover"
                self.facing = -self.facing
                self.litter.kick(now, -self.facing)
                log.info("Used the litter box")
            else:
                self.poop_stage = "shame"
                cx = self.x + self.W / 2 - self.facing * POOP_BEHIND
                cx = min(max(PoopWindow.W / 2, cx), self.screen_w - PoopWindow.W / 2)
                poop = PoopWindow(cx, self.y + GROUND)
                poop.show()
                self.raise_()
                self.poops.append(poop)
                log.info("Accident at x=%d y=%d", cx, self.y)
            self.errand = None   # the deed is done, whatever happens next
        elif self.poop_stage == "cover":
            self.walk_phase += 0.7
            if t >= COVER_SECONDS:
                self.poop_stage = None
                self.mode = "idle"
                self.idle_until = now + random.uniform(1.2, 2.5)
                self.happy_until = now + 1.2
                if self.lively:
                    if random.random() < ZOOM_AFTER_BOX:
                        self.idle_until = now + 0.5
                        self.next_zoom_at = now   # that famous victory lap
                    else:
                        self.groom_next = True
        elif self.poop_stage == "shame" and t >= SHAME_SECONDS:
            # Slink away from the scene.
            self.poop_stage = None
            self.groom_next = self.lively
            far = self.x + self.facing * random.uniform(220, 420)
            self.target_x = min(max(0.0, far), float(max(0, self.screen_w - self.W)))
            self.target_y = self._hill_y(self.target_x)
            self.mode = "walk"

    def _tick_toilet(self, now):
        if self.litter is not None:
            if self.errand != "litter" and self.mode != "poop":
                self.litter.vanish(now)
            if not self.litter.tick(now):
                self.litter.close()
                self.litter.deleteLater()
                self.litter = None
        for poop in list(self.poops):
            if poop.cleaned_at is not None and not poop.thanked:
                poop.thanked = True
                if self.mode in ("idle", "sit"):
                    self.happy_until = now + 1.2
            if not poop.tick(now):
                self.poops.remove(poop)
                poop.close()
                poop.deleteLater()
        if self.mode not in ("idle", "walk", "sit"):
            return
        if self.errand is None and self.litter is None and now >= self.next_poop_at:
            self._need_toilet(now)
        elif self.errand == "litter" and now >= self.litter_deadline:
            # Never made it to the box: it can't wait any longer.
            self.errand = "accident"
            log.info("Litter box taken away: the cat never got there")

    def _tick_bubble(self, now):
        stage = self.stage
        t = now - self.stage_t0

        if stage == "look":
            # Check nobody is watching: glance the other way and back.
            self.facing = -self.look_facing if 0.45 <= t < 0.95 else self.look_facing
        elif stage == "float":
            ft = now - self.float_t0
            self.y = max(self.pop_y, self.y - FLOAT_SPEED * min(1.0, 0.2 + ft))
            if self.y <= self.pop_y:
                self._set_stage("pop2" if self.early else "shrink", now)
        elif stage == "drift":
            ft = now - self.float_t0
            self.y = min(self.pop_y, self.y + DRIFT_SPEED * min(1.0, 0.2 + ft))
            if self.y >= self.pop_y:
                self._set_stage("pop2" if self.early else "release", now)
        elif stage == "fall":
            k = min(1.0, t / self.air_secs)
            self.y = self.fall_from + (self.fall_to - self.fall_from) * k * k
        elif stage == "leap":
            tt = min(t, self.air_secs)
            self.x = self.leap_x0 + self.leap_vx * tt
            self.y = self.fall_from - self.leap_v0 * tt + FALL_G * tt * tt / 2
            if t >= self.air_secs:
                self.y = self.floor_y

        stage = self.stage  # float/drift may just have moved on
        if stage in ("float", "drift", "shrink", "poke", "pop2", "panic"):
            ft = now - self.float_t0
            gain = min(1.0, ft / 1.5)
            self.sway = math.sin(ft * 1.6) * 12 * gain
            self.tilt = math.cos(ft * 1.6) * 4 * gain

        if stage in STAGE_SECS:
            over = now - self.stage_t0 >= STAGE_SECS[stage]
        else:
            over = stage in ("fall", "leap") and now - self.stage_t0 >= self.air_secs
        if over:
            nxt = self._next_stage(stage)
            if nxt == "dash":
                self._end_flight(now)
                self._startle()
            elif nxt is None:
                self._end_flight(now)   # all done, back to wandering
            else:
                self._set_stage(nxt, now)

    def _click_during_flight(self):
        now = time.monotonic()
        if self.stage in GROUND_STAGES:
            self.facing = self.look_facing
            self._end_flight(now)
            self._startle()
            return
        # In the air: the click pops the bubble; the dash waits for landing.
        self.dash_after = True
        if self.stage in ("lift", "float", "drift", "shrink", "poke"):
            if self.stage == "lift":
                self.float_t0 = now
            self._set_stage("pop2", now)

    def _flight_look(self, now):
        """How to draw the cat right now: (pose, scared, shadow, blink, fx)."""
        stage = self.stage
        t = now - self.stage_t0
        k = min(1.0, t / STAGE_SECS[stage]) if stage in STAGE_SECS else 0.0
        R = self.bubble_r
        blink = self._blinking()
        fx = {}
        pose, scared, shadow = "sit", False, True

        if stage == "look":
            pose = "walk"
        elif stage == "chew1":
            fx["chew"] = t * 9
        elif stage == "blow1":
            r = 9 * _ease(k)
            fx.update(o_mouth=True, bubble=(*mouth_bubble_pos(r), r), wobble=t * 20)
        elif stage == "pop1":
            fx.update(pop=(*mouth_bubble_pos(9), 9, k), gum_on_nose=True)
            blink = True
        elif stage == "annoyed":
            fx.update(annoyed=True, gum_on_nose=k < 0.6)
        elif stage == "chew2":
            fx.update(annoyed=True, chew=t * 17)
        elif stage == "blow2":
            r = R * _ease(k) * (1 + 0.03 * math.sin(t * 12))
            fx.update(o_mouth=True, bubble=(*mouth_bubble_pos(r), r), wobble=t * 14)
        elif stage == "lift":
            # The bubble drifts up over the head and the cat grabs on.
            x0, y0 = mouth_bubble_pos(R)
            x1, y1 = hang_bubble_pos(R)
            e = _ease(k)
            pose = "hang"
            fx.update(bubble=(x0 + (x1 - x0) * e, y0 + (y1 - y0) * e, R),
                      wobble=t * 10, look=(0, -1.5), reach=_ease(k * 1.4))
        elif stage == "crouch":
            # Wind up for the jump: sink down, wiggle, eyes on the landing.
            pose = "walk"
            fx.update(squash=1 - 0.18 * _ease(k * 2), tilt=math.sin(t * 30) * 1.5,
                      look=(1.0, 1.5))
        elif stage == "leap":
            pose, shadow = "walk", False
            vy = -self.leap_v0 + FALL_G * min(t, self.air_secs)
            lean = math.degrees(math.atan2(vy, abs(self.leap_vx) + 200))
            fx.update(splay=True, tilt=max(-18.0, min(32.0, lean * 0.6)),
                      look=(1.0, 1.5))
        elif stage == "release":
            # Touched down: let go, and the little bubble drifts off and pops.
            pose = "walk"
            bx, by = hang_bubble_pos(R)
            by -= 30 * _ease(k)
            if k < 0.6:
                fx.update(bubble=(bx, by, R), wobble=t * 10)
            else:
                fx["pop"] = (bx, by, R, (k - 0.6) / 0.4)
            fx["look"] = (-1.0, -1.5)
        elif stage in ("float", "drift", "shrink", "poke"):
            pose, shadow = "hang", False
            ft = now - self.float_t0
            r = R
            if stage == "shrink":
                r = R * (1 - 0.35 * _ease(k))
                fx["look"] = (0, -1.5)        # notices the bubble shrinking
            elif stage == "poke":
                r = R * 0.65
                fx.update(poke=math.sin(math.pi * k), look=(0, -1.5))
            else:
                if ft % 4.5 > 3.6:
                    fx["kick"] = math.sin((ft % 4.5 - 3.6) / 0.9 * 2 * math.pi)
                if 2.0 < ft % 7.0 < 3.0:
                    fx["look"] = (0, 2.0)     # a nervous look down
                    scared = True
            fx.update(bubble=(*hang_bubble_pos(r), r), wobble=ft * 5, tilt=self.tilt)
        elif stage in ("pop2", "panic"):
            pose, shadow, scared = "hang", False, True
            fx.update(flail=(now - self.float_t0) * 28,
                      kick=math.sin((now - self.float_t0) * 22))
            if stage == "pop2":
                r = R if (self.early or self.dash_after) else R * 0.65
                fx["pop"] = (*hang_bubble_pos(r), r, k)
        elif stage == "fall":
            pose, shadow, scared = "walk", False, True
            fx["splay"] = True
        elif stage == "land":
            pose = "walk"
            fx["squash"] = 1 - self.land_squash * math.sin(math.pi * k)
        elif stage == "shake":
            pose, blink = "walk", True
            fx["tilt"] = math.sin(t * 38) * 5 * (1 - k)
        elif stage == "blush":
            pose = "walk"
            fx.update(blush=True, look=(-1.5, 1.5))
            blink = blink or k < 0.25
        return pose, scared, shadow, blink, fx

    def _blinking(self):
        return time.monotonic() < self.blink_until

    def _tick(self):
        now = time.monotonic()
        self.tail_phase += 0.08
        self.breathe_phase += 0.05

        if now >= self.next_blink:
            self.blink_until = now + 0.15
            self.next_blink = now + random.uniform(3, 8)

        # A soft meow now and then, only while resting.
        if now >= self.next_meow and self.mode in ("idle", "sit"):
            play_meow()
            self.next_meow = now + random.uniform(45, 120)

        self._tick_meal(now)
        self._tick_toilet(now)

        # Too long since the last bubble ride: go now, even mid-stroll.
        if (self.mode in ("idle", "walk", "sit") and not self.errand
                and self._flight_overdue(now)):
            if not self._start_flight() and self.mode != "walk":
                # No room above (already up high): head downhill first.
                self._pick_target()
                self.target_y = min(self.y + HILL_SLOPE * abs(self.target_x - self.x),
                                    self.y + HILL_DOWN_MAX,
                                    max(TOP_MARGIN, self.screen_h - self.H))

        if self.mode in ("walk", "dash"):
            trot = bool(self.errand) and self.mode == "walk"
            speed = DASH_SPEED if self.mode == "dash" else (
                TROT_SPEED if trot else WALK_SPEED)
            if self.mode == "dash" and self.zoom_legs:
                speed = ZOOM_SPEED
            self.walk_phase += 0.9 if self.mode == "dash" else (
                0.55 if trot else 0.35)
            dx, dy = self.target_x - self.x, self.target_y - self.y
            dist = math.hypot(dx, dy)
            if abs(dx) > 2:
                self.facing = 1 if dx > 0 else -1
            if dist <= speed:
                self.x, self.y = self.target_x, self.target_y
                if self.mode == "dash" and self.zoom_legs > 1:
                    self.zoom_legs -= 1
                    self._zoom_leg()
                else:
                    self.zoom_legs = 0
                    self.mode = "idle"
                    self.idle_until = now + (0.25 if self.errand
                                             else random.uniform(1, 4))
            else:
                self.x += dx / dist * speed
                self.y += dy / dist * speed
        elif self.mode == "bubble":
            self._tick_bubble(now)
        elif self.mode == "eat":
            self.food_left = max(0.0, self.food_left - TICK_MS / 1000 / EAT_SECONDS)
            if self.bowl is not None:
                self.bowl.level = self.food_left
            if self.food_left <= 0:
                self._end_meal(now, eaten=True)
        elif self.mode == "poop":
            self._tick_poop_mode(now)
        elif self.mode == "sleep":
            # Sleeps its fill, unless a bubble ride is overdue.
            if now >= self.sleep_until or self._flight_overdue(now):
                self._end_nap(now, grumpy=False)
        elif self.mode == "act":
            if now - self.act_t0 >= self.act_secs:
                self.act = None
                self.mode = "idle"
                self.idle_until = now + random.uniform(0.6, 1.5)
        elif (self.mode == "idle" and now >= self.idle_until and not self.errand
              and self.lively and (self.groom_next or now >= self.next_nap_at
                                   or now >= self.next_zoom_at)):
            if self.groom_next:
                self._start_act("groom", now)
            elif now >= self.next_zoom_at:
                self._start_zoom(now)
            else:
                self._start_nap(now)
        elif self.mode == "idle" and now >= self.idle_until and self.errand:
            self._go_errand(now)
        elif self.mode == "idle" and now >= self.idle_until:
            roll = random.random()
            if roll < 0.55:
                # Usually a stroll; now and then, a bubble ride up high.
                # or a trip down by parachute bubble or a jump.
                pick = random.random()
                if pick < BUBBLE_CHANCE and self._start_flight():
                    pass
                elif (BUBBLE_CHANCE <= pick < BUBBLE_CHANCE + DESCENT_CHANCE
                      and self._start_descent()):
                    pass
                else:
                    self._pick_target()
            elif roll < 0.8:
                self.mode = "sit"
                self.sit_until = now + random.uniform(3, 7)
            elif self.lively and random.random() < GROOM_CHANCE:
                self._start_act("groom", now)
            else:
                # Look around, then decide again shortly.
                self.facing *= -1
                self.idle_until = now + random.uniform(1, 2)
        elif self.mode == "sit" and now >= self.sit_until:
            self.mode = "idle"
            self.idle_until = now + 0.5
            if (self.lively and not self.errand and not self.groom_next
                    and random.random() < YAWN_CHANCE):
                self._start_act("stretch", now)

        hop = 0.0
        if self.hop_start is not None:
            t = now - self.hop_start
            if t < 0.35:
                hop = -math.sin(math.pi * t / 0.35) * 25
            else:
                self.hop_start = None

        self._place(hop)
        self.update()

    def _place(self, hop=0.0):
        """Put the window where the cat is.

        While the window is enlarged it extends up and to both sides, so it
        is shifted to keep the cat itself in the same place on screen.
        """
        ox, oy = (-BIG_DX, -BIG_DY) if self.big else (0, 0)
        self.move(int(self.x + self.sway + ox), int(self.y + hop + oy))

    def showEvent(self, event):
        log.info("Cat window shown")
        super().showEvent(event)

    def hideEvent(self, event):
        log.info("Cat window hidden")
        super().hideEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        now = time.monotonic()
        moving = self.mode in ("walk", "dash")
        pose = "sit" if self.mode == "sit" else "walk"
        scared = now < self.scared_until
        blink, shadow, fx = self._blinking(), True, None
        if self.mode == "bubble" and self.stage:
            pose, scared, shadow, blink, fx = self._flight_look(now)
        elif self.mode == "eat":
            # Head down in the bowl, bobbing as it munches.
            fx = {"head": (6.0, 21 + 2 * math.sin(now * 9)), "chew": now * 12}
        elif self.mode == "sleep":
            t = now - self.sleep_t0
            if t < YAWN_SECONDS:
                # One big yawn sitting up, then down it goes.
                pose, blink = "sit", True
                fx = {"yawn": math.sin(math.pi * t / YAWN_SECONDS) ** 0.6}
            else:
                pose = "curl"
        elif self.mode == "act":
            t = now - self.act_t0
            k = min(1.0, t / self.act_secs)
            if self.act == "groom":
                pose, blink = "sit", True
                fx = {"lick": t, "head": (1.0, 3.0 + 1.2 * math.sin(t * 11))}
            elif self.act == "stretch":
                # Down into the stretch, hold with a yawn, back up.
                s = _ease(min(1.0, k / 0.25)) if k < 0.75 else _ease((1 - k) / 0.25)
                blink = True
                fx = {"stretch": s}
                if 0.2 < k < 0.8:
                    fx["yawn"] = math.sin(math.pi * (k - 0.2) / 0.6) ** 0.6
            else:
                # Woken up: a long, flat stare.
                pose = "sit"
                fx = {"annoyed": True, "look": (1.0, 0.5)}
        elif self.mode == "poop":
            t = now - self.poop_t0
            if self.poop_stage == "squat":
                # Hunched, tail up, pushing in little waves.
                pose, blink = "sit", False
                fx = {"strain": t, "tail_up": True, "blush": True,
                      "squash": 1 - 0.05 * abs(math.sin(t * 4.2))}
            elif self.poop_stage == "cover":
                moving = True
                fx = {"head": (4.0, 12.0)}
            else:
                # Caught in the act: can't quite look at you.
                fx = {"blush": True, "look": (-1.5, 1.5)}
                blink = blink or t < 0.3
        elif now < self.notice_until and self.errand in ("food", "litter"):
            # Spotted the bowl or the box: eyes on it.
            goal_y = self.bowl_y if self.errand == "food" else self.litter_y
            fx = {"look": (1.5, -1.5 if goal_y < self.y else 1.5)}
        elif now < self.happy_until:
            blink = True
            fx = {"blush": True}
        # The cat stands 54 px above the bottom edge, whatever the window size.
        draw_cat(p, self.width() // 2, self.height() - 54, 1.0, self.facing,
                 pose, self.walk_phase, self.tail_phase,
                 blink=blink, breathe=self.breathe_phase,
                 moving=moving, scared=scared, shadow=shadow, fx=fx)
        if pose == "curl":
            self._draw_zs(p, now - self.sleep_t0 - YAWN_SECONDS)

    def _draw_zs(self, p, t):
        """Little z's drifting up from the sleeping cat's head."""
        x0 = self.width() / 2 + self.facing * 30
        y0 = self.height() - 54 + 2
        for i in range(3):
            ph = (t * 0.33 + i / 3.0) % 1.0
            if t < i / 3.0 / 0.33:
                continue    # the first ones appear one by one
            font = QFont("Helvetica", int(8 + 7 * ph))
            font.setBold(True)
            p.setFont(font)
            p.setPen(QColor(110, 130, 190, int(230 * math.sin(math.pi * ph) ** 0.7)))
            p.drawText(QPointF(x0 + self.facing * (4 + 14 * ph) + 3 * math.sin(ph * 7 + i),
                               y0 - 46 * ph), "z")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            QApplication.quit()
        elif event.button() == Qt.MouseButton.LeftButton:
            if self.mode == "bubble":
                self._click_during_flight()
            elif self.mode == "sleep":
                self._end_nap(time.monotonic(), grumpy=True)   # woken: not amused
            else:
                self._startle()

    def _startle(self):
        now = time.monotonic()
        self.hop_start = now
        self.scared_until = now + 1.2
        play_meow()  # a surprised little mew
        margin = 100
        if self.x > self.screen_w // 2:
            far_x = random.randint(0, margin)
        else:
            far_x = random.randint(max(0, self.screen_w - margin - self.W),
                                   max(0, self.screen_w - self.W))
        self.target_x = max(0, far_x)
        self.target_y = self._hill_y(self.target_x)
        self.zoom_legs = 0
        self.act = None
        self.mode = "dash"

    def _schedule_break(self, first=False):
        if "--demo" in sys.argv and first:
            delay_ms = 20 * 1000
        else:
            delay_ms = BREAK_MINUTES * 60 * 1000
        QTimer.singleShot(delay_ms, self._show_break)

    def _show_break(self):
        if self.break_window is not None:
            try:
                if self.break_window.isVisible():
                    self._schedule_break()
                    return
            except RuntimeError:
                self.break_window = None
        self.break_window = BreakWindow()
        self.break_window.destroyed.connect(self._break_gone)
        self.break_window.show()
        self._schedule_break()

    def _break_gone(self):
        self.break_window = None


class BowlWindow(QWidget):
    """A small food bowl that sits on the cat's ground line.

    cx is the screen x of the middle of the bowl, ground_y the screen y of
    the ground it stands on. Clicks pass straight through it.
    """
    W, H = 84, 60
    BASE = 50   # row inside the window that rests on the ground

    def __init__(self, cx, ground_y):
        super().__init__()
        self.setWindowFlags(
            PROP_WINDOW
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(self.W, self.H)
        self.move(int(cx - self.W / 2), int(ground_y - self.BASE))
        self.level = 1.0            # how full: 1 = heaped, 0 = empty
        self.born = time.monotonic()
        self.vanish_at = None

    def vanish(self, now):
        """Start fading out."""
        if self.vanish_at is None:
            self.vanish_at = now

    def tick(self, now):
        """Animate; returns False once it has faded away completely."""
        if self.vanish_at is not None:
            k = (now - self.vanish_at) / 0.8
            if k >= 1:
                return False
            self.setWindowOpacity(1 - k)
        self.update()
        return True

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Pop in with a little bounce.
        k = min(1.0, (time.monotonic() - self.born) / 0.4)
        grow = 1 + 0.25 * math.sin(math.pi * k) if k < 1 else 1.0
        p.translate(self.W / 2, self.BASE)
        p.scale(_ease(k) * grow, _ease(k) * grow)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 45))
        p.drawEllipse(QRectF(-34, -4, 68, 9))

        # Inside of the bowl, then the food heaped in it.
        p.setPen(QPen(BOWL_EDGE, 2))
        p.setBrush(BOWL_INSIDE)
        p.drawEllipse(QPointF(0, -20), 28, 5.5)
        if self.level > 0.02:
            heap = 2 + 9 * self.level
            p.setPen(QPen(FOOD_DARK, 1.5))
            p.setBrush(FOOD)
            p.drawEllipse(QPointF(0, -20 - heap * 0.45), 23, heap)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(FOOD_DARK)
            for i, fx in enumerate((-15, -7, 2, 10, 17, -2, 8)):
                fy = -20 - heap * (0.35 + 0.5 * ((i * 37) % 10) / 10)
                p.drawEllipse(QPointF(fx, fy), 1.8, 1.4)

        # Front of the bowl.
        body = QPainterPath(QPointF(-28, -20))
        body.quadTo(QPointF(-26, 0), QPointF(-17, 0))
        body.lineTo(QPointF(17, 0))
        body.quadTo(QPointF(26, 0), QPointF(28, -20))
        body.quadTo(QPointF(0, -13), QPointF(-28, -20))
        body.closeSubpath()
        pen = QPen(BOWL_EDGE, 2)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(BOWL)
        p.drawPath(body)

        # A little paw print on the front.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 210))
        p.drawEllipse(QPointF(0, -5.5), 4, 3.2)
        for tx in (-4.5, 0, 4.5):
            p.drawEllipse(QPointF(tx, -11 + abs(tx) * 0.25), 1.7, 1.9)


class LitterWindow(QWidget):
    """A litter tray seen from the side, standing on the cat's ground line.

    It sits in front of the cat, so its front wall hides the cat's feet and
    whatever the cat leaves in it. Clicks pass straight through it.
    """
    W, H = 190, 90
    BASE = 78   # row inside the window that rests on the ground

    def __init__(self, cx, ground_y):
        super().__init__()
        self.setWindowFlags(
            PROP_WINDOW
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(self.W, self.H)
        self.move(int(cx - self.W / 2), int(ground_y - self.BASE))
        self.born = time.monotonic()
        self.vanish_at = None
        self.kick_at = None
        self.kick_dir = 1

    def kick(self, now, direction):
        """Litter starts flying out toward direction (1 = right)."""
        self.kick_at, self.kick_dir = now, direction

    def vanish(self, now):
        if self.vanish_at is None:
            self.vanish_at = now

    def tick(self, now):
        """Animate; returns False once it has faded away completely."""
        if self.vanish_at is not None:
            k = (now - self.vanish_at) / 0.8
            if k >= 1:
                return False
            self.setWindowOpacity(1 - k)
        self.update()
        return True

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        now = time.monotonic()
        k = min(1.0, (now - self.born) / 0.4)
        grow = 1 + 0.25 * math.sin(math.pi * k) if k < 1 else 1.0
        p.translate(self.W / 2, self.BASE)
        p.scale(_ease(k) * grow, _ease(k) * grow)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 45))
        p.drawEllipse(QRectF(-62, -3, 124, 9))

        # Front wall of the tray, with a lip along the top.
        wall = QPainterPath(QPointF(-56, -17))
        wall.lineTo(QPointF(-51, -1))
        wall.quadTo(QPointF(-50, 2), QPointF(-46, 2))
        wall.lineTo(QPointF(46, 2))
        wall.quadTo(QPointF(50, 2), QPointF(51, -1))
        wall.lineTo(QPointF(56, -17))
        wall.closeSubpath()
        pen = QPen(TRAY_EDGE, 2)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(TRAY)
        p.drawPath(wall)
        p.drawRoundedRect(QRectF(-60, -21, 120, 6), 3, 3)
        # A few grains spilled over the lip.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(LITTER)
        for gx, gy in ((-40, -22), (-12, -22.5), (22, -22), (45, -22.5), (64, -1), (-66, -1)):
            p.drawEllipse(QPointF(gx, gy), 2.2, 1.6)
        # Paw print on the front.
        p.setBrush(QColor(255, 255, 255, 200))
        p.drawEllipse(QPointF(0, -5), 4, 3.2)
        for tx in (-4.5, 0, 4.5):
            p.drawEllipse(QPointF(tx, -10.5 + abs(tx) * 0.25), 1.7, 1.9)

        # Litter flung out while the cat scratches.
        if self.kick_at is not None:
            for i in range(18):
                t = now - self.kick_at - i * 0.075
                if not 0 <= t <= 0.55:
                    continue
                speed = 55 + (i * 29) % 40
                up = 95 + (i * 53) % 60
                gx = self.kick_dir * (44 + speed * t)
                gy = -20 - up * t + 260 * t * t
                p.setBrush(LITTER if i % 3 else LITTER_DARK)
                p.drawEllipse(QPointF(gx, gy), 2.4, 1.9)


class PoopWindow(QWidget):
    """An accident left on the desktop. Click it to clean it up.

    cx is the screen x of its middle, ground_y the screen y it rests on.
    Left alone it fades away by itself after POOP_STAY_MINUTES.
    """
    W, H = 56, 76
    BASE = 68

    def __init__(self, cx, ground_y):
        super().__init__()
        # Unlike the bowl this one takes clicks. No Qt.Tool: see CatWidget.
        self.setWindowFlags(
            PROP_WINDOW
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self.W, self.H)
        self.move(int(cx - self.W / 2), int(ground_y - self.BASE))
        self.born = time.monotonic()
        self.expire_at = self.born + POOP_STAY_MINUTES * 60
        self.cleaned_at = None      # clicked: sparkle, then gone
        self.thanked = False        # the cat has noticed the clean-up

    def clean(self, now):
        if self.cleaned_at is None:
            self.cleaned_at = now
            log.info("Poop cleaned up")

    def tick(self, now):
        """Animate; returns False once it is gone."""
        if self.cleaned_at is not None:
            if now - self.cleaned_at >= 0.6:
                return False
        elif now >= self.expire_at:
            k = (now - self.expire_at) / 1.5
            if k >= 1:
                return False
            self.setWindowOpacity(1 - k)
        self.update()
        return True

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clean(time.monotonic())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        now = time.monotonic()
        p.translate(self.W / 2, self.BASE)

        if self.cleaned_at is not None:
            # Wiped away: the poop shrinks and sparkles burst outward.
            c = min(1.0, (now - self.cleaned_at) / 0.6)
            p.setPen(Qt.PenStyle.NoPen)
            for i in range(6):
                a = i * math.pi / 3 + 0.4
                d = 8 + 20 * _ease(c)
                sx, sy = math.cos(a) * d, -12 + math.sin(a) * d
                size = 5.5 * math.sin(math.pi * c) + 0.5
                star = QPainterPath(QPointF(sx, sy - size))
                for j in range(1, 8):
                    r = size if j % 2 == 0 else size * 0.35
                    b = j * math.pi / 4
                    star.lineTo(QPointF(sx + math.sin(b) * r, sy - math.cos(b) * r))
                star.closeSubpath()
                p.setBrush(QColor(255, 236, 140, int(255 * (1 - c * 0.6))))
                p.drawPath(star)
            if c >= 0.5:
                return
            p.scale(1 - c * 2, 1 - c * 2)
        else:
            k = min(1.0, (now - self.born) / 0.3)
            grow = 1 + 0.3 * math.sin(math.pi * k) if k < 1 else 1.0
            p.scale(_ease(k) * grow, (0.4 + 0.6 * _ease(k)) * grow)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawEllipse(QRectF(-17, -3, 34, 7))

        # Three soft coils and a little curl on top.
        pen = QPen(POOP_DARK, 1.8)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(POOP)
        p.drawRoundedRect(QRectF(-15, -10, 30, 11), 5.5, 5.5)
        p.drawRoundedRect(QRectF(-11, -18, 22, 10), 5, 5)
        tip = QPainterPath(QPointF(-7, -17))
        tip.quadTo(QPointF(-7, -25), QPointF(1, -25))
        tip.quadTo(QPointF(5, -26), QPointF(4, -30))
        tip.quadTo(QPointF(9, -24), QPointF(7, -17))
        tip.closeSubpath()
        p.drawPath(tip)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 70))
        p.drawEllipse(QPointF(-7, -6), 3.5, 1.8)
        p.drawEllipse(QPointF(-5, -14.5), 2.6, 1.4)

        if self.cleaned_at is None:
            # Wavy stink lines drifting up.
            stink = QPen(STINK, 1.8)
            stink.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setBrush(Qt.BrushStyle.NoBrush)
            for i, sx in enumerate((-13, 0, 13)):
                ph = (now * 0.55 + i * 0.37) % 1.0
                stink.setColor(QColor(STINK.red(), STINK.green(), STINK.blue(),
                                      int(190 * math.sin(math.pi * ph))))
                p.setPen(stink)
                y0 = -32 - 14 * ph
                wave = QPainterPath(QPointF(sx, y0))
                wave.quadTo(QPointF(sx + 4, y0 - 4), QPointF(sx, y0 - 8))
                wave.quadTo(QPointF(sx - 4, y0 - 12), QPointF(sx, y0 - 16))
                p.drawPath(wave)


class BreakWindow(QWidget):
    W, H = 480, 440

    def __init__(self):
        super().__init__()
        # NOTE: no Qt.Tool here on purpose — see CatWidget above.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFixedSize(self.W, self.H)

        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - self.W) // 2, (screen.height() - self.H) // 2)

        self.tail_phase = 0.0
        self.breathe_phase = 0.0
        self.next_blink = time.monotonic() + random.uniform(1, 3)
        self.blink_until = 0.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(TICK_MS)
        QTimer.singleShot(BREAK_SECONDS * 1000, self.close)

    def _tick(self):
        now = time.monotonic()
        self.tail_phase += 0.1
        self.breathe_phase += 0.07
        if now >= self.next_blink:
            self.blink_until = now + 0.15
            self.next_blink = now + random.uniform(2, 6)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        draw_cat(p, self.W // 2, 185, 2.1, 1, "sit", 0.0, self.tail_phase,
                 blink=time.monotonic() < self.blink_until,
                 breathe=self.breathe_phase, moving=False)

        # Text card.
        card = QRectF(40, 315, self.W - 80, 95)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 215))
        p.drawRoundedRect(card, 18, 18)
        p.setPen(QColor("#5A3A1A"))
        p.setFont(QFont("Helvetica", 24, QFont.Weight.Bold))
        p.drawText(QRectF(40, 325, self.W - 80, 36),
                   Qt.AlignmentFlag.AlignCenter, "Time for a break!")
        p.setFont(QFont("Helvetica", 14))
        p.setPen(QColor("#7A5A3A"))
        p.drawText(QRectF(40, 362, self.W - 80, 26),
                   Qt.AlignmentFlag.AlignCenter,
                   "Stretch, grab some water, rest your eyes.")
        p.setFont(QFont("Helvetica", 11))
        p.setPen(QColor(120, 120, 120))
        p.drawText(QRectF(40, self.H - 24, self.W - 80, 18),
                   Qt.AlignmentFlag.AlignCenter, "click anywhere to dismiss")

    def mousePressEvent(self, event):
        self.close()


def main():
    log.info("DeskCat starting (argv=%s)", sys.argv)
    app = QApplication(sys.argv)
    cat = CatWidget()
    cat.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

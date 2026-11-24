"""Tests for the hill-walking rule and the bubble flight.

Run from the project folder:  python3 -m pytest tests -q
"""
import os
import random
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication

import deskcat

deskcat.log.disabled = True  # keep test runs out of the real deskcat.log

TICK = deskcat.TICK_MS / 1000.0


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def clock(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(deskcat.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(deskcat, "play_meow", lambda: None)
    return now


@pytest.fixture
def cat(app, clock):
    random.seed(7)
    w = deskcat.CatWidget()
    w.x = 400.0
    w.y = float(w.screen_h - w.H)
    w.mode = "idle"
    w.idle_until = clock[0] + 9999
    w.next_meal_at = float("inf")   # no surprise meals unless a test asks
    w.poops_enabled = False         # nor toilet trips after them
    w.lively = False                # nor naps, washes, yawns or zoomies
    return w


def run(cat, clock, until, max_seconds=120, each=None):
    """Tick the cat with a fake clock until until() is true."""
    for _ in range(int(max_seconds / TICK)):
        if until():
            return
        clock[0] += TICK
        cat._tick()
        if each:
            each()
    raise AssertionError("did not finish; stage=%r mode=%r" % (cat.stage, cat.mode))


def click(cat):
    cat.mousePressEvent(QMouseEvent(
        QMouseEvent.Type.MouseButtonPress, QPointF(10, 10), QPointF(10, 10),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier))


# ---- hills ----

def test_hill_target_stays_within_limits():
    rng = random.Random(1)
    for _ in range(500):
        y = rng.uniform(40, 980)
        dx = rng.uniform(-1500, 1500)
        ty = deskcat.hill_target_y(y, dx, 40, 980, rng)
        assert 40 <= ty <= 980
        rise, drop = y - ty, ty - y
        assert rise <= deskcat.HILL_UP_MAX + 1e-6
        assert drop <= deskcat.HILL_DOWN_MAX + 1e-6
        assert abs(ty - y) <= deskcat.HILL_SLOPE * abs(dx) + 1e-6


def test_hill_target_no_sideways_means_no_height_change():
    assert deskcat.hill_target_y(300, 0, 40, 980) == 300


def test_hill_target_clamps_a_cat_that_is_out_of_range():
    assert deskcat.hill_target_y(5, 0, 40, 980) == 40


def test_walk_targets_follow_the_hill_rule(cat):
    for _ in range(200):
        cat.x, cat.y = 700.0, 500.0
        cat._pick_target()
        assert cat.y - cat.target_y <= deskcat.HILL_UP_MAX
        assert cat.target_y - cat.y <= deskcat.HILL_DOWN_MAX


def test_startle_dash_follows_the_hill_rule(cat):
    for _ in range(100):
        cat.x, cat.y = 700.0, 500.0
        cat._startle()
        assert cat.mode == "dash"
        assert cat.y - cat.target_y <= deskcat.HILL_UP_MAX
        assert cat.target_y - cat.y <= deskcat.HILL_DOWN_MAX


# ---- flight ----

def test_flight_top_y():
    assert deskcat.flight_top_y(1000, "small", 1000) == 750
    assert deskcat.flight_top_y(1000, "medium", 1000) == 500
    assert deskcat.flight_top_y(1000, "huge", 1000) == deskcat.BIG_DY
    assert deskcat.flight_top_y(300, "medium", 1000) == deskcat.BIG_DY


@pytest.mark.parametrize("size", ["small", "medium", "huge"])
def test_full_flight(cat, clock, size):
    start_y = cat.y
    expected_top = deskcat.flight_top_y(start_y, size, cat.screen_h)
    assert cat._start_flight(size=size, early=False)
    assert cat.mode == "bubble"

    lowest = [cat.y]
    stages = []

    def watch():
        lowest[0] = min(lowest[0], cat.y)
        if cat.stage and (not stages or stages[-1] != cat.stage):
            stages.append(cat.stage)

    run(cat, clock, lambda: cat.mode != "bubble", each=watch)

    assert stages == ["look", "chew1", "blow1", "pop1", "annoyed", "chew2",
                      "blow2", "lift", "float", "shrink", "poke", "pop2",
                      "fall", "land", "shake"]
    assert cat.mode == "idle"
    assert cat.stage is None
    assert (cat.width(), cat.height()) == (cat.W, cat.H)
    assert lowest[0] >= deskcat.BIG_DY - 1
    assert lowest[0] == pytest.approx(expected_top, abs=deskcat.FLOAT_SPEED + 1)
    assert cat.y == pytest.approx(lowest[0] + deskcat.POP_DROP, abs=1)


def test_window_grows_only_while_the_big_bubble_is_out(cat, clock):
    cat._start_flight(size="huge", early=False)
    seen = {}

    def watch():
        if cat.stage:
            seen[cat.stage] = (cat.width(), cat.height())

    run(cat, clock, lambda: cat.mode != "bubble", each=watch)
    big = (cat.W + 2 * deskcat.BIG_DX, cat.H + deskcat.BIG_DY)
    for stage in ("look", "chew1", "blow1", "pop1", "annoyed", "chew2",
                  "fall", "land", "shake"):
        assert seen[stage] == (cat.W, cat.H), stage
    for stage in ("blow2", "lift", "float", "shrink", "poke", "pop2"):
        assert seen[stage] == big, stage


def test_burst_bubble_drops_the_cat_to_the_bottom(cat, clock):
    cat.y = start_y = float(cat.screen_h - cat.H - 200)   # start above the bottom
    full_top = deskcat.flight_top_y(start_y, "huge", cat.screen_h)
    cat._start_flight(size="huge", early=True)
    stages, heights = [], []

    def watch():
        heights.append(cat.y)
        if cat.stage and (not stages or stages[-1] != cat.stage):
            stages.append(cat.stage)

    run(cat, clock, lambda: cat.mode != "bubble", each=watch)
    assert "shrink" not in stages and "poke" not in stages
    assert stages[-5:] == ["pop2", "panic", "fall", "land", "blush"]
    assert min(heights) == pytest.approx((start_y + full_top) / 2, abs=3)
    assert cat.y == cat.screen_h - cat.H
    assert (cat.width(), cat.height()) == (cat.W, cat.H)


def test_flight_stays_below_the_menu_bar(cat, clock):
    cat.screen_top = 34
    assert deskcat.flight_top_y(1000, "huge", 1000, top=34) == deskcat.BIG_DY + 34
    cat._start_flight(size="huge", early=False)
    tops = []
    run(cat, clock, lambda: cat.mode != "bubble",
        each=lambda: tops.append(cat.pos().y()))
    assert min(tops) == 34
    cat.y = 34 + deskcat.BIG_DY + deskcat.BUBBLE_MIN_ROOM - 1
    assert not cat._start_flight()


def test_no_flight_without_room_above(cat):
    cat.y = deskcat.BIG_DY + deskcat.BUBBLE_MIN_ROOM - 1
    assert not cat._start_flight()
    assert cat.mode == "idle"
    cat.y = deskcat.BIG_DY + deskcat.BUBBLE_MIN_ROOM
    assert cat._start_flight()


def test_no_second_flight_while_one_is_running(cat):
    assert cat._start_flight(size="small", early=False)
    assert not cat._start_flight(size="huge", early=False)
    assert cat.bubble_size == "small"


@pytest.mark.parametrize("stage", ["look", "chew1", "blow1", "pop1",
                                   "annoyed", "chew2", "blow2"])
def test_click_on_the_ground_cancels_and_dashes(cat, clock, stage):
    start_y = cat.y
    cat._start_flight(size="medium", early=False)
    run(cat, clock, lambda: cat.stage == stage)
    click(cat)
    assert cat.mode == "dash"
    assert cat.stage is None
    assert cat.y == start_y
    assert (cat.width(), cat.height()) == (cat.W, cat.H)


@pytest.mark.parametrize("stage", ["lift", "float", "shrink", "poke", "pop2",
                                   "fall", "land", "shake"])
def test_click_in_the_air_pops_then_dashes(cat, clock, stage):
    start_y = cat.y
    cat._start_flight(size="medium", early=False)
    run(cat, clock, lambda: cat.stage == stage)
    if stage == "float":
        run(cat, clock, lambda: cat.y < start_y - 120)
    click(cat)
    assert cat.mode == "bubble" or cat.mode == "dash"
    run(cat, clock, lambda: cat.mode != "bubble")
    assert cat.mode == "dash"
    assert cat.stage is None
    assert (cat.width(), cat.height()) == (cat.W, cat.H)
    assert deskcat.TOP_MARGIN <= cat.y <= cat.screen_h - cat.H


def anchor(cat):
    """Where the cat itself is on screen, whatever the window size."""
    return (cat.pos().x() + cat.width() // 2, cat.pos().y() + cat.height() - 54)


@pytest.mark.parametrize("early", [False, True])
def test_cat_never_jumps_on_screen_during_a_flight(cat, clock, early):
    cat._start_flight(size="huge", early=early)
    last = [anchor(cat)]

    def watch():
        ax, ay = anchor(cat)
        assert abs(ax - last[0][0]) <= 3, cat.stage
        limit = 60 if cat.stage in ("fall", "land") else 3
        assert abs(ay - last[0][1]) <= limit, cat.stage
        last[0] = (ax, ay)

    clock[0] += TICK
    cat._tick()
    last[0] = anchor(cat)
    run(cat, clock, lambda: cat.mode != "bubble", each=watch)


@pytest.mark.parametrize("stage", ["blow2", "lift", "float", "poke", "pop2"])
def test_click_does_not_make_the_cat_jump(cat, clock, stage):
    cat._start_flight(size="huge", early=False)
    run(cat, clock, lambda: cat.stage == stage)
    before = anchor(cat)
    click(cat)
    assert anchor(cat) == before


def test_break_reminder_during_a_flight_is_harmless(cat, clock):
    cat._start_flight(size="medium", early=False)
    run(cat, clock, lambda: cat.stage == "float")
    cat._show_break()
    assert cat.break_window is not None
    run(cat, clock, lambda: cat.mode != "bubble")
    assert cat.mode == "idle"
    cat.break_window.close()


def test_idle_cat_sometimes_takes_a_bubble(cat, clock, monkeypatch):
    monkeypatch.setattr(deskcat, "BUBBLE_CHANCE", 1.0)
    monkeypatch.setattr(deskcat.random, "random", lambda: 0.1)  # "go somewhere"
    cat.idle_until = clock[0]
    clock[0] += TICK
    cat._tick()
    assert cat.mode == "bubble"


def test_every_stage_paints(cat, clock):
    """Smoke test: painting never raises at any point of a flight."""
    for early in (False, True):
        cat.y = float(cat.screen_h - cat.H)
        cat.mode = "idle"
        cat._start_flight(size="huge", early=early)
        run(cat, clock, lambda: cat.mode != "bubble", each=cat.grab)


# ---- never too long without a flight ----

def test_flight_is_forced_after_the_maximum_wait(cat, clock, monkeypatch):
    monkeypatch.setattr(deskcat, "BUBBLE_CHANCE", 0.0)
    cat.last_flight_at = clock[0]
    cat._pick_target()                      # busy walking
    clock[0] += deskcat.BUBBLE_MAX_MINUTES * 60 - 1
    cat._tick()
    assert cat.mode != "bubble"
    clock[0] += 1
    cat._tick()
    assert cat.mode == "bubble"
    assert cat.last_flight_at == clock[0]


def test_overdue_cat_near_the_top_walks_down_then_flies(cat, clock, monkeypatch):
    monkeypatch.setattr(deskcat, "BUBBLE_CHANCE", 0.0)
    cat.y = float(deskcat.TOP_MARGIN)
    cat.last_flight_at = clock[0] - deskcat.BUBBLE_MAX_MINUTES * 60
    cat.idle_until = clock[0]
    start = clock[0]
    run(cat, clock, lambda: cat.mode == "bubble", max_seconds=300)
    assert cat.y - deskcat.BIG_DY >= deskcat.BUBBLE_MIN_ROOM
    assert clock[0] - start < 240


def test_no_limit_when_maximum_is_zero(cat, clock, monkeypatch):
    monkeypatch.setattr(deskcat, "BUBBLE_CHANCE", 0.0)
    monkeypatch.setattr(deskcat, "BUBBLE_MAX_MINUTES", 0)
    cat.last_flight_at = clock[0] - 99999
    cat._pick_target()
    clock[0] += TICK
    cat._tick()
    assert cat.mode != "bubble"


# ---- coming down: parachute and jump ----

def high_cat(cat):
    cat.y = 100.0
    cat.x = 300.0
    return cat


def collect(cat, clock):
    stages, heights = [], []

    def watch():
        heights.append(cat.y)
        if cat.stage and (not stages or stages[-1] != cat.stage):
            stages.append(cat.stage)

    run(cat, clock, lambda: cat.mode != "bubble", each=watch)
    return stages, heights


def test_parachute_drifts_down_and_lands(cat, clock):
    high_cat(cat)
    assert cat._start_descent(kind="down", early=False)
    target = cat.floor_y
    assert target - 100 >= 0.5 * (cat.screen_h - cat.H - 100) - 1
    stages, heights = collect(cat, clock)
    assert stages == ["look", "chew1", "blow2", "lift", "drift", "release"]
    assert cat.mode == "idle" and cat.stage is None
    assert cat.y == pytest.approx(target)
    assert min(heights) >= 100 - 1e-6            # never goes up
    assert max(b - a for a, b in zip(heights, heights[1:])) <= deskcat.DRIFT_SPEED + 1e-6
    assert (cat.width(), cat.height()) == (cat.W, cat.H)


def test_parachute_burst_falls_to_the_bottom(cat, clock):
    high_cat(cat)
    cat._start_descent(kind="down", early=True)
    target = cat.floor_y
    stages, heights = collect(cat, clock)
    assert stages == ["look", "chew1", "blow2", "lift", "drift", "pop2",
                      "panic", "fall", "land", "blush"]
    assert cat.y == cat.screen_h - cat.H
    assert target <= cat.y


def test_jump_lands_lower_and_to_the_side(cat, clock):
    high_cat(cat)
    cat.facing = 1
    assert cat._start_descent(kind="jump")
    target = cat.floor_y
    assert deskcat.JUMP_MIN <= target - 100 <= deskcat.JUMP_MAX
    stages, heights = collect(cat, clock)
    assert stages == ["look", "crouch", "leap", "land"]
    assert cat.mode == "idle"
    assert cat.y == pytest.approx(target)
    assert cat.x > 300 + 50
    assert min(heights) >= 100 - deskcat.LEAP_RISE - 1
    assert (cat.width(), cat.height()) == (cat.W, cat.H)


def test_jump_turns_away_from_a_wall(cat, clock):
    high_cat(cat)
    cat.x = float(cat.screen_w - cat.W)
    cat.facing = 1
    cat._start_descent(kind="jump")
    collect(cat, clock)
    assert cat.facing == -1
    assert 0 <= cat.x < cat.screen_w - cat.W - 50


def test_short_room_means_a_jump_not_a_parachute(cat):
    cat.y = float(cat.screen_h - cat.H - 200)
    assert cat._start_descent(kind="down")
    assert cat.flight_kind == "jump"
    assert cat.floor_y <= cat.screen_h - cat.H


def test_no_descent_near_the_bottom(cat):
    cat.y = float(cat.screen_h - cat.H - deskcat.DESCENT_MIN_ROOM + 1)
    assert not cat._start_descent()
    assert cat.mode == "idle"


@pytest.mark.parametrize("kind,stage", [("down", "chew1"), ("down", "blow2"),
                                        ("down", "release"), ("jump", "crouch")])
def test_click_on_the_ground_cancels_a_descent(cat, clock, kind, stage):
    high_cat(cat)
    cat._start_descent(kind=kind, early=False)
    run(cat, clock, lambda: cat.stage == stage)
    before = anchor(cat)
    click(cat)
    assert anchor(cat) == before
    assert cat.mode == "dash" and cat.stage is None
    assert (cat.width(), cat.height()) == (cat.W, cat.H)


@pytest.mark.parametrize("kind,stage", [("down", "lift"), ("down", "drift"),
                                        ("jump", "leap")])
def test_click_in_the_air_during_a_descent(cat, clock, kind, stage):
    high_cat(cat)
    cat._start_descent(kind=kind, early=False)
    target = cat.floor_y
    run(cat, clock, lambda: cat.stage == stage)
    if stage == "drift":
        run(cat, clock, lambda: cat.y > 180)
    before = anchor(cat)
    click(cat)
    assert anchor(cat) == before
    run(cat, clock, lambda: cat.mode != "bubble")
    assert cat.mode == "dash"
    assert cat.y <= target + 1e-6                 # a click never drops it further
    assert (cat.width(), cat.height()) == (cat.W, cat.H)


def test_idle_cat_sometimes_takes_a_trip_down(cat, clock, monkeypatch):
    high_cat(cat)
    monkeypatch.setattr(deskcat, "BUBBLE_CHANCE", 0.0)
    monkeypatch.setattr(deskcat, "DESCENT_CHANCE", 1.0)
    cat.idle_until = clock[0]
    clock[0] += TICK
    cat._tick()
    assert cat.mode == "bubble"
    assert cat.flight_kind in ("down", "jump")


def test_descents_paint_and_never_jump_on_screen(cat, clock):
    for kind, early in (("down", False), ("down", True), ("jump", False)):
        high_cat(cat)
        cat.mode = "idle"
        cat._start_descent(kind=kind, early=early)
        clock[0] += TICK
        cat._tick()
        last = [anchor(cat)]

        def watch():
            cat.grab()
            ax, ay = anchor(cat)
            fast = cat.stage in ("fall", "leap", "land")
            assert abs(ax - last[0][0]) <= (8 if fast else 3), cat.stage
            assert abs(ay - last[0][1]) <= (60 if fast else 3), cat.stage
            last[0] = (ax, ay)

        run(cat, clock, lambda: cat.mode != "bubble", each=watch)


# ---- mealtime ----

def serve(cat, clock, bowl_y, bowl_cx=400.0, monkeypatch=None):
    """Serve a meal at a chosen spot instead of a random one."""
    cat._serve_meal(clock[0])
    cat.bowl_y, cat.bowl_cx = float(bowl_y), float(bowl_cx)
    cat.bowl.move(int(bowl_cx - cat.bowl.W / 2),
                  int(bowl_y + deskcat.GROUND - cat.bowl.BASE))


def eat_whole_meal(cat, clock, max_seconds=400):
    modes = set()
    run(cat, clock, lambda: cat.mode == "eat", max_seconds=max_seconds,
        each=lambda: modes.add((cat.mode, cat.flight_kind if cat.mode == "bubble" else "")))
    # Standing level with the bowl, facing it, the bowl just in front.
    assert cat.y == pytest.approx(cat.bowl_y, abs=2)
    cat_cx = cat.x + cat.W / 2
    assert cat_cx + cat.facing * deskcat.EAT_REACH == pytest.approx(cat.bowl_cx, abs=3)
    run(cat, clock, lambda: cat.mode != "eat", each=cat.grab)
    assert cat.mode == "sit" and not cat.hungry
    assert cat.bowl.level == 0
    run(cat, clock, lambda: cat.bowl is None, max_seconds=5)
    return modes


def test_meal_is_served_when_due_and_scheduled_again(cat, clock, monkeypatch):
    monkeypatch.setattr(deskcat, "BUBBLE_MAX_MINUTES", 0)
    cat.next_meal_at = clock[0] + 1
    cat._pick_target()
    run(cat, clock, lambda: cat.hungry, max_seconds=3)
    assert cat.bowl is not None and cat.bowl.isVisible()
    lo = cat.screen_top + deskcat.BIG_DY + deskcat.POP_DROP
    assert lo <= cat.bowl_y <= cat.screen_h - cat.H
    assert cat.W <= cat.bowl_cx <= cat.screen_w - cat.W
    eat_whole_meal(cat, clock)
    wait = cat.next_meal_at - clock[0]
    assert deskcat.MEAL_MIN_MINUTES * 60 - 10 <= wait <= deskcat.MEAL_MAX_MINUTES * 60


def test_bowl_on_the_same_level_is_walked_to(cat, clock):
    serve(cat, clock, bowl_y=cat.y, bowl_cx=150.0)
    modes = eat_whole_meal(cat, clock)
    assert ("bubble", "up") not in modes and ("walk", "") in modes


def test_bowl_high_above_is_reached_by_bubble(cat, clock, monkeypatch):
    monkeypatch.setattr(deskcat, "EARLY_POP_CHANCE", 0.0)
    serve(cat, clock, bowl_y=250)
    modes = eat_whole_meal(cat, clock)
    assert ("bubble", "up") in modes


def test_bowl_far_below_is_reached_by_parachute(cat, clock, monkeypatch):
    monkeypatch.setattr(deskcat, "EARLY_POP_CHANCE", 0.0)
    cat.y = 150.0
    serve(cat, clock, bowl_y=cat.screen_h - cat.H)
    modes = eat_whole_meal(cat, clock)
    assert ("bubble", "down") in modes


def test_bowl_a_bit_below_is_reached_by_jump(cat, clock):
    cat.y = 300.0
    serve(cat, clock, bowl_y=500, bowl_cx=cat.x + cat.W / 2 + 60)
    modes = eat_whole_meal(cat, clock)
    assert ("bubble", "jump") in modes


def test_burst_bubble_on_the_way_still_ends_in_dinner(cat, clock, monkeypatch):
    serve(cat, clock, bowl_y=250)
    bursts = iter([True])
    real = cat._start_flight
    monkeypatch.setattr(cat, "_start_flight",
                        lambda **kw: real(early=next(bursts, False), **kw))
    eat_whole_meal(cat, clock)


def test_click_while_eating_scares_it_off_but_it_comes_back(cat, clock):
    serve(cat, clock, bowl_y=cat.y, bowl_cx=300.0)
    run(cat, clock, lambda: cat.mode == "eat" and cat.food_left < 0.6)
    click(cat)
    assert cat.mode == "dash"
    left = cat.food_left
    run(cat, clock, lambda: cat.mode == "eat", max_seconds=200)
    assert cat.food_left == pytest.approx(left)
    run(cat, clock, lambda: cat.mode != "eat")
    assert not cat.hungry


def test_unreached_bowl_is_taken_away(cat, clock):
    serve(cat, clock, bowl_y=250)
    cat.meal_deadline = clock[0]
    clock[0] += TICK
    cat._tick()
    assert not cat.hungry
    run(cat, clock, lambda: cat.bowl is None, max_seconds=5)
    assert cat.next_meal_at > clock[0]


def test_hungry_cat_skips_the_overdue_flight(cat, clock):
    serve(cat, clock, bowl_y=cat.y, bowl_cx=600.0)
    cat.last_flight_at = clock[0] - 99999
    run(cat, clock, lambda: cat.mode == "eat", max_seconds=200,
        each=lambda: None if cat.mode != "bubble" else pytest.fail("flew"))


def test_many_random_meals_all_get_eaten(cat, clock, monkeypatch):
    monkeypatch.setattr(deskcat, "BUBBLE_MAX_MINUTES", 0)
    for seed in range(12):
        random.seed(seed)
        cat.x = float(random.randint(0, cat.screen_w - cat.W))
        cat.y = float(random.randint(deskcat.TOP_MARGIN, cat.screen_h - cat.H))
        cat.mode = "idle"
        cat._serve_meal(clock[0])
        cat.meal_deadline = float("inf")
        eat_whole_meal(cat, clock, max_seconds=900)


# ---- toilet ----

def place_litter(cat, clock, y, cx):
    """Put out a litter box at a chosen spot instead of a random one."""
    cat._serve_litter(clock[0])
    cat.litter_y, cat.litter_cx = float(y), float(cx)
    cat.litter.move(int(cx - cat.litter.W / 2),
                    int(y + deskcat.GROUND - cat.litter.BASE))


def use_the_box(cat, clock, max_seconds=400):
    run(cat, clock, lambda: cat.mode == "poop", max_seconds=max_seconds)
    # Standing right in the tray.
    assert cat.y == pytest.approx(cat.litter_y, abs=2)
    assert cat.x + cat.W / 2 == pytest.approx(cat.litter_cx, abs=3)
    run(cat, clock, lambda: cat.mode != "poop", each=cat.grab)
    assert cat.errand is None and cat.mode == "idle"
    assert cat.poops == []
    run(cat, clock, lambda: cat.litter is None, max_seconds=5)


def have_accident(cat, clock):
    cat.force_poop = "accident"
    cat._need_toilet(clock[0])
    assert cat.litter is None
    run(cat, clock, lambda: cat.poops, max_seconds=10, each=cat.grab)
    return cat.poops[0]


def click_poop(poop):
    poop.mousePressEvent(QMouseEvent(
        QMouseEvent.Type.MouseButtonPress, QPointF(10, 10), QPointF(10, 10),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier))


def test_a_meal_is_followed_by_a_toilet_trip(cat, clock, monkeypatch):
    monkeypatch.setattr(deskcat, "BUBBLE_MAX_MINUTES", 0)
    monkeypatch.setattr(deskcat, "ACCIDENT_CHANCE", 0.0)
    cat.poops_enabled = True
    serve(cat, clock, bowl_y=cat.y, bowl_cx=300.0)
    eat_whole_meal(cat, clock)
    wait = cat.next_poop_at - clock[0]
    assert deskcat.POOP_MIN_MINUTES * 60 - 10 <= wait <= deskcat.POOP_MAX_MINUTES * 60
    run(cat, clock, lambda: cat.litter is not None, max_seconds=200)
    assert cat.errand == "litter" and cat.litter.isVisible()
    use_the_box(cat, clock)
    assert cat.next_poop_at == float("inf")   # nothing more until the next meal


def test_litter_boxes_anywhere_all_get_used(cat, clock, monkeypatch):
    monkeypatch.setattr(deskcat, "BUBBLE_MAX_MINUTES", 0)
    for seed in range(12):
        random.seed(seed)
        cat.x = float(random.randint(0, cat.screen_w - cat.W))
        cat.y = float(random.randint(deskcat.TOP_MARGIN, cat.screen_h - cat.H))
        cat.mode = "idle"
        cat.force_poop = "box"
        cat._need_toilet(clock[0])
        cat.litter_deadline = float("inf")
        use_the_box(cat, clock, max_seconds=900)


@pytest.mark.parametrize("stage, after", [("squat", 0.5), ("squat", 2.5), ("cover", 0.5)])
def test_click_at_the_litter_box(cat, clock, stage, after):
    place_litter(cat, clock, cat.y, 300.0)
    run(cat, clock, lambda: cat.mode == "poop" and cat.poop_stage == stage
        and clock[0] - cat.poop_t0 >= after)
    click(cat)
    assert cat.mode == "dash"
    if stage == "squat":
        use_the_box(cat, clock)          # it comes back and finishes
    else:
        # Already done: it doesn't go again, and the box is cleared away.
        run(cat, clock, lambda: cat.litter is None, max_seconds=5)
        assert cat.errand is None
    assert cat.poops == []
    assert (cat.width(), cat.height()) == (cat.W, cat.H)


def test_accident_leaves_a_poop_behind_the_cat(cat, clock):
    cat.x, cat.facing = 300.0, 1
    y = cat.y
    poop = have_accident(cat, clock)
    assert poop.isVisible()
    # On the cat's ground line, behind it.
    assert poop.pos().y() + poop.BASE == pytest.approx(y + deskcat.GROUND, abs=1)
    poop_cx = poop.pos().x() + poop.W / 2
    assert poop_cx == pytest.approx(300 + cat.W / 2 - cat.facing * deskcat.POOP_BEHIND, abs=1)
    assert cat.errand is None
    # It slinks off far enough that its own window no longer covers the poop.
    run(cat, clock, lambda: cat.mode == "idle", max_seconds=30)
    assert not (cat.x < poop.pos().x() + poop.W and poop.pos().x() < cat.x + cat.W)


def test_accident_near_an_edge_still_uncovers_the_poop(cat, clock):
    for x, facing in ((0.0, -1), (float(cat.screen_w - cat.W), 1)):
        cat.x, cat.facing, cat.mode = x, facing, "idle"
        poop = have_accident(cat, clock)
        assert 0 <= poop.pos().x() <= cat.screen_w - poop.W
        run(cat, clock, lambda: cat.mode == "idle", max_seconds=30)
        assert not (cat.x < poop.pos().x() + poop.W and poop.pos().x() < cat.x + cat.W)
        click_poop(poop)
        run(cat, clock, lambda: not cat.poops, max_seconds=3)


def test_clicking_a_poop_cleans_it_up(cat, clock):
    poop = have_accident(cat, clock)
    click_poop(poop)
    assert poop.cleaned_at is not None
    run(cat, clock, lambda: not cat.poops, max_seconds=2, each=poop.grab)
    assert not poop.isVisible()


def test_unclicked_poop_fades_by_itself(cat, clock):
    poop = have_accident(cat, clock)
    clock[0] += deskcat.POOP_STAY_MINUTES * 60 - 30
    cat._tick()
    assert cat.poops == [poop]
    clock[0] += 30
    run(cat, clock, lambda: not cat.poops, max_seconds=3)


def test_two_poops_can_be_out_at_once(cat, clock):
    cat.x = 100.0
    first = have_accident(cat, clock)
    run(cat, clock, lambda: cat.mode == "idle", max_seconds=30)
    cat.force_poop = "accident"
    cat._need_toilet(clock[0])
    run(cat, clock, lambda: len(cat.poops) == 2, max_seconds=10)
    second = cat.poops[1]
    assert cat.poops == [first, second] and first.isVisible()
    click_poop(first)
    run(cat, clock, lambda: cat.poops == [second], max_seconds=2)
    click_poop(second)
    run(cat, clock, lambda: not cat.poops, max_seconds=2)


def test_click_mid_accident_delays_it_but_it_still_happens(cat, clock):
    cat.x = 300.0
    cat.force_poop = "accident"
    cat._need_toilet(clock[0])
    run(cat, clock, lambda: cat.mode == "poop" and clock[0] - cat.poop_t0 > 1)
    click(cat)
    assert cat.mode == "dash" and cat.poops == []
    run(cat, clock, lambda: cat.poops, max_seconds=60)
    run(cat, clock, lambda: cat.mode == "idle", max_seconds=30)
    assert cat.errand is None


def test_no_accident_where_the_dock_would_hide_it(cat, clock):
    cat.avail_bottom = cat.screen_h - 80     # pretend there is a Dock
    cat.y = float(cat.screen_h - cat.H)
    cat.force_poop = "accident"
    cat._need_toilet(clock[0])
    assert cat.errand == "litter" and cat.litter is not None
    assert cat.litter_y + deskcat.GROUND <= cat.avail_bottom
    use_the_box(cat, clock)


def test_unreached_litter_box_ends_in_an_accident(cat, clock):
    cat.y = 300.0
    place_litter(cat, clock, 300.0, 600.0)
    cat.litter_deadline = clock[0]
    run(cat, clock, lambda: cat.poops, max_seconds=30)
    run(cat, clock, lambda: cat.litter is None, max_seconds=5)
    assert cat.errand is None


def test_meal_due_during_a_toilet_trip_waits_its_turn(cat, clock, monkeypatch):
    monkeypatch.setattr(deskcat, "BUBBLE_MAX_MINUTES", 0)
    place_litter(cat, clock, cat.y, 300.0)
    cat.next_meal_at = clock[0]
    run(cat, clock, lambda: cat.mode == "poop")
    assert cat.bowl is None
    run(cat, clock, lambda: cat.hungry, max_seconds=30)
    assert cat.errand == "food"
    cat.meal_deadline = float("inf")
    eat_whole_meal(cat, clock, max_seconds=900)


def test_toilet_due_during_a_meal_waits_its_turn(cat, clock, monkeypatch):
    monkeypatch.setattr(deskcat, "BUBBLE_MAX_MINUTES", 0)
    serve(cat, clock, bowl_y=cat.y, bowl_cx=300.0)
    cat.next_poop_at, cat.force_poop = clock[0], "box"
    run(cat, clock, lambda: cat.mode == "eat")
    assert cat.litter is None and cat.errand == "food"
    run(cat, clock, lambda: cat.litter is not None, max_seconds=30)
    cat.litter_deadline = float("inf")
    use_the_box(cat, clock, max_seconds=900)


def test_cat_on_a_toilet_trip_skips_the_overdue_flight(cat, clock):
    place_litter(cat, clock, cat.y, 600.0)
    cat.last_flight_at = clock[0] - 99999
    run(cat, clock, lambda: cat.mode == "poop", max_seconds=200,
        each=lambda: None if cat.mode != "bubble" else pytest.fail("flew"))


# ---- a life of its own: naps, grooming, stretching, zoomies ----

@pytest.fixture
def day(monkeypatch):
    monkeypatch.setattr(deskcat, "is_night", lambda: False)


def lively(cat, clock):
    """Switch the spontaneous behaviours on, with nothing due yet."""
    cat.lively = True
    cat.next_nap_at = cat.next_zoom_at = float("inf")
    cat.last_flight_at = clock[0]
    cat.idle_until = clock[0]


def test_nap_starts_when_due_and_ends_with_a_stretch(cat, clock, day):
    lively(cat, clock)
    cat.next_nap_at = clock[0]
    run(cat, clock, lambda: cat.mode == "sleep", max_seconds=2)
    x, y, t0 = cat.x, cat.y, clock[0]
    run(cat, clock, lambda: cat.mode != "sleep", max_seconds=120, each=cat.grab)
    lo, hi = deskcat.NAP_SECONDS
    assert lo <= clock[0] - t0 <= hi + deskcat.YAWN_SECONDS + 1
    assert (cat.x, cat.y) == (x, y)
    assert cat.mode == "act" and cat.act == "stretch"
    run(cat, clock, lambda: cat.mode == "idle", max_seconds=5, each=cat.grab)
    wait = cat.next_nap_at - clock[0]
    assert deskcat.NAP_MIN_MINUTES * 60 - 10 <= wait <= deskcat.NAP_MAX_MINUTES * 60


def test_night_naps_are_longer(cat, clock, monkeypatch):
    monkeypatch.setattr(deskcat, "is_night", lambda: True)
    cat._start_nap(clock[0])
    assert cat.sleep_until - clock[0] >= deskcat.NIGHT_NAP_SECONDS[0]
    assert deskcat.NIGHT_NAP_SECONDS[0] > deskcat.NAP_SECONDS[1]


def test_is_night_follows_the_clock(monkeypatch):
    import time as real_time
    for hour, night in ((23, True), (3, True), (7, False), (12, False), (21, False), (22, True)):
        monkeypatch.setattr(deskcat.time, "localtime",
                            lambda h=hour: real_time.struct_time((2026, 1, 1, h, 0, 0, 0, 1, 0)))
        assert deskcat.is_night() is night


def test_click_wakes_it_grumpy_and_a_second_click_scares_it(cat, clock, day):
    cat._start_nap(clock[0])
    run(cat, clock, lambda: clock[0] - cat.sleep_t0 > 5, each=cat.grab)
    x = cat.x
    click(cat)
    assert cat.mode == "act" and cat.act == "grumpy" and cat.x == x
    cat.grab()
    click(cat)
    assert cat.mode == "dash"
    run(cat, clock, lambda: cat.mode == "idle", max_seconds=30)


def test_click_during_the_yawn_also_wakes_it(cat, clock, day):
    cat._start_nap(clock[0])
    clock[0] += 0.3
    cat._tick(); cat.grab()
    click(cat)
    assert cat.act == "grumpy"
    run(cat, clock, lambda: cat.mode == "idle", max_seconds=5, each=cat.grab)


def test_meal_and_toilet_wait_for_the_nap_to_end(cat, clock, day):
    cat._start_nap(clock[0])
    cat.next_meal_at = clock[0]
    cat.next_poop_at, cat.force_poop = clock[0], "box"
    run(cat, clock, lambda: cat.mode != "sleep", max_seconds=120,
        each=lambda: None if cat.bowl is None and cat.litter is None else pytest.fail("woken"))
    run(cat, clock, lambda: cat.errand is not None, max_seconds=10)


def test_overdue_flight_cuts_the_nap_short(cat, clock, monkeypatch):
    monkeypatch.setattr(deskcat, "is_night", lambda: True)
    cat.last_flight_at = clock[0] - (deskcat.BUBBLE_MAX_MINUTES * 60 - 20)
    cat._start_nap(clock[0])
    run(cat, clock, lambda: cat.mode == "bubble", max_seconds=40)
    assert clock[0] - cat.sleep_t0 >= 19


@pytest.mark.parametrize("act", ["groom", "stretch", "grumpy"])
def test_acts_paint_end_idle_and_can_be_interrupted(cat, clock, act):
    x, y = cat.x, cat.y
    cat._start_act(act, clock[0])
    run(cat, clock, lambda: cat.mode == "idle", max_seconds=10, each=cat.grab)
    assert (cat.x, cat.y) == (x, y) and cat.act is None
    cat._start_act(act, clock[0])
    clock[0] += 0.5
    cat._tick()
    click(cat)
    assert cat.mode == "dash" and cat.act is None
    run(cat, clock, lambda: cat.mode == "idle", max_seconds=30, each=cat.grab)


def test_it_washes_after_a_meal(cat, clock, day):
    lively(cat, clock)
    serve(cat, clock, bowl_y=cat.y, bowl_cx=300.0)
    eat_whole_meal(cat, clock)
    run(cat, clock, lambda: cat.mode == "act", max_seconds=15)
    assert cat.act == "groom"
    run(cat, clock, lambda: cat.mode == "idle", max_seconds=10)
    assert not cat.groom_next


def test_it_washes_after_an_accident(cat, clock, day):
    lively(cat, clock)
    cat.x = 300.0
    have_accident(cat, clock)
    run(cat, clock, lambda: cat.mode == "act", max_seconds=40)
    assert cat.act == "groom"


def test_after_the_litter_box_it_washes_or_zooms(cat, clock, day, monkeypatch):
    seen = set()
    for chance in (0.0, 1.0):
        monkeypatch.setattr(deskcat, "ZOOM_AFTER_BOX", chance)
        lively(cat, clock)
        cat.mode = "idle"
        place_litter(cat, clock, cat.y, 300.0)
        use_the_box(cat, clock)
        run(cat, clock, lambda: cat.mode in ("act", "dash"), max_seconds=10)
        seen.add("zoom" if cat.zoom_legs else cat.act)
        run(cat, clock, lambda: cat.mode == "idle", max_seconds=60)
    assert seen == {"groom", "zoom"}


@pytest.mark.parametrize("x", [0.0, 300.0, None])
def test_zoomies_run_back_and_forth_on_one_level(cat, clock, day, x):
    lively(cat, clock)
    cat.x = float(cat.screen_w - cat.W) if x is None else x
    cat.y = 300.0
    cat.next_zoom_at = clock[0]
    run(cat, clock, lambda: cat.mode == "dash", max_seconds=2)
    assert cat.zoom_legs >= 3
    turns, last = [], [cat.facing]

    def watch():
        cat.grab()
        assert 0 <= cat.x <= cat.screen_w - cat.W and cat.y == 300.0
        if cat.facing != last[0]:
            last[0] = cat.facing
            turns.append(clock[0])

    run(cat, clock, lambda: cat.mode != "dash", max_seconds=60, each=watch)
    assert cat.mode == "idle" and cat.zoom_legs == 0
    assert len(turns) >= 2
    assert cat.next_zoom_at - clock[0] >= deskcat.ZOOM_MIN_MINUTES * 60 - 30


def test_click_stops_the_zoomies(cat, clock, day):
    cat.x = 300.0
    cat._start_zoom(clock[0])
    clock[0] += TICK
    cat._tick()
    click(cat)
    assert cat.zoom_legs == 0 and cat.mode == "dash"
    run(cat, clock, lambda: cat.mode == "idle", max_seconds=30)


def test_nothing_spontaneous_while_on_an_errand(cat, clock, day):
    lively(cat, clock)
    cat.next_nap_at = cat.next_zoom_at = clock[0]
    cat.groom_next = True
    serve(cat, clock, bowl_y=cat.y, bowl_cx=600.0)
    run(cat, clock, lambda: cat.mode == "eat", max_seconds=200,
        each=lambda: None if cat.mode in ("idle", "walk", "eat") else pytest.fail(cat.mode))


def test_a_long_lively_day_never_gets_stuck(cat, clock, monkeypatch):
    """Everything switched on for four simulated hours."""
    monkeypatch.setattr(deskcat, "is_night", lambda: False)
    cat.lively = cat.poops_enabled = True
    cat.next_meal_at = clock[0] + 60
    cat.next_nap_at = clock[0] + 120
    cat.next_zoom_at = clock[0] + 200
    cat.idle_until = clock[0]
    seen, since, mode = set(), [clock[0]], [cat.mode]
    for i in range(int(4 * 3600 / TICK)):
        clock[0] += TICK
        cat._tick()
        if cat.mode != mode[0]:
            mode[0], since[0] = cat.mode, clock[0]
            seen.add(cat.mode if cat.mode != "act" else cat.act)
        assert clock[0] - since[0] < 400, "stuck in %s" % cat.mode
        assert 0 <= cat.x <= cat.screen_w - cat.W
        for poop in list(cat.poops):
            if poop.cleaned_at is None and random.random() < 0.001:
                click_poop(poop)
    assert {"sleep", "groom", "stretch", "eat", "poop", "bubble", "dash"} <= seen

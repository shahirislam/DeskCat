# Bubble Gum Flight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The cat walks only on gentle invisible hills and uses a bubble-gum balloon for long climbs.

**Architecture:** Everything stays in `deskcat.py`. Two pure helper functions decide where the cat may walk and how high a bubble carries it. `CatWidget` gains a `"bubble"` mode driven by a small table of timed stages. `draw_cat` gains a `"hang"` pose and an optional `fx` dict for the new expressions and the bubble; existing callers are unchanged.

**Tech Stack:** Python 3.10+, PyQt6, pytest (tests only).

**Spec:** `docs/superpowers/specs/2026-11-24-bubble-gum-flight-design.md`

## Global Constraints

- No new dependencies and no new asset files.
- `BreakWindow`'s existing `draw_cat(...)` call must keep working unchanged.
- The folder is not a git repository: no commit steps.
- `self.x` / `self.y` always mean the top-left of the normal 150×120 window, even while the window is enlarged, so every existing clamp stays valid.

## Review Focus

- Flight requested with too little room above: must not start (or must cap), never push the bubble off the top.
- Click during every stage of the flight: the cat must always end up back in a normal mode with the normal window size.
- Cat at the very bottom or very top edge: hill walks stay inside the screen.
- Very short sideways walk: slope cap must make the height change tiny, not produce a steep walk.
- Break reminder appearing mid-flight: flight continues, nothing crashes.

---

### Task 1: Hill walking

**Files:** Modify `deskcat.py`; create `tests/test_deskcat.py`.

**Produces:**
- Settings `HILL_UP_MAX = 60`, `HILL_DOWN_MAX = 180`, `HILL_SLOPE = 0.2`, `TOP_MARGIN = 40`.
- `hill_target_y(y: float, dx: float, y_min: float, y_max: float, rng=random) -> float` — new height for a walk of `dx` px sideways: rise ≤ `min(HILL_UP_MAX, HILL_SLOPE*|dx|)`, drop ≤ `min(HILL_DOWN_MAX, HILL_SLOPE*|dx|)`, clamped to `[y_min, y_max]`.

- [ ] Tests: 500 random calls stay within the rise/drop/slope limits and the clamp; `dx = 0` returns `y` (clamped).
- [ ] Implement; use it in `_pick_target` and `_startle`.
- [ ] Run `python3 -m pytest tests -q`.

### Task 2: Flight logic

**Produces:**
- Settings `BUBBLE_CHANCE = 0.08`, `EARLY_POP_CHANCE = 0.03`, `FLOAT_SPEED = 2.0`, `POP_DROP = 50`, `BUBBLE_MIN_ROOM = 150`, `BUBBLE_SIZES = {"small": (26, 0.25), "medium": (34, 0.5), "huge": (44, 1.0)}` (radius, fraction of screen height), `BIG_DX = 20`, `BIG_DY = 85` (how much the window grows left/right and upward).
- `flight_top_y(y: float, size: str, screen_h: int) -> float` — height where the bubble pops: `max(top + BIG_DY, y - fraction*screen_h)`, where `top` is the height of the macOS menu bar (0 elsewhere).
- `CatWidget._start_flight(size=None, early=None) -> bool` (False if less than `BUBBLE_MIN_ROOM` above), `_tick_bubble(now)`, `_set_stage(name, now)`, `_set_big(flag)`.
- Stage order: look → chew1 → blow1 → pop1 → annoyed → chew2 → blow2 → lift → float → shrink → poke → pop2 → fall → land → shake. Early pop: float → pop2 → panic → fall → land → blush.
- Window is enlarged from `blow2` until `fall`.
- Click: on the ground before lift → cancel and startle; airborne → pop now, startle after landing.
- `--bubble[=small|medium|huge|early]` starts the cat at the bottom and forces a flight after 3 s.

- [ ] Tests (offscreen Qt, fake clock): a forced flight of each size ends in a normal mode with a 150×120 window, final `y` equals `flight_top_y + POP_DROP`, and `y` never goes below `BIG_DY`; `_start_flight` returns False near the top; clicking at each stage still ends normally; an early flight lands lower than a full one.
- [ ] Implement.
- [ ] Run tests.

### Task 3: Drawing

**Produces:** `draw_cat(..., shadow=True, fx=None)`; pose `"hang"`; `fx` keys: `chew`, `annoyed`, `blush`, `look` (pupil offset), `bubble` (centre x, y, radius), `pop` (x, y, radius, 0..1 progress), `kick`, `poke`, `tilt`, `squash`.

- [ ] Implement the poses and expressions.
- [ ] Render every stage to PNG in the scratchpad and look at each one; fix what looks wrong.

### Task 4: Docs and end-to-end check

- [ ] README: describe the hills, the bubble flight, `--bubble`, and the new settings.
- [ ] Run `python3 deskcat.py --bubble` briefly and check the log for errors.

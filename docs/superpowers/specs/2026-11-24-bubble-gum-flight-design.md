# Bubble Gum Flight — design

Date: 2026-11-24. Status: waiting for approval.

## Why

Today the cat picks a random spot anywhere on screen and walks straight to it,
including steeply upward, which looks like it ignores gravity. We want upward
travel to be believable and to add personality: long climbs become a small
cartoon performance with bubble gum.

## The world: invisible hills

Decided by the owner: the cat lives on invisible ground that behaves like a
hill. It can walk uphill a little; to go a long way up it uses the bubble.

My calls on the numbers (all tunable settings at the top of `deskcat.py`):

- Every walk is mostly sideways. Uphill: at most about 60 px of rise per walk.
- Downhill is easier than uphill: at most about 180 px of drop per walk. This
  makes the cat drift down over time, and the bubble is what brings it back up.
- Slope is capped, so a walk with a big height change must also be long.
- The click-to-startle dash follows the same hill rule (far side of the screen,
  small height change).

## The bubble flight

When the idle cat decides to move, there is a small chance (`BUBBLE_CHANCE`,
default 8%) it goes high instead, provided there is at least ~150 px of room
above it.

Sequence:

1. Stops, looks left and right.
2. Chews with puffed cheeks.
3. Small bubble grows, then pops. Cat looks annoyed.
4. Chews faster. Bubble grows past head size.
5. Lift-off: front paws hold the bubble, hind legs dangle, no ground shadow.
6. Floats up with a gentle side-to-side sway, a few degrees of tilt, tail
   swinging as a rudder, occasional kick, blinking, sometimes a nervous look
   down.
7. At the chosen height the bubble shrinks, the cat pokes it, it pops.
8. Drops about 50 px, lands on all fours, shakes, carries on walking.

Bubble size is picked at random and sets how far it rises:

| Size   | Rise                         |
|--------|------------------------------|
| Small  | about a quarter of the screen |
| Medium | about half the screen         |
| Huge   | almost to the top             |

Rise is always capped so the top of the bubble stays below the top margin.

Rare event in v1: **early pop** (about 3% of flights). The bubble pops halfway,
the cat panics briefly, lands after the same short drop, looks embarrassed.

## Clicking

- Click while floating: the bubble pops, short drop, landing, then the usual
  startled dash.
- Click while chewing: the bubble is abandoned and the cat dashes as today.
- Right-click still quits at any time.

## Approaches considered (how the bubble fits on screen)

The cat's window is a fixed 150×120 and blocks clicks over its whole area. A
bubble bigger than the head does not fit.

1. **Grow the window only during the flight (chosen).** The window becomes
   taller and a bit wider while the bubble is out, with the cat's feet kept in
   the same place, then shrinks back. Blocks extra screen area only for the
   seconds the bubble exists.
2. Permanently larger window. Simplest, but it would block clicks over a much
   bigger invisible area all day.
3. Separate bubble window that follows the cat. Two windows have to stay in
   step, and the paws holding the bubble would cross the gap between them.

Chosen by me, since the owner left the how to me.

## Other decisions (my calls)

- No new sound files in v1; the flight is silent and the cat does not meow
  during it.
- New `--bubble` flag: forces a flight a few seconds after start, for testing,
  like `--demo` does for the break reminder.
- The break-reminder cat is unchanged.
- Everything stays in `deskcat.py`; no new dependencies.

## Not in v1

Double bubble, wind gust, bird encounter, heart-shaped or rainbow bubble,
squeak sound. The flight is built as a list of timed steps so these can be
added later.

## How it will be checked

- Render each new pose to an image and look at it.
- Run with `--bubble` and watch a full flight, including a click mid-flight
  and a flight that starts near the top of the screen.

DeskCat for Windows - one-click start
=====================================

1. Unzip this folder anywhere you like.
2. Double-click run_windows.bat.

That's it. The first time, it installs Python and the cat's graphics
library automatically (needs internet, takes a few minutes). After that,
double-clicking just starts the cat straight away.

- The little white cat wanders around your screen.
- Now and then it blows a gum bubble and floats up the screen with it.
- Every few minutes a food bowl appears and the cat goes to eat.
- After eating it visits a litter box. Sometimes it has an accident on
  your desktop instead: click the poop to clean it up.
- It naps (longer at night), washes, stretches and sometimes gets the
  zoomies. Click it while it sleeps and it wakes up grumpy.
- Click it and it dashes away.
- Every ~25 minutes it pops up big to remind you to take a break.
- Right-click the cat to quit.

If something goes wrong, the black window will say what happened, and
deskcat.log in this folder has more detail.

If it still cannot install the graphics library by itself, open the
Start menu, type cmd, press Enter, and run this once:

    py -m pip install PyQt6

(or  python -m pip install PyQt6  if that says py is not found),
then double-click run_windows.bat again.

Making DeskCat.exe to share with friends
----------------------------------------
Double-click build_windows.bat. After a minute or two the dist folder
opens with DeskCat.exe in it. That single file is all a friend needs:
no Python, no installing, just double-click.

The first time a friend runs it, Windows may show a blue "Windows
protected your PC" box, because the file is not signed by a company.
They click "More info" and then "Run anyway".

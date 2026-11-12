# ⌨️ Cirrus Keyboard

Cirrus is my split wireless keyboard, built from and evolved out of Christian Selig's
[Caldera](https://github.com/christianselig/caldera-keyboard) (MIT license; his original README is below).
Firmware is ZMK **v0.3**, built automatically by GitHub Actions on every push.

- Firmware: `config/` (shield name `cirrus_left` / `cirrus_right`, Bluetooth name "Cirrus")
- PCBs for both halves, ready to order from JLCPCB: `cirrus-pcb/` (the left board adds a status light; see its README)
- Original Caldera design files (Ergogen, KiCad, gerbers): `ergogen/`

### How keys are named in this README

Each half is numbered on its own: **rows 1-5 from the top, columns 1-6 from the left** of that half.
`L` = left half, `R` = right half. Example: **L R3C1** = Caps Lock, **R R3C2** = J.

```
            LEFT HALF                                RIGHT HALF
        C1    C2    C3    C4    C5    C6        C1    C2    C3    C4    C5    C6
  R1   Esc    1     2     3     4     5         6     7     8     9     0    Bksp
  R2   Tab    Q     W     E     R     T         Y     U     I     O     P     '
  R3   Caps   A     S     D     F     G         H     J     K     L     ;    Enter
  R4   Shift  Z     X     C     V     B         N     M     ,     .     /    Shift
  R5   Ctrl  Alt   Win   Home  Thumb Space     Space  Nav   Num   Alt   -    Menu
```
- **L R5C4 "Home"**: turns off any locked layer and returns to normal typing.
- **L R5C5 "Thumb"**: hold = Numpad layer, tap = Layer Lock (applies to the next key only).
- **R R5C2 "Nav"** and **R R5C3 "Num"**: hold for the layer, quick tap to lock it on.

### Updating the firmware

**Step 1: Get the firmware files**
1. On GitHub, open the **Actions** tab and click the latest run with a green check mark.
2. Scroll down to **Artifacts**, download the firmware zip, and unzip it. You'll use:
   - `cirrus_left_studio.uf2` for the left half
   - `cirrus_right-nice_nano_v2-zmk.uf2` for the right half

**Step 2: Flash each half using keys (no reset button needed)**

Only the half you're flashing needs a USB cable. The other half stays wireless.
The left half is the keyboard's "brain": it reads the right half's key presses wirelessly and decides what every key does. So:
- **Flashing the left half:** the left half must be on (the USB cable powers it).
- **Flashing the right half:** the right half is plugged in, **and the left half must be switched on** (on battery, no cable needed). Otherwise nothing hears the right half's flashing key.

1. Plug the half you're flashing into your computer with a USB cable.
2. Tap **L R5C5** (Thumb). This starts Layer Lock.
3. Press **L R4C6** (B). This opens the System layer for **one** action. You have 5 seconds to press the next key before it closes itself.
4. Press the flashing key for the half that's plugged in:
   - **Left half:** **L R1C1** (Esc spot)
   - **Right half:** **R R1C6** (Backspace spot)
5. The half restarts and appears on your computer as a USB drive (named something like `NICENANO`).
6. Drag that half's `.uf2` file onto the drive. It copies, ejects itself, and restarts with the new firmware. Windows may warn that the drive was removed unexpectedly. That's normal.
7. Repeat for the other half.

**When you still need the physical reset button** (double-tap it to get the USB drive):
- The **first time** you flash a firmware that has these flashing keys, since the old firmware doesn't have them.
- After flashing `settings_reset` (it has no keys at all).
- If a half is frozen or the halves won't connect.

**If the halves won't talk to each other after an update**
1. Use the reset button to flash `settings_reset-nice_nano_v2-zmk.uf2` onto **both** halves.
2. Flash the normal left and right files again.
3. Turn both halves on and tap both reset buttons at the same time.
4. Re-pair the keyboard with your computer (settings reset forgets all Bluetooth pairings).

### Changing keys without flashing (ZMK Studio)
1. Plug the **left** half in over USB and open https://zmk.studio in Chrome/Edge (or the desktop app).
2. If the keyboard is also connected over Bluetooth, first send keystrokes over USB: tap **L R5C5** (Thumb), press **L R4C6** (B), then press **R R2C2** (U).
3. Unlock the keyboard: tap **L R5C5** (Thumb), press **L R4C6** (B), then press **L R2C2** (Q).
   (The System layer closes itself after each action, so each one starts with Thumb, B.)
4. To go back to Bluetooth later: Thumb, B, then **L R4C6** (B) again.
5. Edit keys and save. Note that Studio edits are stored on the keyboard and override `config/cirrus.keymap` until you choose "Restore Stock Settings" in Studio.

### Status light (Cirrus left PCB)
A small side light on the left half's inner edge. Most important first:
1. **Short signals** (queued, never cut each other off): blue blinks when switching Bluetooth profile
   (1 blink = profile 1, 2 = profile 2); a 1-second battery check at power-on/wake (green > 50%,
   yellow, red < 15%); low-battery reminders every 30 s while typing (left half: 1 red blink,
   right half: 2 fast red blinks).
2. **Layers**: Layer Lock magenta, System cyan, Nav yellow, Numpad green, HID Test purple.
3. **Caps Lock**: white.
4. **Word-delete mode**: orange.

Otherwise the light's power is switched off. Steady colors also turn off after ~30 s without typing.
Colors and brightness: the `status_led` section at the end of `config/boards/shields/cirrus/cirrus_left.overlay`.
After first flashing firmware with the light, remove and re-pair the keyboard on each computer
(it now asks the computer for the Caps Lock state, which changes how it describes itself).

### Where things are
- `config/cirrus.keymap`: the keymap (layers and what each key does)
- `config/cirrus.conf`: settings for both halves (sleep, Bluetooth power, etc.)
- `config/boards/shields/cirrus/cirrus.dtsi`: wiring (which controller pins are rows/columns)
- `config/boards/shields/cirrus/cirrus-layouts.dtsi`: key positions shown in ZMK Studio
- `build.yaml`: which firmware files GitHub builds
- `keymap-sheet/`: printable picture of every layer. GitHub redraws it on every push: download
  **keymap-sheet** from the same Artifacts list as the firmware. (To redraw it on your own computer:
  `python keymap-sheet/make_keymap_sheet.py`, which needs Python plus Edge or Chrome.)
- `src/`, `dts/bindings/`, `zephyr/`, `CMakeLists.txt`, `Kconfig`: custom firmware code (status light,
  Bluetooth profile toggle). These make the repo a ZMK module, which the GitHub build picks up automatically.

### Pin reference
ZMK uses Pro Micro numbers; Ergogen/KiCad use nice!nano names.

| Pro Micro | nice!nano | Used for |
|---|---|---|
| 2, 3, 4, 5, 6, 7 | P0.17, P0.20, P0.22, P0.24, P1.00, P0.11 | Columns |
| 21, 20, 19, 18, 15 | P0.31, P0.29, P0.02, P1.15, P1.13 | Rows (number row to bottom row) |
| 0 | P0.08 | Status light power on/off (Cirrus left PCB only) |
| 1 | P0.06 | Status light data (Cirrus left PCB only) |
| 8, 9, 10, 14, 16 | P1.04, P1.06, P0.09, P1.11, P0.10 | **Free** (not connected on the PCB) |

---

## Original Caldera README (by Christian Selig)

This repo contains:

- The [Ergogen](https://github.com/ergogen/ergogen) v4 `config.yaml` file
- The outputted PCB files for use in KiCad (both the wired and uncompleted versions) available in the `ergogen` directory
- The left key plate JSCAD file generated by Ergogen (as well as the converted STL version). Note that no right side is included as in Fusion 360 I simply build out the case using the left side and then mirror the case with some modifications
- The ZMK firmware files for Caldera
- The completed case files for 3D printing can be found here: https://makerworld.com/en/models/545431

## Video

A full overview of the build process for this keyboard can be found on YouTube here: https://www.youtube.com/watch?v=7UXsD7nSfDY

[![YouTube video thumbnail for Caldera keyboard](youtube-thumbnail.jpg)](https://www.youtube.com/watch?v=7UXsD7nSfDY)

## Instructions

If you're interested in building a Caldera keyboard, you can use the left and right `gerber.zip` files in this directory and upload those to a PCB manufacturer like JLCPCB or PCBWay (neither are sponsors) to obtain the PCBs. Then it's just a matter of acquiring the other keyboard parts from a site like Typeractive, and following the steps in the video above (soldering, assembling, flashing firmware).

Otherwise hopefully you can use some of these files and instructions as a jumping off point for building your own cool custom keyboard!

# Ergogen config.yaml overview

The Ergogen `config.yaml` file used for this keyboard is expanded upon versus the overview in the YouTube video above, and while there's comments throughout the file to help, I wanted to give a somewhat more substantial overview of how the file works.

## Mirror strategy

One important point is that when building a PCB for split keyboards, many people build a reversible PCB so that the same PCB can be used for both the left and right side, the benefits being you're only maintaining one PCB and when ordering PCBs from manufacturers (which often have a minimum order size of 5), you can just order the 5, rather than using a separate PCB for the left and right side and needing to order 5 of *each*, which can feel excessive.

All that to say, Caldera does *not* use a reversible PCB. 😄 Why? 

- I'm just learning Ergogen and KiCad, making the PCB reversible seemed like it added a lot of complexity that wasn't immediately clear to me, so this feels a bit more beginner friendly
- Since Caldera stashes the controller underneath the actual keys (unlike most keyboards which have it separated in its own area), it was quite challenging to maneuver all the controller pins/holes so they wouldn't run into keys/diodes/etc., making the PCB reversible would have made an already difficult task much more so
- Most of the cost in ordering PCBs is the shipping, so ordering 5 PCBs versus 10 PCBs isn't a big deal, if anything it's just more PCBs to have in case you mess something up somehow

This is accomplished through Ergogen's `mirror_` suffix which allows you to create a mirrored image of a specific component. However both sides of the keyboard still maintain the same controller pin locations, and are simply horizontally mirrored.

## Outlines

There may be simpler ways to define the outlines of the PCB, but I elected to define the points (like the anchor point tool in Figma/Sketch/Illustrator) for more control.

## Component positioning

The Ergogen config uses a lot of custom positioning to allow for the controller to fit underneath the board properly or around mounting holes, which can make routing traces a bit trickier but still totally possible. 

For instance diodes aren't uniformly placed, you can see this in the `config.yaml` where I use regex extensively to apply positioning to only specific diodes, for example whether or not they start with `mirror_` or start with `matrix_`, which dictates which side of the board they're on. I also use regex to target specific rows or columns.

## KiCad

Ergogen outputs PCBs to be wired up in KiCad, which is a relatively simple and honestly kinda fun task. Note that you sometimes end up with `.kicad_proj` files, and you can safely ignore those and just use the `.kicad_pcb` files directly.

One area I didn't touch on in the video was the concept of Vias. Remember, you have two sides of your PCB (in KiCad, the red side, and the blue side), which you can use to your routing advantage. When routing traces in KiCad, sometimes you'll hit a situation where you need to run a trace but another trace is in the way of your path. Sometimes the best way to solve this is to use a Via, which just creates a hole in the PCB to the other side so you can safely route your trace on the other side where there hopefully isn't also something in the way, and if need be, you can Via back to the other side to finish the trace. Very handy, but try not to abuse it too much versus just being smart with your routing (I use it probably a bit more than I should as a beginner, but it's not the end of the world).

A warning you might receive in KiCad when routing the Ergogen schematic is: `Warning: The current configuration does not include the library ''.` From all I can gather, this is just a bug that has no meaningful effect, and you can safely ignore it. There's also a bunch of warnings for `Warning: Silkscreen clipped by solder mask`, this one I don't fully understand (my understanding is the silkscreen is *on top* of the solder mask, so not sure how that's possible), but it's only a warning, not an error, so it's not something I've had any issue ignoring. From what I gather it *might* refer to the silkscreen being cut out by holes in the solder mask/PCB, but again, we're just using the silkscreen as labels, so not to worry if that is the case.

However you do always want to run the Design Rules Checker (DRC aka The Validator) to see if you have any actual errors, and can also help you find which traces are unrouted.

## Cases

I use the handy Ergogen `cases` feature to easily use the key positioning to generate a 3D model file for the plate that the key switches click into, which is much nicer than manually doing everything in CAD software (which I use after Ergogen did a bunch of the heavy lifting). And yeah a 3D printed key plate in PLA is more than strong enough.

## Nothin' fancy

There are changes you could make to this PCB design to make it better, but I did not do:

- Change track width in KiCad. This would give you more resilient, sturdier traces for the electricity to pass through, but I just used the thinner KiCad default. Easier to route and honestly for keyboards and the tiny amount of electricity flowing it really feels negligible, but you can always re-trace the PCB yourself in KiCad with thicker traces!
- Reversible PCB: I did not do this, see *Mirror strategy* for why
- Ground plane: some folks build a ground plane into the PCB rather than requiring wiring directly to a ground pin. I'm not going to lie, I don't 100% understand this, it confused me, and from what I read seemed also negligible for keyboard PCBs, but would be a fun extra thing to learn!


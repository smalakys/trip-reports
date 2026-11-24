---
name: adding-photos
description: Add photos or route topos to a trip report in this repo - copy them into the trip folder, put them in logical order, write Lithuanian captions that end with "(Author, YYYY-MM-DD)", set the cover, and check the pages. Use it whenever the user gives a folder or files of pictures for a report.
---

# Adding photos to a trip report

Real trips live in `reports/<trip>/` (git-ignored). Photos go in `reports/<trip>/photos/`, never anywhere
else in the repository. Read the finished `tajikistan` and `saas-fee` reports' `photos:` lists for the
house style before you start.

## 1. Look at everything first

- List the files, then read the camera data (time, device, front or back camera). Without it you cannot
  order the pictures or say when they were taken:

  ```python
  from PIL import Image
  from pathlib import Path
  for f in sorted(Path("<folder>").iterdir()):
      ex = Image.open(f).getexif()
      print(f.name, Image.open(f).size, ex.get(272), ex.get(306) or ex.get_ifd(0x8769).get(36867))
  ```
- Make a contact sheet (PIL, thumbnails with file names) and **look at it**: the Read tool shows images.
  Captions describe what is in the picture and what the file name says, nothing more.
- Separate route topos (guidebook diagrams, usually photographed pages) from photos of the climb.

## 2. Copy, rename, order

- Copy (do not move) into `photos/` with names that start with the order number and say what the picture
  is: `07-summit-jardin.jpg`; topos `topo-1-couloirs.jpg`. Lower-case `.jpg`. The build rotates by EXIF and
  downsizes, so keep the originals' pixels.
- Order follows the story of the trip: by capture time (EXIF), day by day, approach to descent. A picture
  without camera data goes next to the one it belongs with (same summit, same place); say so in your reply.
- Place a topo where the report describes that part of the route: `route_topos:` lists them in order and
  the report prints them under the table of route sections ("Atskirų techninių atkarpų aprašymas"). A tall
  diagram gets `size: full` (almost a page, like a vertical photo); the default `half` is small, so two
  fit on a page with the text after them.

## 3. Captions: who took it and when

- Format: `"<Lithuanian caption>. (Author Name, YYYY-MM-DD)"`. The author is the person who took the
  picture, the date is the day it was taken (EXIF date, else the day of the event; ask if unknown).
- Authorship is a fact: **never guess it**. Ask the user, unless this trip's earlier answer holds. The
  Aiguille Verte rule given by the user: the report's author took the photo, unless the author is alone
  in it as the subject of a picture someone else must have taken, then the other participant. A selfie
  with both people in it is the author's own (they hold the phone).
- A topo is credited with its source in the same brackets, **without a date**: `(Tibbetts, B. The 4000m
  Peaks of the Alps, Volume I: West)`, the guidebook as in the reference list. It goes on its own line: put
  `\n` before the bracket in the caption.
- Lithuanian: names of peaks, huts, glaciers and passes stay in the original language and spelling
  (check them against the trip text: "Pointe Eveline", not "Evelina"). Every climbing term comes from
  `docs/terminology-lt.md` (skill `lithuanian-terminology`): "šiaurinė siena", "ant keteros", "nusileidimas
  virve". Say which terms you chose that the glossary does not settle.
- Do not name people the user has not named; first names are fine for participants. No invented facts:
  no altitudes, times or places that the user or the track did not give.

## 4. Cover and layout

- The cover is `cover.image`; the picture also stays in the photo section unless the user says otherwise.
- Portrait photos and `size: full` photos get a page each (house rule). Mention the resulting page count
  and offer two portraits per page if it grows long; do not change the layout rule unasked.

## 5. Check

`.venv/bin/tripreport validate reports/<trip>`, then `build reports/<trip> --lang lt --png reports/<trip>/preview --ppi 70`
and **look at the pages**: cover, the route-sections page with the topos, a photo page with the longest
caption (it must not run off the page), the photo order. Then `make test`.

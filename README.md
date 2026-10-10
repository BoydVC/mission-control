# Mission Control — SpaceX · Starship · Starlink wall

A cinematic dark wall dashboard for Boyd (TokenMax; SHORTLIST idea #7). Remastered Sat Oct 10, 2026 for the Saturday daily-usage-check.

**Live:** `./run.sh` → http://127.0.0.1:4245/ (kiosk auto-cycle: `/?kiosk=1`, dwell per scene `&dwell=10`)
**Offline:** `dist/mission-control-snapshot.html` — one self-contained file (CSS, JS, coastline and the saved
data inlined). Open it in any browser; countdowns keep ticking from the saved NETs, and a yellow
"OFFLINE SNAPSHOT · saved …" badge shows when the data was frozen.

## What's on the wall
| Panel | Data | Source |
|---|---|---|
| Next SpaceX launch + On deck | T-minus to the next launches, NET in ET, launch window, pad, vehicle, status (GO/TBC/TBD) | Launch Library 2 (The Space Devs), `launches/upcoming?lsp__id=121` |
| Last launch chip (header) | Most recent SpaceX launch with a T+ clock | LL2 `launches/previous` (seeded read-only from the boyd-wall cache until the LL2 throttle allows our own fetch) |
| Globe | Animated orthographic globe: real pad coordinates (LL2), real day/night terminator from the sun's position, *illustrative* Starlink shells at McDowell inclinations (53°, 43°, 70°, 97°) with rim labels marked ILLUSTRATIVE | LL2 pads · Natural Earth 1:110m land |
| Starlink constellation | In orbit, working, operational orbit, launched, ascent, drift, down; in orbit by generation | Jonathan McDowell, planet4589.org Starlink statistics (table "Data last updated" date shown) |
| Starship status | Next flight (LL2 NET as published) + Jim's latest Flight 15 note with links | LL2 Starship dashboard · Jim's journal |
| Starship flight history | All 14 integrated flights (IFT-1 → Flight 14) + 9 prototype hops, colored by LL2 outcome, + the next flight | LL2 Starship dashboard |
| From Jim's journal | Scrolling cards of the latest SpaceX/Starlink items from `/workspace/ij_*_research.md` (newest first), each linked to its sources (markdown links + bare URLs) | Jim's research files |

Every panel has a `SRC … · fetched <time ET>` line. Nothing is invented:
* Live countdowns are shown **only** when LL2's NET precision is second/minute/hour.
* Coarse NETs are shown exactly as published: `NET Oct 2026`, `NET Q4 2026` with LL2's TBD/TBC badge — never a made-up time.
* If a saved NET passes in the offline snapshot, it flips to T+ and says it's awaiting an LL2 update.

## Kiosk scenes (keys `1`–`7`, `K` toggles auto-cycle, `R` reloads data)
1 overview · 2–4 launch spotlights (globe flies to the pad and draws an ascent arc) · 5 Starship · 6 Starlink · 7 Journal.
A progress bar under the header shows the dwell timer. Spotlight cards for scenes 5–7 summarize Starship / Starlink / journal without inventing figures.

## Files
* `collect.py` — fetches + caches sources (TTL: upcoming 30 min, previous 60 min, Starship 90 min, McDowell 6 h),
  checks the LL2 free-tier throttle first (15 req/h shared with boyd-wall) and keeps the last good cache on errors.
  Writes `data/mission.json`. Raw responses in `data/cache/raw_*`.
* `server.py` — serves `web/` + `/api/mission.json` on :4245 and re-runs the collector every 5 min.
* `web/` — `index.html`, `style.css`, `app.js` (render, countdowns, kiosk), `globe.js` (canvas globe), `land.js`.
* `export_snapshot.py` → `dist/mission-control-snapshot.html`.
* `screenshot.sh NAME W H [query] [url]` → `screenshots/` (headless Chrome). Best overview: `screenshots/00-best-home.png`.
* `tests/smoke_test.py` — re-derives the numbers from the raw fetched files (independently of `collect.py`), then renders
  the live wall **and** the offline snapshot and cross-checks what is displayed: launch order, NET labels in ET, pads,
  Starlink totals, Starship outcomes/colors, last launch, journal titles and links (verbatim from Jim's files),
  source/fetched-at lines, no fake countdowns for coarse NETs, no external dependencies in the snapshot.

```
./run.sh                       # start/restart (nohup) on :4245
python3 tests/smoke_test.py    # 80+ checks
python3 export_snapshot.py     # refresh the offline file
```

Read-only: only public GETs; writes only inside this folder (boyd-wall's cache is read, never modified).


---
## Repo notes
- **Built:** Oct 10, 2026, by TokenMax (Boyd's Grok Bot) on the Grok Bot box.
- **Run:** `./run.sh` (then open the localhost URL it prints).
- Imported from `/workspace/tokenmax/mission-control` on Oct 23, 2026. node_modules, virtualenvs, logs and files over 20 MB were left out.

# Data privacy and page performance

## Privacy (ISEF items 30, 199, 208)

**What is stored.** A reading carries the device code, the value, QC and versions; optionally a parent sample ID,
electrode lot and `SampleMeta` (source kind, depth, purge time, bottle ID, preservation, collector *initials*,
custody note). A device may have a site: name, village, district, state, latitude/longitude. No household names,
phone numbers or photographs are stored by the platform; alert contacts entered on the dashboard stay in that
browser's local storage, not on the server.

**Who can see what.**

| Surface | Coordinates | Readings | Who |
|---|---|---|---|
| Dashboard (`index.html`) | exact, on the map | all | the pilot team on the local network (read protection: `READ_PROTECT`, sign-in in v5.6) |
| Public QR page (`/api/public/devices/{code}`) | **none** | latest outcome only | anyone with the sticker |
| Paired export (`/api/data/export/paired`) | **rounded to 3 decimals (~100 m)** unless `precise_coordinates=true` | real readings | whoever receives the file |
| JJM export | as the government format requires | real readings | district lab |
| Raw export (`/api/data/export`) | exact unless `redact_coordinates=true` | all | admin |

Before anything is published (poster, dataset DOI), round or withhold the coordinates of private wells and keep the
collector field to initials. `PUBLIC_COORD_DECIMALS` sets the rounding (default 3).

**Retention.** Data stays in the pilot's SQLite file; backups via `/api/admin/backup`. Decide with the district
authority who owns the data after the project (item 209).

## Page performance (item 197)

Measured on 8 Nov 2026 with headless Chromium emulating a 360 × 740 phone, CPU slowed 4×, first visit (nothing cached):

| Network | Page load | Verdict visible | Transfer | Requests |
|---|---|---|---|---|
| Regular 3G (750 kb/s, 100 ms RTT) | 6.1 s | 6.4 s | 519 kB | 25 |
| Slow 3G (400 kb/s, 400 ms RTT) | 11.7 s | 11.9 s | 519 kB | 25 |

After the first visit the service worker caches every file, so later loads do not depend on the network. The
largest items are the Leaflet map library and the fonts; the 3D viewer is lazy-loaded. Measure once on a real cheap
Android phone and replace this table with that number (the headless figure is a stand-in, not a claim).

# Draft thread (quote-tweet https://x.com/celestepoasts/status/2103232383139057950)

**1/** — `1_everest.png`
I extended "blind Claudes see the Earth" to altitude.

Claude was asked for the elevation of 2,576 points around Everest, given only as text coordinates, 1 km apart. No images, no tools, no internet.

Left: real satellite data. Right: Fable 5.1 from memory.

**2/** — `2_globe.png`
Same 2° globe as the original, but every point it calls land also gets a height.

Opus 5.5: 98.2% land/water, ±175 m elevation error.
All four get the Tibetan plateau, the Andes and the Greenland and Antarctic ice domes.
Haiku 4.5's stripes are what happens when one row of 180 points is asked at once.

**3/** — `3_range_himalaya.png`, `3_range_alps.png`, `3_range_andes.png`, `3_range_southern_alps.png`
Then one famous range per continent, one guess every 5 km.

Opus 5.5 gets the shape right everywhere: the Himalayan wall above the Ganges plain, the Alps curving round the Po valley, the Andes falling into the Pacific, New Zealand's coastline.

**4/** — `4_ranges_grid.png`
All seven side by side. ▲ marks the famous peaks.

The models usually put their highest point within a few km of Everest, Aconcagua, Toubkal, Aoraki/Mt Cook and Vinson.

**5/** — `5_scoreboard.png`
How much do they really know? Blur the real terrain until it's as wrong as the model.

Best case is ~30 km (the Alps); most ranges come out at 60–90 km. Below that, the ridges are invented, and smoothing the models' own answers makes them more accurate.

**6/** — `6_method.png`
How it works, plus the audit: 1,825 calls, 0 web searches, every call a single model turn, an empty tool list in the sandbox. 75–85% of answers are round to 50 m, which is memory, not lookup.

Code, raw answers and an interactive 3D viewer: github.com/andre15silva/geobench

---

Spare images: `3_range_rockies.png`, `3_range_atlas.png`, `3_range_ellsworth.png`.
X allows up to 4 images per post; all images are 2400×1350 (16:9) except the 4:5 ranges grid.

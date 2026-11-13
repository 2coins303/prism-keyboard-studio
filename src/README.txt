Prism Keyboard Studio 2.5 source

Run build.ps1 at the project root with Python 3.13 on Windows to fetch verified dependencies, run the checks, and rebuild the portable Windows ZIP. This source-folder build.ps1 forwards to that entry point. Keep the supplied bridge folder adjacent to the app. See the root README.md for development and build commands.

The bridge uses official unmodified OpenRGB 1.1 binaries, with all PawnIO .bin modules omitted. scripts/fetch_bridge.py downloads the checksum-pinned bridge and complete corresponding source archive. The archive is excluded from Git and included with each portable release; release metadata is checked in here.

The compatibility JSON is editable source data. rebuild_catalog.py documents its generation from the upstream tree and portable archive in the original work layout; it is not needed for normal app rebuilding.

The runtime bridge-manifest.json in _internal is editable to allow replacing the helper or compatible LGPL libraries. Recompute SHA256 entries for intentionally changed files; keep .bin payload modules absent.

For isolated checks, --check-package REPORT.json validates the UI, profiles, audio enumeration and a read-only direct keyboard query. --check-bridge REPORT.json --check-discovery validates real managed setup and enumeration. Omitting --check-discovery also sends live lighting/audio frames to the connected 1532:02A6; close other controllers first.

Version 2.1 adds 24 deterministic spatial effects in patterns.py and the searchable
pattern_browser.py gallery (31 patterns total, with 11 additional theme palettes).
The original seven effect identifiers and profile format are retained.

--check-patterns REPORT.json checks every pattern, profile export/save, the gallery,
palette retention and undo/redo in an isolated offscreen window. It saves preview
images next to the report. It does not connect to a keyboard or send USB frames.
test_patterns.py additionally covers full-size/TKL/compact/zonal layouts, physical
coordinate invariance, unmapped lights, brightness bounds and static-only devices.

Version 2.2 exposes keyboard brightness in a fixed footer on every editing tab and
inside the pattern browser. brightness_control.py shares the synchronized slider
and numeric percentage field. The existing per-profile 0-100 brightness field
continues to scale all output LEDs, including Audio and painted colors.

43 automated checks now pass, including all-pattern/all-layout brightness scaling,
zero-output frames, typed percentage entry, gallery thumbnail dimming, settings
retention, static-only devices and the live frame submission path with a fake
worker. --check-patterns additionally verifies the packaged brightness controls,
all-off frames and gallery rendering in an offscreen window without hardware.

Version 2.3 opens to an embedded Presets screen with preview cards and the four
original color shortcuts. Selecting a preset opens Customize. Sidebar navigation
separates built-in presets from saved looks; less-used profile actions are under
More. Brightness, Apply, and the keyboard selector remain outside page scrolling.
The gallery adapts between two and three columns at supported window sizes.

45 automated checks pass. test_navigation.py exercises launch, actual preset and
color buttons, returning to presets, selecting the current saved look, Escape
handling, persistence, compact layout and static-only keyboard capabilities.
The packaged --check-patterns report includes this navigation and screenshots.

Version 2.3.1 fixes clipped button labels when resizing. The explicit 278-pixel
tab minimum overrode Qt's content-derived 319-pixel minimum and compressed the
Paint buttons to 25 pixels (only 5 pixels left for 17-pixel text). Removing that
override lets the outer scroll area preserve full control sizes.

46 automated checks now pass. test_resize.py verifies actual styled text rectangles
across 18 resize/tab cases. --check-resize REPORT.json checks the frozen app with
isolated temporary profiles and no hardware access. Use QT_SCALE_FACTOR to repeat
at other display scales. Verification includes 100%, 125%, 150%, and 200%.

Version 2.4 extends animation speed to 1000%. model.animation_rate preserves the
original .12 + speed/45 mapping at 0-100 and extends values above 100 relative to
the former maximum, so 1000 is exactly ten times that maximum. Speed edits rescale
the elapsed animation phase to avoid a visual jump. Device refresh rates are
unchanged. SpeedControl supplies the slider, numeric entry and four quick values.

50 automated checks pass. speed-baselines.json contains 93 frames recorded from
2.3.1 at 0, 45 and 100 for all 31 patterns. Tests verify these remain byte-identical,
all 26 animations match ten-times playback at the maximum, high-speed validation,
draft/save/import round trips, numeric input, quick buttons and phase continuity.
--check-speed REPORT.json checks the frozen app with isolated temporary profiles
and no hardware access. Values above 100 require Prism 2.4 or later.

Version 2.5 simplifies the visible copy in Presets, Customize, Paint, Audio,
keyboard setup and Help. Buttons, tabs and color swatches have larger rounded
shapes and clearer filled backgrounds. Pattern descriptions and extra guidance
are available through tooltips and Help. Normal footer status is a single line;
connection errors and manual-Apply requirements remain visible. Audio uses the
main page's natural layout and scroll area, avoiding nested scrolling.

All 50 existing automated checks pass, including speed, profiles, navigation,
brightness and resize regression. --check-resize renders all main pages and
checks button text after 18 tab/window changes, with no keyboard access.
Animation timing, hardware refresh rates, pattern recipes, audio analysis,
keyboard transport and profile formats are unchanged from version 2.4.

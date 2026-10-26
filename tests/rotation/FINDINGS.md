# Issue #99 — root cause, fix and verification record

Status: fixed and verified on Hyprland 0.56.0 (commit
`a1c2428f79b3b05c3fd36c27378e3538c8c6a014`), 2026-10-26. This file records what
was tested, what was not, and what was found but deliberately left out of this
branch. It is a test record, not a specification.

## Environment

- Outputs: one 1920x1080 panel at `transform = 1` (logical 1080x1920) and two
  landscape 1920x1080 panels at `transform = 0`, all `scale = 1` unless noted.
- Plugin built against the exact running Hyprland revision, then hot-loaded.
- Test wallpaper: eight horizontal colour bands with row numbers, a white
  vertical bar at 20% of the width and a black bar at 70%. Neutral glass preset
  (no blur/refraction/noise/tint, opacity 1) with brightness 1 vs 0.5 pairs.
- Coverage is `sum(dim)/sum(bright)` at points inside the glass; alignment
  compares normalised RGB against an uncovered column of the same band.

## Root cause

Hyprland 0.56 renders the scene into a work buffer sized to
`monitor->m_transformedSize`, with an identity `RPT_MONITOR` projection and
render damage already in that monitor-oriented space. The output transform is
applied only when the finished frame is copied to the output framebuffer
(`RPT_OUTPUT`, viewport `m_pixelSize`, `transformDamage = true`).

The plugin still converted window, layer and item boxes to the output's native
orientation: it inverse-rotated sample rectangles, blur regions and damage
tests, passed an inverse transform to `projectBoxToTarget`, and called
`scissor` with the default `transform = true`. On 90/270-degree outputs this
scissored the glass to the output's native 1920x1080 rectangle and sampled the
wallpaper sideways.

Relevant Hyprland code: `src/render/OpenGL.cpp` `begin()` / `end()` and
`scissor()`, `src/render/Renderer.cpp` `setProjectionType()`,
`projectBoxToTarget()` and `getWorkBuffer()`.

## Fix

All pixel geometry stays in monitor-oriented work-buffer space; the output
transform is applied after the scene is drawn. The change covers windows,
layers, snapshots/x-ray and subsurface items, passes
`ctx.m_data.transformDamage` to `scissor`, removes the obsolete transform
helpers and the duplicate `applyGlassEffect` box, and keys the layer cache by
monitor as well as scene generation.

Commits on `fix/rotated-monitor`: `362dc45` (fix), `622c5ca` (this test
procedure and checker), `ec9d306` (layer cache monitor identity), `05ae111`
(remove duplicate box, correct stale documentation).

This targets the monitor-oriented pipeline on `main`/hyprland-git. Release
branches that still render into native-orientation framebuffers must not take
these coordinate changes without checking their own pipeline.

## Verification record

All results below are from real `grim` captures of the running compositor, not
synthetic images.

| Case | Result |
| --- | --- |
| Window, transforms 0–7 | 8/8 coverage points per transform, ratio 0.49–0.51, alignment error ≤ 0.002, screenshot dimensions match the transform's logical size |
| Window, transform 1, before fix | rows at y ≥ 1080 had ratio 1.0 (no glass); wallpaper labels were rotated 90° |
| Window, transform 1, after fix | all eight rows dim to 0.50; rows and labels upright and continuous through the glass |
| Cache on and off, including a runtime 1→3 change with cache on | aligned; no stale sample (the work buffer is logical-space, so same-size transform changes need no invalidation) |
| X-ray, window behind glass at y=400 and y=1200 | hidden window visible upright through the glass, wallpaper aligned around it; covers below the old 1080 cut |
| Self-sample + blur + refraction + chromatic aberration + frost, transform 1 | upright, full height, `blur_pass` counter rises |
| Layer glass, alpha mask, portrait below y=1080 and landscape | coverage and alignment pass |
| Layer glass, `mask_mode = contour`, `mask_threshold = 0.10` | `contour_build` rises; content and border aligned on both outputs |
| Scale 1.25 + transform 1 | coverage and alignment pass; wallpaper text continuous across the glass |
| Portrait and landscape glass simultaneously | independent samples; both pass |
| Idle 15 s with cache on | no deferral or miss growth; cache hits only |
| Rapid behind-window moves, then window resize 700x1200 / 950x1800 | no stale blocks or artifacts; neutral alignment ≤ 0.0016 afterwards |
| Plugin unload and reload | clean; status active, shaders ready, version check match |
| Subsurface item | see below |

### Subsurface item test

A throwaway Wayland client mapped a 400x300 translucent toplevel with a 240x64
`wl_subsurface` carrying a partial 200x48 blur region and an explicit
`hyprglass_item_v1` shape of 196x44 with four different corner radii
(TL/TR/BR/BL = 2/8/16/24). On transforms 1 and 3:

- `hyprctl hyprglass items` reported the hint unchanged:
  `10,10 196x44  radii 2,8,16,24`, and last drawn
  `610,410 196x44  radii 2,8,16,24` in physical pixels.
- The screenshot showed TL sharp (2), TR 8, BR 16, BL most rounded (24), with
  glass only inside the blur region. The old radii permutation would have put
  the largest radius at TL on a 90-degree output.
- `sub_draws`/`sub_hit` counters rose; the item appeared with the default
  `skip_opaque_windows = 1` (the parent window was genuinely translucent).

## Not covered

- Physical mirror scanout for `FLIPPED*` transforms. Captures are logical-space
  views; the plugin now draws entirely before Hyprland's final output blit, so
  mirroring is the compositor's responsibility.
- Lock screen and screen-share/foreign-render contexts.
- Layer surfaces migrating between outputs (the monitor-id cache guard is
  logical and was reviewed, but not exercised live).
- Shipped applications' subsurface items. The synthetic client exercises the
  protocol, the partial region and the four radii, but not a real toolkit.
- Long-run performance and GPU memory. Only correctness counters were checked.

## Pre-existing findings (out of scope)

Found while reviewing, not caused by this change and not fixed here:

- Subsurface deferral damages the whole monitor instead of the item's sample
  box (`src/GlassSubsurfaceState.cpp`, uncovered-sample branch).
- The shared blur ping-pong framebuffer is reallocated whenever callers differ
  in size (`src/GlassRenderer.cpp`, `blurBackground`).
- Several `alloc()` results are ignored before `getTexture()->...` use
  (`src/GlassRenderer.cpp`, `src/GlassLayerSurface.cpp`,
  `src/GlassSubsurfaceState.cpp`); allocation failure would crash rather than
  skip the frame.
- `sampleMapFor()`'s source rectangle and padded-size arithmetic only agree for
  integral boxes (all current callers round; the invariant is undocumented).
- `sceneGeneration` entries are not erased when a monitor is removed
  (`src/main.cpp`), unlike the other per-monitor maps.

## Reproduction hazards

- Changing the portrait output to an even transform widens its logical size to
  1920 while the neighbouring landscape output may sit at x=1080. Hyprland then
  reports overlapping monitor geometry and can leave outputs unhappy. Park the
  other outputs further right for the sweep and restore them afterwards.
- `hyprctl clients -j` reports `at` in global layout coordinates. On a monitor
  not at (0,0), subtract the monitor position before using it as a
  screenshot-local position.
- `hyprctl reload` resets the plugin's runtime config and any runtime
  `hl.plugin.hyprglass.layer(...)` rule; re-apply them after reloading.
- Item glass requires the parent window's own glass. An intentionally opaque
  window with the default `skip_opaque_windows = 1` will not register items;
  that is expected behaviour, not a missing item.

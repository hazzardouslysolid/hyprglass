# Rotated-output regression (issue #99)

This is a live compositor test for the `main` branch's monitor-oriented render
pipeline. Build against the exact running Hyprland revision before loading the
plugin. Do not apply the coordinate changes to older release branches without
checking their framebuffer/projection conventions.

## Reproduction

1. Use a non-square output, e.g. native 1920×1080 with transform 1, giving a
   1080×1920 monitor-oriented scene. Keep a landscape output as a control.
2. Display an asymmetric wallpaper: eight differently coloured horizontal bands,
   readable row numbers, and vertical markers at 20% and 70% of the width.
3. Place a mostly transparent, blank window across both halves of the portrait
   screen. Use a neutral glass configuration: no blur, refraction, noise,
   chromatic aberration, fresnel, specular, bevel, lens distortion, tint, frost,
   adaptive dimming or colour adjustments. Set glass opacity to 1, brightness,
   contrast and saturation to 1. Clear `default_preset` so a preset does not
   override these global controls. Start with background caching disabled.
4. Capture the output at brightness 1 and 0.5, allowing the display to settle
   after each change. In Lua configurations the runtime control is:

   ```sh
   hyprctl eval 'hl.plugin.hyprglass.config({brightness=0.5})'
   grim -o HDMI-A-1 dim.png
   ```

5. Check that labels and band boundaries continue in the same orientation and
   position through the glass. Then use the pixel checker on points inside the
   window, away from text, borders and overlapping panels:

   ```sh
   python -m venv /tmp/hyprglass-rotation-check
   /tmp/hyprglass-rotation-check/bin/pip install Pillow
   /tmp/hyprglass-rotation-check/bin/python tests/rotation/check-coverage.py \
     bright.png dim.png --x 100 --ys 180 360 600 840 1080 1320 1560 1700
   ```

   Coordinates are examples: adapt them to the actual window geometry. The
   checker exits non-zero if any sampled row fails to dim. A neutral screenshot
   alone cannot prove full coverage: missing glass looks like correct
   transparency. Also inspect alignment; the checker is a coverage test only.

## Regression matrix

- Transforms 0–7: no extra rotation/mirror of the sampled background, complete
  window coverage and correct rounded corners.
- Cache enabled and disabled; live resampling; move and resize the window;
  damage only a small wallpaper rectangle. No stale blocks or sample deferrals
  that persist indefinitely (`hyprctl hyprglass stats`).
- X-ray enabled: wallpaper remains aligned, including below native output height;
  moving another window behind the glass does not enter the x-ray sample.
- Layer glass: a translucent layer below y=1080 on the portrait scene, then
  near every edge. Check content/alpha masks, explicit shape and contour modes.
- Subsurface item glass where a client is available: a partial blur region and
  four different corner radii must stay aligned with the surface's corners.
- Blur/downsampling, refraction and self-sampling: enable individually after the
  neutral comparison. Keep the landscape output as a control.
- Restore the user's monitor transform, effects, wallpaper and workspaces.

Record which cases actually ran; do not treat this checklist as a test result.

The results of the initial verification, the cases that were not covered and the
pre-existing findings left out of this change are recorded in
[FINDINGS.md](FINDINGS.md).

"""Check that a neutral glass brightness change reaches every sampled row.

Inputs are real compositor captures with identical geometry, brightness 1 vs 0.5.
This reads pixels only. Keep sample points inside glass and away from text/borders.
"""
import argparse
import json
from PIL import Image

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('bright')
p.add_argument('dim')
p.add_argument('--x', type=int, required=True)
p.add_argument('--ys', type=int, nargs='+', required=True)
p.add_argument('--background-x', type=int, help='Optional uncovered column of the same horizontal-band wallpaper')
a = p.parse_args()
bright, dim = (Image.open(path).convert('RGB') for path in (a.bright, a.dim))
assert bright.size == dim.size, 'capture dimensions changed'
results = []
for y in a.ys:
    b, d = bright.getpixel((a.x, y)), dim.getpixel((a.x, y))
    ratio = sum(d) / max(1, sum(b))
    result = dict(x=a.x, y=y, bright=b, dim=d, ratio=round(ratio, 4), passed=0.40 <= ratio <= 0.65)
    if a.background_x is not None:
        reference = bright.getpixel((a.background_x, y))
        error = max(abs(b[i] / max(1, sum(b)) - reference[i] / max(1, sum(reference))) for i in range(3))
        result.update(alignment_error=round(error, 4), passed=result['passed'] and error < 0.025)
    results.append(result)
print(json.dumps(results, indent=2))
raise SystemExit(0 if all(r['passed'] for r in results) else 1)

// Continuous structural color scale shared by the 3D result overlays and the
// on-canvas legend. A green -> yellow -> orange -> red ramp reads naturally as
// "safe -> critical" and matches common FEA tools.

const STOPS = [
  { t: 0.0, c: [34, 197, 94] },    // green  #22c55e
  { t: 0.4, c: [163, 230, 53] },   // lime   #a3e635
  { t: 0.6, c: [234, 179, 8] },    // yellow #eab308
  { t: 0.8, c: [249, 115, 22] },   // orange #f97316
  { t: 1.0, c: [239, 68, 68] },    // red    #ef4444
];

function lerp(a, b, t) {
  return a + (b - a) * t;
}

// ratio in [0, 1] -> [r, g, b] (0-255)
export function colorForRatio(ratio) {
  const r = Math.max(0, Math.min(1, ratio));
  for (let i = 0; i < STOPS.length - 1; i += 1) {
    const a = STOPS[i];
    const b = STOPS[i + 1];
    if (r >= a.t && r <= b.t) {
      const local = (r - a.t) / (b.t - a.t);
      return [
        Math.round(lerp(a.c[0], b.c[0], local)),
        Math.round(lerp(a.c[1], b.c[1], local)),
        Math.round(lerp(a.c[2], b.c[2], local)),
      ];
    }
  }
  return STOPS[STOPS.length - 1].c;
}

export function colorForRatioHex(ratio) {
  const [r, g, b] = colorForRatio(ratio);
  return (r << 16) | (g << 8) | b;
}

export function colorForRatioCss(ratio) {
  const [r, g, b] = colorForRatio(ratio);
  return `rgb(${r}, ${g}, ${b})`;
}

// CSS linear-gradient string for the legend bar.
export function legendGradientCss() {
  const parts = STOPS.map((s) => `rgb(${s.c[0]}, ${s.c[1]}, ${s.c[2]}) ${Math.round(s.t * 100)}%`);
  return `linear-gradient(to right, ${parts.join(', ')})`;
}

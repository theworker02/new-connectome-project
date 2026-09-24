/** Build a tiny XY silhouette path from skeleton line segments (client-side). */

export function silhouetteFromSegments(segments: number[], size = 96): string {
  if (!segments.length) return emptySilhouette(size);
  let minX = Infinity,
    minY = Infinity,
    maxX = -Infinity,
    maxY = -Infinity;
  for (let i = 0; i + 5 < segments.length; i += 6) {
    const xs = [segments[i], segments[i + 3]];
    const ys = [segments[i + 1], segments[i + 4]];
    for (const x of xs) {
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
    }
    for (const y of ys) {
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
    }
  }
  const span = Math.max(maxX - minX, maxY - minY, 1);
  const pad = 0.08;
  const scale = ((1 - 2 * pad) * size) / span;
  const midX = (minX + maxX) / 2;
  const midY = (minY + maxY) / 2;
  const o = size / 2;
  const tx = (x: number, y: number) => [o + (x - midX) * scale, o - (y - midY) * scale] as const;

  const step = Math.max(6, Math.floor(segments.length / 2400) * 6);
  const lines: string[] = [];
  for (let i = 0; i + 5 < segments.length; i += step) {
    const [x1, y1] = tx(segments[i], segments[i + 1]);
    const [x2, y2] = tx(segments[i + 3], segments[i + 4]);
    lines.push(`<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" />`);
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" class="sil-svg">${lines.join("")}</svg>`;
}

function emptySilhouette(size: number) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" class="sil-svg"><circle cx="${size / 2}" cy="${size / 2}" r="5" fill="#24352e"/></svg>`;
}

export function typeHue(cellType: string | undefined | null): string {
  const s = String(cellType || "unknown");
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  const hue = h % 360;
  return `hsl(${hue} 42% 55%)`;
}

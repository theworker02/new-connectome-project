import React, { useMemo } from "react";

type Edge = { pre: number; post: number; weight: number; direction: "in" | "out" };

type Props = {
  selectedId: number | null;
  upstream: Record<string, unknown>[];
  downstream: Record<string, unknown>[];
  onSelect: (id: number) => void;
};

export function GraphPanel({ selectedId, upstream, downstream, onSelect }: Props) {
  const edges: Edge[] = useMemo(() => {
    const out: Edge[] = [];
    for (const row of upstream) {
      out.push({
        pre: Number(row.pre_neuron_id),
        post: selectedId ?? 0,
        weight: Number(row.synapse_count ?? 1),
        direction: "in",
      });
    }
    for (const row of downstream) {
      out.push({
        pre: selectedId ?? 0,
        post: Number(row.post_neuron_id),
        weight: Number(row.synapse_count ?? 1),
        direction: "out",
      });
    }
    return out.slice(0, 48);
  }, [upstream, downstream, selectedId]);

  if (selectedId == null) {
    return <p className="muted">Select a neuron to open the local connectivity graph.</p>;
  }

  const maxW = Math.max(1, ...edges.map((e) => e.weight));
  const cx = 220;
  const cy = 130;
  const r = 95;

  const nodes = new Map<number, { x: number; y: number; kind: string }>();
  nodes.set(selectedId, { x: cx, y: cy, kind: "sel" });
  const partners = edges.map((e) => (e.direction === "in" ? e.pre : e.post));
  const uniq = [...new Set(partners)];
  uniq.forEach((id, i) => {
    const a = (i / Math.max(1, uniq.length)) * Math.PI * 2 - Math.PI / 2;
    nodes.set(id, {
      x: cx + Math.cos(a) * r,
      y: cy + Math.sin(a) * (r * 0.72),
      kind: upstream.some((u) => Number(u.pre_neuron_id) === id) ? "up" : "down",
    });
  });

  return (
    <div className="graph-wrap">
      <svg viewBox="0 0 440 260" className="graph-svg">
        {edges.map((e, i) => {
          const a = nodes.get(e.pre);
          const b = nodes.get(e.post);
          if (!a || !b) return null;
          const w = 0.6 + (e.weight / maxW) * 3.2;
          return (
            <line
              key={i}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={e.direction === "in" ? "#5ec8ff" : "#ff9a4a"}
              strokeWidth={w}
              strokeOpacity={0.55}
            />
          );
        })}
        {[...nodes.entries()].map(([id, p]) => (
          <g key={id} onClick={() => onSelect(id)} style={{ cursor: "pointer" }}>
            <circle
              cx={p.x}
              cy={p.y}
              r={p.kind === "sel" ? 11 : 7}
              fill={p.kind === "sel" ? "#ffe8b0" : p.kind === "up" ? "#5ec8ff" : "#ff9a4a"}
            />
            <text x={p.x} y={p.y - 14} textAnchor="middle" fill="#c5d4cb" fontSize="9" fontFamily="IBM Plex Mono, monospace">
              {id}
            </text>
          </g>
        ))}
      </svg>
      <div className="graph-legend">
        <span className="lg up">upstream</span>
        <span className="lg down">downstream</span>
        <span className="lg sel">selected</span>
      </div>
    </div>
  );
}

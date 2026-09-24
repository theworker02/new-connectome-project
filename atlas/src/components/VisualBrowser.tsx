import React, { useEffect, useMemo, useRef, useState } from "react";
import type { NeuronIndexRow, SkeletonBatch } from "../api";
import { describeNeuron } from "../neuronRoles";
import { silhouetteFromSegments, typeHue } from "../silhouette";

type Mode = "gallery" | "map";

type Props = {
  neurons: NeuronIndexRow[];
  batch: SkeletonBatch | null;
  selectedId: number | null;
  upstream?: Set<number>;
  downstream?: Set<number>;
  onSelect: (id: number) => void;
  skOnly: boolean;
  onSkOnly: (v: boolean) => void;
  q: string;
  onQ: (v: string) => void;
  total: number;
  loading?: boolean;
  packKey?: string;
  onLoadMore?: () => void;
  loadingMore?: boolean;
  canLoadMore?: boolean;
};

function shortLabel(n: NeuronIndexRow) {
  const role = describeNeuron({
    cellType: n.cell_type,
    name: n.name,
    degreeIn: n.degree_in,
    degreeOut: n.degree_out,
    hasSkeleton: n.has_skeleton,
  });
  const raw = String(n.name || n.cell_type || `Neuron ${n.source_id}`);
  const side = raw.match(/_([LR]\d+)\b/)?.[1] || raw.match(/\b([LR]\d+)\b/)?.[1];
  const type = n.cell_type || raw.split(/[(_]/)[0] || "Neuron";
  const title = side ? `${type} · ${side}` : type;
  const system = role.system.split("·").map((s) => s.trim());
  return {
    title,
    subtitle: system[1] || system[0] || "cell class",
  };
}

export function VisualBrowser({
  neurons,
  batch,
  selectedId,
  upstream,
  downstream,
  onSelect,
  skOnly,
  onSkOnly,
  q,
  onQ,
  total,
  loading,
  packKey,
  onLoadMore,
  loadingMore,
  canLoadMore,
}: Props) {
  const [mode, setMode] = useState<Mode>("gallery");
  const [openTypes, setOpenTypes] = useState<Record<string, boolean>>({});
  const openedOnce = useRef(false);
  const selectedRef = useRef<HTMLButtonElement | null>(null);

  const silMap = useMemo(() => {
    const m = new Map<number, string>();
    for (const n of batch?.neurons || []) {
      if (n.line_segments?.length) m.set(n.source_id, silhouetteFromSegments(n.line_segments, 88));
    }
    return m;
  }, [batch]);

  const filtered = useMemo(() => {
    let rows = neurons;
    if (skOnly) rows = rows.filter((n) => n.has_skeleton);
    return rows;
  }, [neurons, skOnly]);

  const groups = useMemo(() => {
    const g = new Map<string, NeuronIndexRow[]>();
    for (const n of filtered) {
      const key = String(n.cell_type || "untyped");
      if (!g.has(key)) g.set(key, []);
      g.get(key)!.push(n);
    }
    return [...g.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [filtered]);

  useEffect(() => {
    openedOnce.current = false;
    setOpenTypes({});
  }, [packKey]);

  useEffect(() => {
    if (openedOnce.current || !groups.length) return;
    openedOnce.current = true;
    const init: Record<string, boolean> = {};
    groups.slice(0, 4).forEach(([k]) => {
      init[k] = true;
    });
    if (selectedId != null) {
      const row = neurons.find((n) => n.source_id === selectedId);
      if (row?.cell_type) init[String(row.cell_type)] = true;
    }
    setOpenTypes(init);
  }, [groups, selectedId, neurons]);

  useEffect(() => {
    if (selectedId == null) return;
    const row = neurons.find((n) => n.source_id === selectedId);
    if (row?.cell_type) {
      setOpenTypes((s) => ({ ...s, [String(row.cell_type)]: true }));
    }
    selectedRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedId, neurons]);

  const flatIds = useMemo(() => filtered.map((n) => n.source_id), [filtered]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (!flatIds.length) return;
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft" && e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      e.preventDefault();
      const idx = selectedId == null ? -1 : flatIds.indexOf(selectedId);
      const step = e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 1;
      const next = flatIds[Math.max(0, Math.min(flatIds.length - 1, idx + step))] ?? flatIds[0];
      onSelect(next);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [flatIds, selectedId, onSelect]);

  const mapBounds = useMemo(() => {
    const withSoma = filtered.filter((n) => n.soma_x != null && n.soma_y != null);
    if (!withSoma.length) return null;
    let minX = Infinity,
      minY = Infinity,
      maxX = -Infinity,
      maxY = -Infinity;
    for (const n of withSoma) {
      minX = Math.min(minX, n.soma_x!);
      maxX = Math.max(maxX, n.soma_x!);
      minY = Math.min(minY, n.soma_y!);
      maxY = Math.max(maxY, n.soma_y!);
    }
    return { minX, minY, maxX, maxY, rows: withSoma };
  }, [filtered]);

  return (
    <div className="visual-browser">
      <div className="vb-toolbar">
        <input
          className="search"
          placeholder="Filter by type or name"
          value={q}
          onChange={(e) => onQ(e.target.value)}
        />
        <div className="toolbar tight">
          <button type="button" className={mode === "gallery" ? "active" : ""} onClick={() => setMode("gallery")}>
            Gallery
          </button>
          <button type="button" className={mode === "map" ? "active" : ""} onClick={() => setMode("map")}>
            Map
          </button>
          <button type="button" className={skOnly ? "active" : ""} onClick={() => onSkOnly(!skOnly)}>
            3D only
          </button>
        </div>
        <div className="vb-meta">
          {loading ? "Loading catalog…" : `${filtered.length} shown · ${total.toLocaleString()} in pack`}
          <span className="vb-keys">← → keys</span>
        </div>
      </div>

      {mode === "gallery" && (
        <div className="vb-gallery">
          {loading && !groups.length && (
            <div className="vb-skeleton-grid">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="vb-skel-card" />
              ))}
            </div>
          )}
          {groups.map(([type, rows]) => {
            const open = openTypes[type] ?? rows.length <= 12;
            const role = describeNeuron({ cellType: type });
            return (
              <section key={type} className="vb-type">
                <button
                  type="button"
                  className="vb-type-head"
                  onClick={() => setOpenTypes((s) => ({ ...s, [type]: !open }))}
                >
                  <span className="vb-swatch" style={{ background: typeHue(type) }} />
                  <span className="vb-type-name">{type}</span>
                  <span className="count-tag">{rows.length}</span>
                  <span className="vb-caret">{open ? "▾" : "▸"}</span>
                  <span className="vb-type-role">{role.system}</span>
                </button>
                {open && (
                  <div className="vb-grid">
                    {rows.slice(0, 64).map((n) => {
                      const labels = shortLabel(n);
                      const sil = silMap.get(n.source_id);
                      const selected = selectedId === n.source_id;
                      const related =
                        selectedId != null &&
                        selectedId !== n.source_id &&
                        (upstream?.has(n.source_id) || downstream?.has(n.source_id));
                      return (
                        <button
                          key={n.source_id}
                          ref={selected ? selectedRef : undefined}
                          type="button"
                          className={`vb-card ${selected ? "selected" : ""} ${related ? "related" : ""} ${n.has_skeleton ? "has-sk" : ""}`}
                          onClick={() => onSelect(n.source_id)}
                          title={`${labels.title} · #${n.source_id}`}
                        >
                          <div
                            className="vb-sil"
                            style={{ ["--sil-color" as string]: typeHue(n.cell_type) }}
                            dangerouslySetInnerHTML={{
                              __html: sil || placeholderSil(n.has_skeleton),
                            }}
                          />
                          <div className="vb-card-text">
                            <div className="vb-card-title">{labels.title}</div>
                            <div className="vb-card-sub">
                              {related ? (upstream?.has(n.source_id) ? "↑ partner" : "↓ partner") : labels.subtitle}
                            </div>
                          </div>
                        </button>
                      );
                    })}
                    {rows.length > 64 && <div className="vb-more">+{rows.length - 64} more in type</div>}
                  </div>
                )}
              </section>
            );
          })}
          {!loading && !groups.length && <p className="muted compact">No neurons match.</p>}
        </div>
      )}

      {mode === "map" && (
        <div className="vb-map-wrap">
          {!mapBounds && <p className="muted compact">{loading ? "Loading…" : "No soma positions in this pack page."}</p>}
          {mapBounds && (
            <svg className="vb-map" viewBox="0 0 280 280" role="img" aria-label="Soma map">
              <rect width="280" height="280" fill="#0a1410" />
              {mapBounds.rows.map((n) => {
                const sx = ((n.soma_x! - mapBounds.minX) / Math.max(1, mapBounds.maxX - mapBounds.minX)) * 260 + 10;
                const sy = 270 - ((n.soma_y! - mapBounds.minY) / Math.max(1, mapBounds.maxY - mapBounds.minY)) * 260;
                const selected = selectedId === n.source_id;
                const related = upstream?.has(n.source_id) || downstream?.has(n.source_id);
                return (
                  <circle
                    key={n.source_id}
                    cx={sx}
                    cy={sy}
                    r={selected ? 7 : related ? 5.5 : 4}
                    fill={typeHue(n.cell_type)}
                    opacity={selected ? 1 : related ? 0.95 : 0.7}
                    stroke={selected ? "#ffe9a8" : related ? "#7ad0ff" : "transparent"}
                    strokeWidth={selected || related ? 1.5 : 0}
                    style={{ cursor: "pointer" }}
                    onClick={() => onSelect(n.source_id)}
                  >
                    <title>{n.name || n.cell_type || n.source_id}</title>
                  </circle>
                );
              })}
            </svg>
          )}
          <p className="muted compact">Each dot is a soma. Color = cell type. Click to zoom.</p>
        </div>
      )}

      {canLoadMore && (
        <button type="button" className="load-more" onClick={onLoadMore} disabled={loadingMore}>
          {loadingMore ? "Loading…" : "Load more neurons"}
        </button>
      )}
    </div>
  );
}

function placeholderSil(hasSk?: boolean) {
  if (hasSk) {
    return `<svg viewBox="0 0 88 88" class="sil-svg"><circle cx="44" cy="44" r="10" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.35"/><path d="M44 20 v48 M28 36 h32" stroke="currentColor" stroke-width="1.2" opacity="0.3"/></svg>`;
  }
  return `<svg viewBox="0 0 88 88" class="sil-svg"><circle cx="44" cy="44" r="6" fill="#24352e"/></svg>`;
}

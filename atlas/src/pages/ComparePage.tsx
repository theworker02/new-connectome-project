import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type ConnectomeStatus, type NeuronIndexRow, type SkeletonBatch } from "../api";
import { Viewer3D } from "../components/Viewer3D";

const PACK: Record<string, string> = {
  drosophila: "hemibrain_epg_v0.1",
  bumblebee: "bombus_terrestris_cx_projectome_v0.1",
  cockroach: "rhyparobia_ibdb_morphology_v0.1",
  locust: "schistocerca_ibdb_morphology_v0.1",
  sweat_bee: "megalopta_ibdb_morphology_v0.1",
};

type Side = {
  batch: SkeletonBatch | null;
  idx: NeuronIndexRow[];
  status: ConnectomeStatus | null;
  manifest: Record<string, unknown> | null;
};

async function loadSide(key: string): Promise<Side> {
  const id = PACK[key] || key;
  const limit = key === "bumblebee" ? 200 : key.includes("bee") || key === "locust" ? 40 : 50;
  const [batch, neurons, conn] = await Promise.all([
    api.skeletonsBatch(id, limit).catch(() => null),
    api.neurons(id, "", 200).then((r) => r.neurons).catch(() => [] as NeuronIndexRow[]),
    api.connectome(id).catch(() => null),
  ]);
  return {
    batch,
    idx: neurons,
    status: (conn?.status as ConnectomeStatus) || null,
    manifest: conn?.manifest || null,
  };
}

function MetaStrip({ label, packId, side }: { label: string; packId: string; side: Side }) {
  const cov = (side.manifest?.coverage_map as Record<string, unknown>) || {};
  const layers = (side.manifest?.graph_layers as Record<string, boolean>) || {};
  return (
    <div className="compare-meta">
      <div className="compare-meta-title">
        <strong>{label}</strong>
        <span className="mono">{packId}</span>
      </div>
      <div className="compare-meta-grid">
        <span>n {side.status?.neurons?.toLocaleString() ?? "—"}</span>
        <span>e {side.status?.edges?.toLocaleString() ?? "—"}</span>
        <span>sk {side.status?.skeletons?.toLocaleString() ?? side.batch?.count ?? "—"}</span>
        <span>syn {side.status?.synapses?.toLocaleString() ?? "—"}</span>
      </div>
      <div className="coverage-chip">{String(cov.claim || side.status?.coverage_claim || "—")}</div>
      <div className="layer-row">
        {Object.entries(layers).map(([k, v]) => (
          <span key={k} className={`layer-pill ${v ? "on" : "off"}`}>
            {k.replace("OBSERVED_", "").replace("INFERRED_", "INF_")}
          </span>
        ))}
      </div>
      <p className="muted compact">
        {String(
          cov.notes ||
            (Array.isArray(side.manifest?.limitations) ? (side.manifest!.limitations as string[])[0] : "") ||
            "",
        )}
      </p>
    </div>
  );
}

export function ComparePage() {
  const { a = "drosophila", b = "bumblebee" } = useParams();
  const [left, setLeft] = useState<Side>({ batch: null, idx: [], status: null, manifest: null });
  const [right, setRight] = useState<Side>({ batch: null, idx: [], status: null, manifest: null });

  useEffect(() => {
    loadSide(a).then(setLeft);
    loadSide(b).then(setRight);
  }, [a, b]);

  const empty = new Set<number>();
  const pa = PACK[a] || a;
  const pb = PACK[b] || b;

  return (
    <div className="compare-shell">
      <div className="compare-bar">
        <div>
          Cross-species morphology compare · <strong>{a}</strong> vs <strong>{b}</strong>
          <span className="muted"> — independent specimens, never merged</span>
        </div>
        <div className="compare-links">
          <Link to={`/species/${a}?c=${encodeURIComponent(pa)}`}>open {a}</Link>
          <Link to={`/species/${b}?c=${encodeURIComponent(pb)}`}>open {b}</Link>
          <Link to="/">home</Link>
        </div>
      </div>
      <div className="compare-grid">
        <div className="compare-pane">
          <MetaStrip label={a} packId={pa} side={left} />
          <div className="viewport">
            <Viewer3D
              batch={left.batch}
              index={left.idx}
              selectedId={null}
              upstream={empty}
              downstream={empty}
              isolated={false}
              showSomas
            />
          </div>
        </div>
        <div className="compare-pane">
          <MetaStrip label={b} packId={pb} side={right} />
          <div className="viewport">
            <Viewer3D
              batch={right.batch}
              index={right.idx}
              selectedId={null}
              upstream={empty}
              downstream={empty}
              isolated={false}
              showSomas
            />
          </div>
        </div>
      </div>
    </div>
  );
}

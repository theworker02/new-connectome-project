import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type AutonomyStatus, type ConnectomeStatus, type SkeletonBatch } from "../api";
import { silhouetteFromSegments, typeHue } from "../silhouette";

const ROUTE: Record<string, string> = {
  "Drosophila melanogaster": "drosophila",
  "Bombus terrestris": "bumblebee",
  "Megalopta genalis": "sweat_bee",
  "Schistocerca gregaria": "locust",
  "Rhyparobia maderae": "cockroach",
};

const LABELS: Record<string, string> = {
  "hemibrain_epg_v0.1": "EPG heading compass",
  "hemibrain_pen_a_v0.1": "PEN compass update",
  "optic_lobe_t4_v0.1": "Optic lobe T4 motion",
  "manc_sample_v0.1": "MANC ventral nerve cord",
  "bombus_terrestris_cx_projectome_v0.1": "Bumblebee central complex",
  "cremi_sample_a_v0.2": "CREMI synapse sample",
  "megalopta_ibdb_morphology_v0.1": "Sweat bee morphology",
  "schistocerca_ibdb_morphology_v0.1": "Locust morphology",
  "rhyparobia_ibdb_morphology_v0.1": "Cockroach morphology",
  "hemibrain_cx_catalog_v0.1": "Hemibrain CX catalog",
  "hemibrain_mb_catalog_v0.1": "Hemibrain MB catalog",
  "optic_lobe_motion_catalog_v0.1": "Optic lobe T4/T5 catalog",
};

const BLURBS: Record<string, string> = {
  "hemibrain_epg_v0.1": "Fly internal compass cells — morphology + synaptic partners from hemibrain.",
  "hemibrain_pen_a_v0.1": "Compass-update pathway that turns the heading bump.",
  "optic_lobe_t4_v0.1": "Direction-selective motion detectors in the medulla.",
  "manc_sample_v0.1": "Full VNC neuron catalog with high-degree 3D sample.",
  "bombus_terrestris_cx_projectome_v0.1": "Bumblebee CX projectome — comparative morphology.",
  "cremi_sample_a_v0.2": "Synaptic graph + optional EM mid-slice evidence.",
  "megalopta_ibdb_morphology_v0.1": "IBdb sweat-bee reconstructions (morphology layer).",
  "schistocerca_ibdb_morphology_v0.1": "IBdb locust reconstructions (morphology layer).",
  "rhyparobia_ibdb_morphology_v0.1": "IBdb cockroach reconstructions (morphology layer).",
  "hemibrain_cx_catalog_v0.1": "Dense CX cell-type index — graph only, tiny footprint.",
  "hemibrain_mb_catalog_v0.1": "Kenyon cells + MBON/DAN catalog — synaptic graph, no EM.",
  "optic_lobe_motion_catalog_v0.1": "Full T4/T5 population catalog from optic-lobe neuPrint.",
};

const FEATURED = [
  "hemibrain_epg_v0.1",
  "hemibrain_pen_a_v0.1",
  "optic_lobe_t4_v0.1",
  "manc_sample_v0.1",
  "bombus_terrestris_cx_projectome_v0.1",
  "cremi_sample_a_v0.2",
  "megalopta_ibdb_morphology_v0.1",
  "schistocerca_ibdb_morphology_v0.1",
  "rhyparobia_ibdb_morphology_v0.1",
  "hemibrain_cx_catalog_v0.1",
  "hemibrain_mb_catalog_v0.1",
  "optic_lobe_motion_catalog_v0.1",
];

const TAGS: Record<string, string[]> = {
  "hemibrain_epg_v0.1": ["synaptic", "3D", "compass"],
  "hemibrain_pen_a_v0.1": ["synaptic", "3D", "compass"],
  "optic_lobe_t4_v0.1": ["synaptic", "3D", "vision"],
  "manc_sample_v0.1": ["synaptic", "3D", "VNC"],
  "bombus_terrestris_cx_projectome_v0.1": ["morphology", "3D", "CX"],
  "cremi_sample_a_v0.2": ["synaptic", "EM evidence"],
  "megalopta_ibdb_morphology_v0.1": ["morphology", "3D", "IBdb"],
  "schistocerca_ibdb_morphology_v0.1": ["morphology", "3D", "IBdb"],
  "rhyparobia_ibdb_morphology_v0.1": ["morphology", "3D", "IBdb"],
  "hemibrain_cx_catalog_v0.1": ["catalog", "CX", "dense"],
  "hemibrain_mb_catalog_v0.1": ["catalog", "MB", "dense"],
  "optic_lobe_motion_catalog_v0.1": ["catalog", "vision", "dense"],
};

function packHref(p: ConnectomeStatus) {
  const key = ROUTE[p.species || ""] || "drosophila";
  return `/species/${key}?c=${encodeURIComponent(p.connectome_id)}`;
}

function PackPreview({ packId }: { packId: string }) {
  const [svg, setSvg] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    api
      .skeletonsBatch(packId, 8)
      .then((b: SkeletonBatch) => {
        if (cancelled || !b.neurons[0]?.line_segments?.length) return;
        setSvg(silhouetteFromSegments(b.neurons[0].line_segments, 120));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [packId]);
  return (
    <div className="pack-preview" style={{ color: typeHue(packId) }} dangerouslySetInnerHTML={{ __html: svg || "" }} />
  );
}

export function Home() {
  const [packs, setPacks] = useState<ConnectomeStatus[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [lastPack, setLastPack] = useState<string | null>(null);
  const [autonomy, setAutonomy] = useState<AutonomyStatus | null>(null);
  const [autonomyBusy, setAutonomyBusy] = useState(false);
  const [autonomyMsg, setAutonomyMsg] = useState<string | null>(null);

  const refresh = () => {
    api.connectomes().then(setPacks).catch((e) => setErr(String(e)));
    api.autonomyStatus().then(setAutonomy).catch(() => setAutonomy(null));
  };

  useEffect(() => {
    refresh();
    try {
      setLastPack(localStorage.getItem("insectome.lastPack"));
    } catch {
      /* ignore */
    }
  }, []);

  const runAutonomy = async () => {
    setAutonomyBusy(true);
    setAutonomyMsg(null);
    try {
      const result = await api.autonomyRun(true);
      const n = (result.ingested_packs || []).length;
      setAutonomyMsg(
        n
          ? `Ingested ${n} catalog pack${n === 1 ? "" : "s"}: ${(result.ingested_packs || []).join(", ")}`
          : "Cycle complete — no new auto-ingest (see candidates below).",
      );
      refresh();
    } catch (e) {
      setAutonomyMsg(String(e));
    } finally {
      setAutonomyBusy(false);
    }
  };

  const totals = useMemo(() => {
    return {
      neurons: packs.reduce((a, p) => a + (p.neurons || 0), 0),
      skeletons: packs.reduce((a, p) => a + (p.skeletons || 0), 0),
      edges: packs.reduce((a, p) => a + (p.edges || 0), 0),
      ready: packs.filter((p) => String(p.atlas_status).includes("READY")).length,
    };
  }, [packs]);

  const featured = useMemo(() => {
    return FEATURED.map((id) => packs.find((p) => p.connectome_id === id)).filter(Boolean) as ConnectomeStatus[];
  }, [packs]);

  const rest = useMemo(() => {
    const feat = new Set(FEATURED);
    return packs.filter((p) => !feat.has(p.connectome_id));
  }, [packs]);

  const continuePack = lastPack ? packs.find((p) => p.connectome_id === lastPack) : null;

  return (
    <div className="studio-home">
      <header className="studio-hero">
        <p className="studio-eyebrow">Local connectome studio</p>
        <h1>Insectome</h1>
        <p>
          Browse real insect nervous-system reconstructions by shape and cell class — then zoom into what each
          neuron does. {api.mode === "static" ? "This is a static GitHub Pages snapshot; EM stays remote." : "Packs stay on your machine; EM volumes stay remote."}
        </p>
        <div className="studio-hero-stats">
          <div>
            <strong>{totals.ready || packs.length}</strong>
            <span>packs ready</span>
          </div>
          <div>
            <strong>{totals.neurons.toLocaleString()}</strong>
            <span>neurons catalogued</span>
          </div>
          <div>
            <strong>{totals.skeletons.toLocaleString()}</strong>
            <span>3D skeletons</span>
          </div>
          <div>
            <strong>{totals.edges.toLocaleString()}</strong>
            <span>synaptic edges</span>
          </div>
        </div>
        {continuePack && (
          <p className="studio-continue">
            <Link className="btn primary" to={packHref(continuePack)}>
              Continue · {LABELS[continuePack.connectome_id] || continuePack.connectome_id}
            </Link>
          </p>
        )}
      </header>

      {err && <p className="coverage-chip danger">{err}</p>}

      <section className="studio-section autonomy-section">
        <h2 className="studio-section-title">Autonomy</h2>
        <p className="studio-section-lede">
          Evidence-gated discovery watches neuPrint, IBdb, and the registry. Dense catalogs auto-ingest as
          graph/index packs (no EM). Other finds stay as review candidates.
        </p>
        <div className="autonomy-bar">
          <div className="autonomy-stat">
            <strong>{autonomy?.pack_bytes_label || "—"}</strong>
            <span>pack footprint</span>
          </div>
          <div className="autonomy-stat">
            <strong>{autonomy?.candidate_count ?? "—"}</strong>
            <span>candidates</span>
          </div>
          <div className="autonomy-stat">
            <strong>{autonomy?.by_status?.AUTO_INGESTED ?? 0}</strong>
            <span>auto-ingested</span>
          </div>
          <div className="autonomy-stat">
            <strong>{autonomy?.by_status?.NEEDS_REVIEW ?? 0}</strong>
            <span>needs review</span>
          </div>
          <button
            className="btn primary"
            type="button"
            disabled={autonomyBusy || api.mode === "static"}
            onClick={runAutonomy}
            title={api.mode === "static" ? "Autonomy runs in the local studio only" : undefined}
          >
            {api.mode === "static" ? "Read-only on Pages" : autonomyBusy ? "Running…" : "Run discovery cycle"}
          </button>
        </div>
        {api.mode === "static" && (
          <p className="autonomy-msg">
            Static snapshot — refresh candidates locally with <code>insectome autonomy run</code> then{" "}
            <code>insectome pages export</code>.
          </p>
        )}
        {autonomyMsg && <p className="autonomy-msg">{autonomyMsg}</p>}
        {autonomy && autonomy.candidates.length > 0 && (
          <div className="candidate-table-wrap">
            <table className="candidate-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Score</th>
                  <th>Candidate</th>
                  <th>Species</th>
                </tr>
              </thead>
              <tbody>
                {autonomy.candidates
                  .filter((c) => {
                    const tags = c.tags || [];
                    if (tags.includes("discovery_seed")) return false;
                    if (c.status === "DISCOVERED" && c.reuse_score < 60) return false;
                    return true;
                  })
                  .slice(0, 18)
                  .map((c) => (
                    <tr key={c.candidate_id}>
                      <td>
                        <span className={`cand-status ${c.status.toLowerCase()}`}>{c.status}</span>
                      </td>
                      <td>{c.reuse_score}</td>
                      <td>
                        <div className="cand-title">{c.title}</div>
                        <div className="cand-id">{c.candidate_id}</div>
                      </td>
                      <td>{c.species || "—"}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {featured.length > 0 && (
        <section className="studio-section">
          <h2 className="studio-section-title">Start here</h2>
          <p className="studio-section-lede">
            Local packs — fly circuits, dense graph catalogs, comparative morphology, and an EM evidence sample.
          </p>
          <div className="pack-tiles featured">
            {featured.map((p) => (
              <Link key={p.connectome_id} className="pack-tile featured-tile" to={packHref(p)}>
                <PackPreview packId={p.connectome_id} />
                <div className="pack-tile-body">
                  <div className="pack-tile-kicker">{p.species || "—"}</div>
                  <h2>{LABELS[p.connectome_id] || p.connectome_id}</h2>
                  <p className="pack-tile-blurb">{BLURBS[p.connectome_id]}</p>
                  <div className="pack-tile-tags">
                    {(TAGS[p.connectome_id] || []).map((t) => (
                      <span key={t} className="pack-tag">
                        {t}
                      </span>
                    ))}
                  </div>
                  <div className="pack-tile-stats">
                    <span>{(p.neurons || 0).toLocaleString()} neurons</span>
                    <span>{(p.skeletons || 0).toLocaleString()} 3D</span>
                    <span>{(p.edges || 0).toLocaleString()} edges</span>
                  </div>
                  <div className={`pack-tile-status ${String(p.atlas_status).includes("READY") ? "ok" : ""}`}>
                    {p.atlas_status}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {rest.length > 0 && (
        <section className="studio-section">
          <h2 className="studio-section-title">More packs</h2>
          <div className="pack-tiles">
            {rest.map((p) => (
              <Link key={p.connectome_id} className="pack-tile" to={packHref(p)}>
                <div className="pack-tile-kicker">{p.species || "—"}</div>
                <h2>{LABELS[p.connectome_id] || p.connectome_id}</h2>
                <p className="pack-tile-blurb">{BLURBS[p.connectome_id] || p.coverage_claim || ""}</p>
                <div className="pack-tile-stats">
                  <span>{(p.neurons || 0).toLocaleString()} neurons</span>
                  <span>{(p.skeletons || 0).toLocaleString()} 3D</span>
                  <span>{(p.edges || 0).toLocaleString()} edges</span>
                </div>
                <div className={`pack-tile-status ${String(p.atlas_status).includes("READY") ? "ok" : ""}`}>
                  {p.atlas_status}
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}
      {!packs.length && !err && <p className="muted">Loading packs…</p>}
    </div>
  );
}

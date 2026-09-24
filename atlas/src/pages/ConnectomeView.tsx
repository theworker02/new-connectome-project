import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, type NeuronIndexRow, type SkeletonBatch } from "../api";
import { Viewer3D } from "../components/Viewer3D";
import { StoragePanel } from "../components/StoragePanel";
import { GraphPanel } from "../components/GraphPanel";
import { VisualBrowser } from "../components/VisualBrowser";
import { describeNeuron } from "../neuronRoles";

const PACKS: { id: string; label: string }[] = [
  { id: "hemibrain_epg_v0.1", label: "Fly · EPG compass" },
  { id: "hemibrain_pen_a_v0.1", label: "Fly · PEN update" },
  { id: "hemibrain_cx_catalog_v0.1", label: "Fly · CX catalog" },
  { id: "hemibrain_mb_catalog_v0.1", label: "Fly · MB catalog" },
  { id: "optic_lobe_t4_v0.1", label: "Fly · Optic lobe T4" },
  { id: "optic_lobe_motion_catalog_v0.1", label: "Fly · T4/T5 catalog" },
  { id: "manc_sample_v0.1", label: "Fly · MANC VNC" },
  { id: "bombus_terrestris_cx_projectome_v0.1", label: "Bumblebee · CX" },
  { id: "cremi_sample_a_v0.2", label: "CREMI · EM sample" },
  { id: "megalopta_ibdb_morphology_v0.1", label: "Sweat bee · morphology" },
  { id: "schistocerca_ibdb_morphology_v0.1", label: "Locust · morphology" },
  { id: "rhyparobia_ibdb_morphology_v0.1", label: "Cockroach · morphology" },
];

const DEFAULT: Record<string, string> = {
  drosophila: "hemibrain_epg_v0.1",
  bumblebee: "bombus_terrestris_cx_projectome_v0.1",
  sweat_bee: "megalopta_ibdb_morphology_v0.1",
  locust: "schistocerca_ibdb_morphology_v0.1",
  cockroach: "rhyparobia_ibdb_morphology_v0.1",
};

const PAGE = 400;

function fmt(n: unknown) {
  if (typeof n === "number") return n.toLocaleString();
  return String(n ?? "—");
}

export function ConnectomeView() {
  const { speciesKey = "drosophila" } = useParams();
  const [params, setParams] = useSearchParams();
  const connectomeId = params.get("c") || DEFAULT[speciesKey] || "hemibrain_epg_v0.1";

  const [manifest, setManifest] = useState<Record<string, unknown> | null>(null);
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [neurons, setNeurons] = useState<NeuronIndexRow[]>([]);
  const [neuronTotal, setNeuronTotal] = useState(0);
  const [skOnly, setSkOnly] = useState(false);
  const [q, setQ] = useState("");
  const [qDebounced, setQDebounced] = useState("");
  const [batch, setBatch] = useState<SkeletonBatch | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [upstream, setUpstream] = useState<Set<number>>(new Set());
  const [downstream, setDownstream] = useState<Set<number>>(new Set());
  const [upRows, setUpRows] = useState<Record<string, unknown>[]>([]);
  const [downRows, setDownRows] = useState<Record<string, unknown>[]>([]);
  const [isolated, setIsolated] = useState(false);
  const [showPartners, setShowPartners] = useState(true);
  const [showSomas, setShowSomas] = useState(true);
  const [showLinks, setShowLinks] = useState(true);
  const [emUrl, setEmUrl] = useState<string | null>(null);
  const [pathFrom, setPathFrom] = useState("");
  const [pathTo, setPathTo] = useState("");
  const [pathResult, setPathResult] = useState<number[] | null>(null);
  const [pathFound, setPathFound] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [emError, setEmError] = useState<string | null>(null);
  const [loadingSk, setLoadingSk] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [exportMsg, setExportMsg] = useState<string | null>(null);
  const [showMethods, setShowMethods] = useState(false);
  const [focusNonce, setFocusNonce] = useState(0);
  const [autoFocus, setAutoFocus] = useState(true);
  const [dockOpen, setDockOpen] = useState(false);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const packSwitchRef = useRef(connectomeId);
  const prevPackRef = useRef<string | null>(null);

  function selectNeuron(id: number) {
    setSelectedId(id);
    if (autoFocus) {
      setIsolated(true);
      setShowPartners(true);
      setShowLinks(true);
      setFocusNonce((n) => n + 1);
    }
  }

  useEffect(() => {
    const t = window.setTimeout(() => setQDebounced(q), 220);
    return () => window.clearTimeout(t);
  }, [q]);

  useEffect(() => {
    setError(null);
    setLoadingSk(true);
    setExportMsg(null);
    setCatalogLoading(true);
    setEmError(null);
    setIsolated(false);
    packSwitchRef.current = connectomeId;

    const switched = prevPackRef.current != null && prevPackRef.current !== connectomeId;
    prevPackRef.current = connectomeId;

    api
      .connectome(connectomeId)
      .then((r) => {
        if (packSwitchRef.current !== connectomeId) return;
        setManifest(r.manifest);
        setStatus(r.status as unknown as Record<string, unknown>);
      })
      .catch((e) => {
        if (packSwitchRef.current === connectomeId) setError(String(e));
      });

    setBatch({ connectome_id: connectomeId, count: 0, neurons: [] });
    const waves = connectomeId.includes("bombus")
      ? [50, 150, 400]
      : connectomeId.includes("ibdb")
        ? [20, 40, 80]
        : connectomeId.includes("optic")
          ? [40, 100, 200]
          : connectomeId.includes("manc")
            ? [20, 40, 60]
            : [20, 50, 80];
    let cancelled = false;
    (async () => {
      try {
        for (const n of waves) {
          const b = await api.skeletonsBatch(connectomeId, n);
          if (cancelled) return;
          setBatch(b);
        }
      } catch {
        if (!cancelled) setBatch(null);
      } finally {
        if (!cancelled) setLoadingSk(false);
      }
    })();

    setDetail(null);
    setUpstream(new Set());
    setDownstream(new Set());
    setUpRows([]);
    setDownRows([]);
    setEmUrl(null);
    setPathResult(null);
    setPathFound(null);
    setNeurons([]);
    setNeuronTotal(0);

    if (switched) {
      setSelectedId(null);
      setParams(
        (p) => {
          const n = new URLSearchParams(p);
          n.set("c", connectomeId);
          n.delete("n");
          return n;
        },
        { replace: true },
      );
    } else {
      setParams(
        (p) => {
          const n = new URLSearchParams(p);
          if (n.get("c") === connectomeId) return p;
          n.set("c", connectomeId);
          return n;
        },
        { replace: true },
      );
    }
    try {
      localStorage.setItem("insectome.lastPack", connectomeId);
    } catch {
      /* ignore */
    }
    return () => {
      cancelled = true;
    };
  }, [connectomeId, setParams]);

  useEffect(() => {
    let cancelled = false;
    setCatalogLoading(true);
    setLoadingMore(true);
    api
      .neurons(connectomeId, qDebounced, PAGE)
      .then((r) => {
        if (cancelled) return;
        setNeuronTotal(r.total);
        setNeurons(r.neurons);
      })
      .catch(() => {
        if (!cancelled) {
          setNeurons([]);
          setNeuronTotal(0);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingMore(false);
          setCatalogLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [connectomeId, qDebounced]);

  // Deep-link / restore ?n= for this pack
  useEffect(() => {
    const nid = params.get("n");
    if (!nid) return;
    const c = params.get("c");
    if (c && c !== connectomeId) return;
    const id = Number(nid);
    if (!Number.isNaN(id)) setSelectedId(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional: run when pack loads
  }, [connectomeId]);

  useEffect(() => {
    if (selectedId == null) return;
    setParams((p) => {
      const n = new URLSearchParams(p);
      n.set("c", connectomeId);
      n.set("n", String(selectedId));
      return n;
    }, { replace: true });
    api.neuron(connectomeId, selectedId).then(setDetail).catch(() => setDetail(null));
    if (showPartners) {
      api.partners(connectomeId, selectedId).then((p) => {
        const up = new Set<number>();
        const down = new Set<number>();
        for (const row of p.upstream) {
          const id = Number(row.pre_neuron_id);
          if (!Number.isNaN(id)) up.add(id);
        }
        for (const row of p.downstream) {
          const id = Number(row.post_neuron_id);
          if (!Number.isNaN(id)) down.add(id);
        }
        setUpstream(up);
        setDownstream(down);
        setUpRows(p.upstream);
        setDownRows(p.downstream);
      });
    } else {
      setUpstream(new Set());
      setDownstream(new Set());
      setUpRows([]);
      setDownRows([]);
    }
  }, [selectedId, connectomeId, showPartners, setParams]);

  useEffect(() => {
    if (selectedId == null) return;
    let cancelled = false;
    const already = batch?.neurons.some((n) => n.source_id === selectedId);
    if (already) {
      if (autoFocus) setFocusNonce((n) => n + 1);
      return;
    }
    api
      .skeleton(connectomeId, selectedId)
      .then((sk) => {
        if (cancelled || !sk.line_segments?.length) return;
        setBatch((b) => {
          const base = b ?? { connectome_id: connectomeId, count: 0, neurons: [] };
          if (base.neurons.some((n) => n.source_id === selectedId)) return base;
          const neurons = [
            ...base.neurons,
            {
              source_id: selectedId,
              global_id: String(sk.meta?.global_id || selectedId),
              name: null,
              line_segments: sk.line_segments!,
              n_vertices: sk.n_vertices,
            },
          ];
          return { ...base, count: neurons.length, neurons };
        });
        if (autoFocus) setFocusNonce((n) => n + 1);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
    // intentionally omit batch from deps — only react to selection changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, connectomeId, autoFocus]);

  const coverage = (manifest?.coverage_map as Record<string, unknown> | undefined) || {};
  const claim = String(coverage.claim || status?.coverage_claim || "");
  const claimLabel = claim || (status || manifest ? "—" : "Loading…");
  const idxRow = (detail?.index as Record<string, unknown> | null) || null;
  const neuronRow = (detail?.neuron as Record<string, unknown>) || {};

  const role = useMemo(() => {
    if (selectedId == null) return null;
    return describeNeuron({
      cellType: String(neuronRow?.type || idxRow?.cell_type || ""),
      name: String(neuronRow?.name || neuronRow?.instance || idxRow?.name || ""),
      region: String(coverage.region || status?.region || ""),
      degreeIn: Number(idxRow?.degree_in ?? upstream.size) || 0,
      degreeOut: Number(idxRow?.degree_out ?? downstream.size) || 0,
      hasSkeleton: Boolean(idxRow?.has_skeleton),
    });
  }, [selectedId, neuronRow, idxRow, coverage.region, status?.region, upstream.size, downstream.size]);

  async function loadMore() {
    if (neurons.length >= neuronTotal) return;
    setLoadingMore(true);
    try {
      const r = await api.neurons(connectomeId, qDebounced, PAGE, neurons.length);
      setNeurons((prev) => {
        const seen = new Set(prev.map((n) => n.source_id));
        const merged = [...prev];
        for (const n of r.neurons) {
          if (!seen.has(n.source_id)) merged.push(n);
        }
        return merged;
      });
      setNeuronTotal(r.total);
    } finally {
      setLoadingMore(false);
    }
  }

  async function loadEm() {
    setEmError(null);
    try {
      const em = await api.synapseEm("cremi_sample_a_v0.2", 0);
      const [h, w] = em.mid_slice_shape;
      const raw = Uint8Array.from(atob(em.mid_slice_b64), (c) => c.charCodeAt(0));
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d")!;
      const img = ctx.createImageData(w, h);
      for (let i = 0; i < raw.length; i++) {
        const v = raw[i];
        img.data[i * 4] = v;
        img.data[i * 4 + 1] = v;
        img.data[i * 4 + 2] = v;
        img.data[i * 4 + 3] = 255;
      }
      ctx.putImageData(img, 0, 0);
      setEmUrl(canvas.toDataURL());
    } catch (e) {
      setEmError(String(e));
    }
  }

  async function runPath() {
    const a = Number(pathFrom || selectedId);
    const b = Number(pathTo);
    if (!a || !b) return;
    const r = await api.path(connectomeId, a, b);
    setPathResult(r.path);
    setPathFound(r.found);
  }

  async function doExport() {
    setExportMsg("exporting…");
    try {
      const r = await api.exportNeuroglancer(connectomeId);
      setExportMsg(`wrote ${r.path}`);
    } catch (e) {
      setExportMsg(String(e));
    }
  }

  return (
    <div className={`viewer-layout ${dockOpen ? "dock-open" : "dock-closed"}`}>
      <aside className="side side-visual">
        <div className="dataset-card">
          <div className="title">Pack</div>
          <select
            className="search"
            value={connectomeId}
            onChange={(e) =>
              setParams((p) => {
                const n = new URLSearchParams(p);
                n.set("c", e.target.value);
                n.delete("n");
                return n;
              })
            }
          >
            {PACKS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
          <p className="pack-blurb">
            {catalogLoading && !status
              ? "Loading pack…"
              : `${String(status?.species || "—")} · ${fmt(neuronTotal)} neurons · ${fmt(status?.skeletons)} with 3D`}
          </p>
          <div className="coverage-chip">{claimLabel}</div>
        </div>

        <VisualBrowser
          neurons={neurons}
          batch={batch}
          selectedId={selectedId}
          upstream={upstream}
          downstream={downstream}
          onSelect={selectNeuron}
          skOnly={skOnly}
          onSkOnly={setSkOnly}
          q={q}
          onQ={setQ}
          total={neuronTotal}
          loading={catalogLoading}
          packKey={connectomeId}
          onLoadMore={loadMore}
          loadingMore={loadingMore}
          canLoadMore={neurons.length < neuronTotal}
        />

        <p className="side-foot">
          <Link to="/">← Packs</Link>
        </p>
      </aside>

      <main className="viewport">
        <div className="viewport-hud">
          <div>
            <span className="coverage-chip teal">
              {batch?.count ?? 0} skeletons{loadingSk ? "…" : ""}
            </span>
            {error && <span className="coverage-chip danger">{error}</span>}
          </div>
          <div>
            <button
              type="button"
              className={`coverage-chip btn-chip ${autoFocus ? "on" : ""}`}
              onClick={() => setAutoFocus((v) => !v)}
            >
              auto-zoom {autoFocus ? "on" : "off"}
            </button>
            <button
              type="button"
              className="coverage-chip btn-chip"
              disabled={selectedId == null}
              onClick={() => {
                setIsolated(true);
                setFocusNonce((n) => n + 1);
              }}
            >
              zoom in
            </button>
            <button
              type="button"
              className="coverage-chip btn-chip"
              onClick={() => {
                setSelectedId(null);
                setIsolated(false);
                setFocusNonce((n) => n + 1);
                setParams(
                  (p) => {
                    const n = new URLSearchParams(p);
                    n.delete("n");
                    return n;
                  },
                  { replace: true },
                );
              }}
            >
              reset view
            </button>
            <button
              type="button"
              className={`coverage-chip btn-chip ${dockOpen ? "on" : ""}`}
              onClick={() => setDockOpen((v) => !v)}
            >
              {dockOpen ? "hide tools" : "tools"}
            </button>
          </div>
        </div>

        {role && selectedId != null && (
          <div className="neuron-focus-card">
            <div className="nfc-kicker">{role.system}</div>
            <h2>
              <span className="nfc-id">#{selectedId}</span>{" "}
              {String(neuronRow?.name || neuronRow?.instance || idxRow?.name || role.label)}
            </h2>
            <p className="nfc-does">
              <strong>What it does.</strong> {role.does}
            </p>
            <p className="nfc-conn">{role.connectivity}</p>
            <div className="nfc-actions">
              <button type="button" className="primary" onClick={() => setFocusNonce((n) => n + 1)}>
                Zoom in
              </button>
              <button type="button" className={isolated ? "active" : ""} onClick={() => setIsolated((v) => !v)}>
                {isolated ? "Show others" : "Isolate"}
              </button>
            </div>
          </div>
        )}

        {!selectedId && (
          <div className="viewport-hint">
            Click a silhouette in the gallery — or a soma on the map — to zoom in and see what it does.
          </div>
        )}

        <div className="viewport-frame">
          <Viewer3D
            batch={batch}
            index={neurons}
            selectedId={selectedId}
            upstream={upstream}
            downstream={downstream}
            isolated={isolated}
            showSomas={showSomas}
            showLinks={showLinks}
            focusNonce={focusNonce}
            onSelect={selectNeuron}
          />
        </div>
      </main>

      <aside className="panel">
        <h3>Inspect</h3>
        <div className="toolbar">
          <button className={isolated ? "active" : ""} onClick={() => setIsolated((v) => !v)}>
            Isolate
          </button>
          <button className={showPartners ? "active" : ""} onClick={() => setShowPartners((v) => !v)}>
            Partners
          </button>
          <button className={showSomas ? "active" : ""} onClick={() => setShowSomas((v) => !v)}>
            Somas
          </button>
          <button className={showLinks ? "active" : ""} onClick={() => setShowLinks((v) => !v)}>
            Hops
          </button>
        </div>
        {!detail && <p className="muted compact">Select a neuron to see identity, role, and partners.</p>}
        {detail && role && (
          <>
            <div className="role-block">
              <div className="nfc-kicker">{role.system}</div>
              <p className="role-does">{role.does}</p>
              <p className="muted compact">{role.connectivity}</p>
            </div>
            <dl className="kv tight">
              <dt>ID</dt>
              <dd>{selectedId}</dd>
              <dt>Name / type</dt>
              <dd>
                {String(neuronRow?.name || neuronRow?.instance || idxRow?.name || "—")} /{" "}
                {String(neuronRow?.type || idxRow?.cell_type || "—")}
              </dd>
              <dt>Degree</dt>
              <dd>
                in {fmt(idxRow?.degree_in ?? upstream.size)} · out {fmt(idxRow?.degree_out ?? downstream.size)}
              </dd>
            </dl>
            <h3>
              Upstream <span className="count-tag">{upRows.length}</span>
            </h3>
            <div className="partner-list">
              {upRows.slice(0, 40).map((p, i) => (
                <button key={i} onClick={() => selectNeuron(Number(p.pre_neuron_id))}>
                  ← {String(p.pre_neuron_id)} · w={String(p.synapse_count)}
                </button>
              ))}
              {!upRows.length && <span className="muted">none in pack</span>}
            </div>
            <h3>
              Downstream <span className="count-tag">{downRows.length}</span>
            </h3>
            <div className="partner-list">
              {downRows.slice(0, 40).map((p, i) => (
                <button key={i} onClick={() => selectNeuron(Number(p.post_neuron_id))}>
                  → {String(p.post_neuron_id)} · w={String(p.synapse_count)}
                </button>
              ))}
              {!downRows.length && <span className="muted">none in pack</span>}
            </div>
            <h3>Path</h3>
            <div className="path-row">
              <input
                placeholder="from"
                value={pathFrom || String(selectedId ?? "")}
                onChange={(e) => setPathFrom(e.target.value)}
              />
              <span className="muted">→</span>
              <input placeholder="to" value={pathTo} onChange={(e) => setPathTo(e.target.value)} />
              <button className="primary" onClick={runPath}>
                Go
              </button>
            </div>
            {pathResult && (
              <p className="muted mono-line">
                {pathResult.length - 1} hop(s): {pathResult.join(" → ")}
              </p>
            )}
            {pathFound === false && <p className="muted">No path in this pack.</p>}
          </>
        )}
        <button type="button" className="methods-toggle" onClick={() => setShowMethods((v) => !v)}>
          {showMethods ? "▾" : "▸"} Provenance
        </button>
        {showMethods && (
          <div className="methods-block">
            <p>
              <strong>Source:</strong> {String(manifest?.source || "—")}
            </p>
            <p>
              <strong>Specimen:</strong> {String(manifest?.specimen || "—")}
            </p>
            <p>
              <strong>Claim:</strong> {claim}
            </p>
            <button type="button" className="primary" onClick={doExport}>
              Export Neuroglancer
            </button>
            {exportMsg && <p className="stream-line">{exportMsg}</p>}
          </div>
        )}
        <StoragePanel connectomeId={connectomeId} />
      </aside>

      {dockOpen && (
        <div className="dock">
          <div className="dock-pane">
            <h3>Connectivity</h3>
            <GraphPanel selectedId={selectedId} upstream={upRows} downstream={downRows} onSelect={selectNeuron} />
          </div>
          <div className="dock-pane">
            <h3>EM cutout</h3>
            <p className="muted compact">CREMI sample only — optional.</p>
            <button onClick={loadEm}>Load CREMI mid-slice</button>
            {emError && (
              <p className="muted" style={{ color: "var(--danger)" }}>
                {emError}
              </p>
            )}
            {emUrl && <img className="em-slice" src={emUrl} alt="EM evidence mid-slice" />}
          </div>
        </div>
      )}
    </div>
  );
}

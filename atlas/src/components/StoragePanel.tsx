import React, { useEffect, useState } from "react";
import { api, type StorageStatus, type StreamingManifest } from "../api";

function fmt(bytes: number) {
  if (bytes > 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
  if (bytes > 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  if (bytes > 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${bytes} B`;
}

export function StoragePanel({ connectomeId }: { connectomeId: string }) {
  const [storage, setStorage] = useState<StorageStatus | null>(null);
  const [stream, setStream] = useState<StreamingManifest | null>(null);

  const refresh = () => {
    api.storage().then(setStorage).catch(() => setStorage(null));
    api.streaming(connectomeId).then(setStream).catch(() => setStream(null));
  };

  useEffect(() => {
    refresh();
  }, [connectomeId]);

  return (
    <div style={{ marginTop: "1rem", borderTop: "1px solid var(--line)", paddingTop: "0.8rem" }}>
      <h3>Storage · streaming</h3>
      {stream && (
        <dl className="kv">
          <dt>Local pack</dt>
          <dd>{fmt(stream.local_total_bytes)}</dd>
          <dt>Remote EM</dt>
          <dd>{stream.remote_raw_size ? fmt(stream.remote_raw_size) : "—"}</dd>
          <dt>Ratio</dt>
          <dd>
            {stream.remote_to_local_ratio
              ? `${Math.round(stream.remote_to_local_ratio).toLocaleString()}× (no full download)`
              : "—"}
          </dd>
        </dl>
      )}
      {storage && (
        <>
          <dl className="kv">
            <dt>Cache</dt>
            <dd>
              {fmt(storage.total_bytes)} / {fmt(storage.hard_limit_bytes)}
            </dd>
            <dt>RAM L1</dt>
            <dd>{fmt(storage.ram_bytes || 0)}</dd>
          </dl>
          <div className="actions">
            {api.mode === "static" ? (
              <p style={{ color: "var(--muted)", fontSize: "0.75rem", margin: 0 }}>
                Read-only GitHub Pages snapshot — cache controls available in the local studio.
              </p>
            ) : (
              <>
                <button onClick={() => api.clearCache("em_chunk,em_evidence").then(refresh)}>Clear EM</button>
                <button onClick={() => api.clearCache("mesh_hi,mesh_lo").then(refresh)}>Clear meshes</button>
                <button onClick={() => api.clearCache().then(refresh)}>Clear all</button>
              </>
            )}
          </div>
        </>
      )}
      <p style={{ color: "var(--muted)", fontSize: "0.75rem" }}>
        Skeletons first. Meshes/EM only on demand. Cache never exceeds the hard ceiling.
      </p>
    </div>
  );
}

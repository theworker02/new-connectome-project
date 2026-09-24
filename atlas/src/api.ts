export type SpeciesInfo = {
  key: string;
  scientific: string;
  common: string;
  heinze_2026: string;
  packs: string[];
  total_neurons: number;
  total_edges: number;
  total_skeletons?: number;
  atlas_ready: boolean;
  notes?: string;
};

export type ConnectomeStatus = {
  connectome_id: string;
  species?: string;
  region?: string;
  neurons: number;
  synapses: number;
  edges: number;
  morphology_coverage: boolean;
  synaptic_coverage: boolean;
  skeletons: number;
  atlas_status: string;
  coverage_claim?: string;
  labels?: string[];
};

export type NeuronIndexRow = {
  global_id?: string;
  source_id: number;
  name?: string;
  cell_type?: string;
  has_skeleton?: boolean;
  pre_count?: number;
  post_count?: number;
  degree_in?: number;
  degree_out?: number;
  soma_x?: number;
  soma_y?: number;
  soma_z?: number;
};

export type SkeletonBatch = {
  connectome_id: string;
  count: number;
  neurons: {
    source_id: number;
    global_id?: string;
    name?: string | null;
    line_segments: number[];
    n_vertices: number;
  }[];
};

export type StreamingManifest = {
  connectome_id: string;
  local_total_bytes: number;
  remote_raw_size: number;
  remote_to_local_ratio: number | null;
  cache_recommendation_gb: number;
  hard_cache_ceiling_gb: number;
  tiers: Record<string, number>;
  notes?: string;
};

export type StorageStatus = {
  total_bytes: number;
  soft_limit_bytes: number;
  hard_limit_bytes: number;
  ram_bytes: number;
  breakdown_bytes: Record<string, number>;
  root: string;
  static?: boolean;
};

export type AutonomyStatus = {
  pack_bytes: number;
  pack_bytes_label: string;
  soft_limit_bytes: number;
  hard_limit_bytes: number;
  candidate_count: number;
  by_status: Record<string, number>;
  candidates: {
    candidate_id: string;
    title: string;
    species?: string;
    status: string;
    reuse_score: number;
    local_pack_id?: string | null;
    notes?: string | null;
    tags?: string[];
    plan?: { connectome_id?: string | null; auto_eligible?: boolean; block_reason?: string | null } | null;
  }[];
  static?: boolean;
  note?: string;
};

const STATIC =
  import.meta.env.VITE_STATIC === "true" || import.meta.env.VITE_STATIC === "1";

const BASE_URL = (import.meta.env.BASE_URL || "/").replace(/\/$/, "");

function dataUrl(path: string) {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${BASE_URL}/data${p}`;
}

function apiUrl(path: string) {
  return path.startsWith("/") ? path : `/${path}`;
}

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json() as Promise<T>;
}

async function get<T>(path: string): Promise<T> {
  if (STATIC) {
    // Map legacy /api paths is handled by api methods below
    return getJson<T>(path.startsWith("/data") || path.includes("/data/") ? path : dataUrl(path));
  }
  return getJson<T>(apiUrl(path));
}

async function post<T>(path: string): Promise<T> {
  if (STATIC) {
    throw new Error("This action requires the local Insectome studio (read-only on GitHub Pages).");
  }
  const r = await fetch(apiUrl(path), { method: "POST" });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json() as Promise<T>;
}

const neuronCache = new Map<string, NeuronIndexRow[]>();
const edgeCache = new Map<string, { pre_neuron_id: number; post_neuron_id: number; synapse_count?: number }[]>();

async function loadNeurons(id: string): Promise<NeuronIndexRow[]> {
  const hit = neuronCache.get(id);
  if (hit) return hit;
  const payload = await getJson<{ total: number; neurons: NeuronIndexRow[] }>(dataUrl(`/packs/${id}/neurons.json`));
  neuronCache.set(id, payload.neurons || []);
  return neuronCache.get(id)!;
}

async function loadEdges(id: string) {
  if (edgeCache.has(id)) return edgeCache.get(id)!;
  try {
    const payload = await getJson<{ edges: { pre_neuron_id: number; post_neuron_id: number; synapse_count?: number }[] }>(
      dataUrl(`/packs/${id}/edges.json`),
    );
    edgeCache.set(id, payload.edges || []);
  } catch {
    edgeCache.set(id, []);
  }
  return edgeCache.get(id)!;
}

function filterNeurons(rows: NeuronIndexRow[], q: string, limit: number, offset: number) {
  const qq = q.trim().toLowerCase();
  let filtered = rows;
  if (qq) {
    filtered = rows.filter((n) => {
      const hay = `${n.source_id} ${n.name || ""} ${n.cell_type || ""} ${n.global_id || ""}`.toLowerCase();
      return hay.includes(qq);
    });
  }
  return {
    total: filtered.length,
    neurons: filtered.slice(offset, offset + limit),
    offset,
    limit,
  };
}

function bfsPath(
  edges: { pre_neuron_id: number; post_neuron_id: number }[],
  source: number,
  target: number,
  cutoff = 4,
): number[] | null {
  if (source === target) return [source];
  const adj = new Map<number, number[]>();
  for (const e of edges) {
    const a = Number(e.pre_neuron_id);
    const b = Number(e.post_neuron_id);
    if (!adj.has(a)) adj.set(a, []);
    adj.get(a)!.push(b);
  }
  const q: number[] = [source];
  const prev = new Map<number, number | null>([[source, null]]);
  const depth = new Map<number, number>([[source, 0]]);
  while (q.length) {
    const cur = q.shift()!;
    const d = depth.get(cur) || 0;
    if (d >= cutoff) continue;
    for (const nxt of adj.get(cur) || []) {
      if (prev.has(nxt)) continue;
      prev.set(nxt, cur);
      depth.set(nxt, d + 1);
      if (nxt === target) {
        const path: number[] = [target];
        let p: number | null = cur;
        while (p != null) {
          path.push(p);
          p = prev.get(p) ?? null;
        }
        return path.reverse();
      }
      q.push(nxt);
    }
  }
  return null;
}

export const api = {
  mode: STATIC ? ("static" as const) : ("live" as const),

  species: () => (STATIC ? get<SpeciesInfo[]>(dataUrl("/species.json")) : get<SpeciesInfo[]>("/api/species")),

  connectomes: () =>
    STATIC ? get<ConnectomeStatus[]>(dataUrl("/connectomes.json")) : get<ConnectomeStatus[]>("/api/connectomes"),

  connectome: async (id: string) => {
    if (STATIC) {
      return getJson<{ manifest: Record<string, unknown>; status: ConnectomeStatus }>(
        dataUrl(`/packs/${id}/manifest.json`),
      );
    }
    return get<{ manifest: Record<string, unknown>; status: ConnectomeStatus }>(`/api/connectomes/${id}`);
  },

  streaming: async (id: string): Promise<StreamingManifest> => {
    if (STATIC) {
      const status = await getJson<ConnectomeStatus>(dataUrl(`/packs/${id}/status.json`));
      return {
        connectome_id: id,
        local_total_bytes: 0,
        remote_raw_size: 0,
        remote_to_local_ratio: null,
        cache_recommendation_gb: 0,
        hard_cache_ceiling_gb: 10,
        tiers: {},
        notes: `Static Pages snapshot · ${status.neurons || 0} neurons catalogued (EM stays remote).`,
      };
    }
    return get<StreamingManifest>(`/api/connectomes/${id}/streaming`);
  },

  storage: () => (STATIC ? get<StorageStatus>(dataUrl("/storage.json")) : get<StorageStatus>("/api/storage")),

  clearCache: async (_kinds?: string) => {
    if (STATIC) {
      return { status: await api.storage() };
    }
    return post<{ status: StorageStatus }>(`/api/storage/clear${_kinds ? `?kinds=${_kinds}` : ""}`);
  },

  neurons: async (id: string, q = "", limit = 200, offset = 0) => {
    if (STATIC) {
      const rows = await loadNeurons(id);
      return filterNeurons(rows, q, limit, offset);
    }
    return get<{ total: number; neurons: NeuronIndexRow[]; offset?: number; limit?: number }>(
      `/api/connectomes/${id}/neurons?limit=${limit}&offset=${offset}&q=${encodeURIComponent(q)}`,
    );
  },

  neuron: async (id: string, sourceId: number) => {
    if (STATIC) {
      try {
        return await getJson<Record<string, unknown>>(dataUrl(`/packs/${id}/neurons/${sourceId}.json`));
      } catch {
        const rows = await loadNeurons(id);
        const row = rows.find((n) => n.source_id === sourceId);
        return {
          connectome_id: id,
          neuron: { neuron_id: sourceId, name: row?.name, type: row?.cell_type },
          index: row || null,
          partners: [],
          upstream: [],
          downstream: [],
        };
      }
    }
    return get<Record<string, unknown>>(`/api/connectomes/${id}/neurons/${sourceId}`);
  },

  partners: async (id: string, sourceId: number) => {
    if (STATIC) {
      try {
        return await getJson<{ upstream: Record<string, unknown>[]; downstream: Record<string, unknown>[] }>(
          dataUrl(`/packs/${id}/partners/${sourceId}.json`),
        );
      } catch {
        const edges = await loadEdges(id);
        const upstream = edges
          .filter((e) => Number(e.post_neuron_id) === sourceId)
          .slice(0, 40)
          .map((e) => ({
            partner_id: e.pre_neuron_id,
            synapse_count: e.synapse_count ?? 1,
            direction: "in",
            pre_neuron_id: e.pre_neuron_id,
            post_neuron_id: e.post_neuron_id,
          }));
        const downstream = edges
          .filter((e) => Number(e.pre_neuron_id) === sourceId)
          .slice(0, 40)
          .map((e) => ({
            partner_id: e.post_neuron_id,
            synapse_count: e.synapse_count ?? 1,
            direction: "out",
            pre_neuron_id: e.pre_neuron_id,
            post_neuron_id: e.post_neuron_id,
          }));
        return { upstream, downstream };
      }
    }
    return get<{ upstream: Record<string, unknown>[]; downstream: Record<string, unknown>[] }>(
      `/api/connectomes/${id}/neurons/${sourceId}/partners`,
    );
  },

  skeletonsBatch: (id: string, limit = 200) => {
    if (STATIC) {
      return getJson<SkeletonBatch>(dataUrl(`/packs/${id}/skeletons/batch.json`)).then((b) => ({
        ...b,
        neurons: (b.neurons || []).slice(0, limit),
        count: Math.min(b.count || 0, limit),
      }));
    }
    return get<SkeletonBatch>(`/api/connectomes/${id}/skeletons/batch?limit=${limit}&lod=true`);
  },

  skeleton: async (id: string, sourceId: number) => {
    if (STATIC) {
      return getJson<{
        source_id: number;
        line_segments?: number[];
        n_vertices: number;
        meta?: Record<string, unknown>;
      }>(dataUrl(`/packs/${id}/skeletons/${sourceId}.json`));
    }
    return get<{
      source_id: number;
      line_segments?: number[];
      n_vertices: number;
      meta?: Record<string, unknown>;
    }>(`/api/connectomes/${id}/neurons/${sourceId}/skeleton?lod=true`);
  },

  path: async (id: string, source: number, target: number) => {
    if (STATIC) {
      const edges = await loadEdges(id);
      const path = bfsPath(edges, source, target);
      return { path, found: path != null };
    }
    return get<{ path: number[] | null; found: boolean }>(
      `/api/connectomes/${id}/paths?source=${source}&target=${target}`,
    );
  },

  synapses: async (id: string, limit = 50) => {
    if (STATIC) {
      return { total: 0, synapses: [] as Record<string, unknown>[] };
    }
    return get<{ total: number; synapses: Record<string, unknown>[] }>(
      `/api/connectomes/${id}/synapses?limit=${limit}`,
    );
  },

  synapseEm: async (_id: string, _index: number) => {
    if (STATIC) {
      throw new Error("EM evidence cutouts require the local studio (HDF access).");
    }
    return get<{
      synapse: Record<string, unknown>;
      mid_slice_shape: number[];
      mid_slice_b64: string;
      note: string;
    }>(`/api/connectomes/${_id}/synapses/${_index}/em`);
  },

  exportNeuroglancer: async (_id: string) => {
    if (STATIC) {
      throw new Error("Neuroglancer export requires the local studio.");
    }
    return post<{ path: string }>(`/api/connectomes/${_id}/export-neuroglancer`);
  },

  autonomyStatus: () =>
    STATIC
      ? getJson<AutonomyStatus>(dataUrl("/autonomy.json"))
      : get<AutonomyStatus>("/api/autonomy/status"),

  autonomyRun: async (_autoIngest = true) => {
    if (STATIC) {
      throw new Error("Autonomy ingestion runs locally only. Use: insectome autonomy run");
    }
    return post<{
      report: Record<string, unknown>;
      ingested_packs: string[];
      status_md: string;
    }>(`/api/autonomy/run?auto_ingest=${_autoIngest}`);
  },
};

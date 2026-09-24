# Insect Connectome Atlas

Interactive multi-species atlas over Phase 3 connectome packs.

## Run

```bash
# API (from repo root)
pip install -e ".[dev]"
connectome atlas --port 8765

# UI
cd atlas
npm install
npm run dev
```

Open http://127.0.0.1:5173

## Milestone specimens

| Specimen | Pack | What you can do |
|---|---|---|
| Drosophila EPG (primary) | `hemibrain_epg_v0.1` | 50 neuPrint skeletons + synaptic partners |
| Bombus CX projectome | `bombus_terrestris_cx_projectome_v0.1` | 678 CATMAID skeletons (morphology only) |
| CREMI sample A | `cremi_sample_a_v0.2` | Synapses + EM evidence mid-slice cutout |

## Coverage honesty

The UI prints coverage claims such as `LOCAL SYNAPTIC CONNECTOME` or `MORPHOLOGY_ONLY`. Central-complex packs are never labeled whole-brain.

## Streaming (not a warehouse)

Local packs hold Tier-0 metadata + optional Tier-1 skeletons. Raw EM stays remote. See `docs/STREAMING.md` and `reports/STREAMING_CRITERION.md` (hemibrain EPG: millions× remote/local).

## Deep links

- `/species/drosophila?c=hemibrain_epg_v0.1&n=<bodyId>`
- `/compare/drosophila/bumblebee`

# Insectome

Multi-species insect connectome studio — provenance-tracked catalogs, sparse 3D morphology, EM stays remote.

## GitHub Pages (static)

The published site is a **read-only** snapshot: neuron indexes + compact LOD skeletons as JSON (no FastAPI, no bulk EM).

```bash
# Refresh static data from local packs, then build atlas/dist
python -m insectome pages build --base /new-connectome-project/
```

- Workflow: `.github/workflows/pages.yml` builds from committed `atlas/public/data`
- After push to `main`, enable **Settings → Pages → Source: GitHub Actions**
- Site URL: `https://theworker02.github.io/new-connectome-project/`

Local live studio (API + packs) remains:

```bash
python -m insectome open
```

Autonomy ingestion and EM evidence cutouts only work locally.

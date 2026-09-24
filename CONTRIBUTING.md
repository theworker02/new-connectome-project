# Contributing to Insectome

Thanks for helping. Insectome is a **reuse-first, provenance-honest** connectome studio — please keep those constraints when you change code or data.

## Ground rules

1. **No fictional biology** — do not invent synapses, cell types, or merged multi-species graphs.
2. **No bulk EM in-repo** — streaming / evidence ROIs only; respect download guards.
3. **Specimen fidelity** — packs stay tied to a source specimen/dataset; comparative work must not silently merge nodes.
4. **Coverage honesty** — update manifests and `species/*/EVIDENCE.yaml` when access or claims change.
5. **Prefer catalogs over bulk skeletons** — grow neuron counts via index/graph packs when possible.

## Setup

```bash
pip install -e ".[dev,neuprint]"
cd atlas && npm ci
pytest
```

## Common workflows

```bash
# Local studio
insectome open

# After pack or autonomy changes that should appear on Pages
insectome pages export
insectome pages build --base /new-connectome-project/

# Registry / reuse
insectome reuse
insectome autonomy run
```

## Pull requests

- Keep diffs focused; do not commit `data/connectomes/` bulk artifacts or `.env` secrets.
- Do commit refreshed `atlas/public/data/**` when the static site should change.
- Mention which packs / coverage claims you touched.

## License

By contributing you agree your contributions are licensed under the MIT License (see [LICENSE](LICENSE)).

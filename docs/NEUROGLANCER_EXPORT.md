# Neuroglancer export

```bash
connectome export-neuroglancer hemibrain_epg_v0.1
```

Writes `data/neuroglancer/<id>/`:

- `skeletons/*.json` — portable LOD skeletons
- `annotations/soma_annotations.json`
- `properties/info` — segment properties
- `viewer_state.json` — shareable state

Raw EM precomputed volumes are intentionally omitted (remote-only policy). Host the folder over HTTP for static inspection; convert to sharded precomputed when EM access exists.

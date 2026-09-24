# Neuron viewer

Primary 3D representation: **batched skeletons** (LOD).

## Interaction

- Click / select from list → neuron panel
- Isolate → hide non-related neurons
- Show partners → color upstream (blue) / downstream (amber)
- Provenance panel → source dataset / specimen / limitations
- EM evidence → CREMI ROI mid-slice only

## Levels of detail

1. Skeleton LOD (`.lod.skbin`) — default atlas stream
2. Full skeleton (`.skbin`) — on demand via API `?lod=false`
3. Meshes — not required for milestone 1

## Performance

Skeletons are merged into a single `THREE.LineSegments` buffer with vertex colors. Do not instantiate one mesh object per segment.

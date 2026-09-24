# Connectome API

Base: `http://127.0.0.1:8765`

| Method | Path |
|---|---|
| GET | `/api/species` |
| GET | `/api/species/{key}` |
| GET | `/api/connectomes` |
| GET | `/api/connectomes/{id}` |
| GET | `/api/connectomes/{id}/neurons?q=&limit=&offset=` |
| GET | `/api/connectomes/{id}/neurons/{source_id}` |
| GET | `/api/connectomes/{id}/neurons/{source_id}/partners` |
| GET | `/api/connectomes/{id}/neurons/{source_id}/skeleton?lod=true` |
| GET | `/api/connectomes/{id}/skeletons/batch?limit=` |
| GET | `/api/connectomes/{id}/paths?source=&target=` |
| GET | `/api/connectomes/{id}/synapses` |
| GET | `/api/connectomes/{id}/synapses/{i}/em` (CREMI) |
| POST | `/api/connectomes/{id}/export-neuroglancer` |
| GET | `/api/atlas/status` |

All list endpoints are paginated / limited. Dense whole-connectome dumps are rejected by design.

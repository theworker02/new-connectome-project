"""neuPrint remote adapter — query API; never clone the database."""

from __future__ import annotations

import os
from typing import Any

from insectome.atlas.skeletons import skeleton_from_neuprint_df, skeleton_to_json
from insectome.remote import HEMIBRAIN_REMOTE_BYTES, RemoteVolume, VolumeMeta
from insectome.storage.cache import InsectomeCache


class NeuPrintRemote(RemoteVolume):
    provider = "neuprint"

    def __init__(self, dataset: str = "hemibrain:v1.2.1", cache: InsectomeCache | None = None):
        self.dataset = dataset
        self.cache = cache or InsectomeCache()
        self._client = None

    def _client_or_raise(self):
        token = os.environ.get("NEUPRINT_APPLICATION_CREDENTIALS") or os.environ.get("NEUPRINT_TOKEN")
        if not token:
            raise RuntimeError("NEUPRINT_APPLICATION_CREDENTIALS required for remote neuPrint fetch")
        if self._client is None:
            from neuprint import Client

            self._client = Client("neuprint.janelia.org", dataset=self.dataset, token=token)
        return self._client

    def get_metadata(self) -> VolumeMeta:
        healthy = True
        try:
            self._client_or_raise()
        except Exception:
            healthy = bool(os.environ.get("NEUPRINT_APPLICATION_CREDENTIALS") or os.environ.get("NEUPRINT_TOKEN"))
        return VolumeMeta(
            provider=self.provider,
            dataset=self.dataset,
            remote_raw_bytes=HEMIBRAIN_REMOTE_BYTES if "hemibrain" in self.dataset else None,
            notes="Query neuPrint API on demand — do not clone. EM stays on Janelia/NG hosts.",
            healthy=healthy,
        )

    def get_skeleton(self, neuron_id: int | str) -> dict[str, Any]:
        key = f"neuprint:skeleton:{self.dataset}:{neuron_id}"
        cached = self.cache.get_bytes(key)
        if cached is not None:
            import json

            return json.loads(cached.decode("utf-8"))
        from neuprint import fetch_skeleton

        sk = fetch_skeleton(int(neuron_id), client=self._client_or_raise())
        verts, links = skeleton_from_neuprint_df(sk)
        payload = skeleton_to_json(verts, links, max_vertices=1200)
        payload["source_id"] = int(neuron_id)
        payload["provider"] = self.provider
        payload["dataset"] = self.dataset
        import json

        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.cache.put_bytes(key, raw, kind="skeleton", source=f"neuprint://{self.dataset}/{neuron_id}")
        return payload

    def get_synapses(self, neuron_id: int | str) -> list[dict[str, Any]]:
        # Adjacency weights only in compact mode — full synapse loci remain remote
        return []

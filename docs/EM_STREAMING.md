# EM streaming (zero-copy)

- Tier-3 only: disposable cutouts via `RemoteVolume.get_em_cutout`.
- CREMI: HDF ROI via `CremiRemote` → cache kind `em_chunk`.
- neuPrint/Neuroglancer: EM remains on host infrastructure; we store pointers + optional evidence ROI.
- DANDI/Zarr/N5: adapter stubs use HTTP Range when available (do not whole-file download).

Policy: DOWNLOAD CHUNK → DISPLAY → EVICT under budget.

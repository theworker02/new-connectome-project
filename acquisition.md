# Acquisition

**Bug Connectome Project** ships as the **Insectome** studio in this repository  
([`new-connectome-project`](https://github.com/theworker02/new-connectome-project)).

This page is the short acquisition path: clone → install → browse packs.  
For philosophy, pack inventory, and architecture see the root [README](README.md).

---

## What you get

| Artifact | Where | Size class |
|---|---|---|
| Studio source (Python + React) | this repo | small |
| Static Pages snapshot | `atlas/public/data/` | ~23 MB |
| Local connectome packs | `data/connectomes/` (gitignored) | ~1.7 GB when fully populated |
| Live demo | [GitHub Pages](https://theworker02.github.io/new-connectome-project/) | read-only |

You do **not** download EM volumes. Raw EM stays remote.

---

## Prerequisites

| Tool | Version |
|---|---|
| Python | ≥ 3.11 |
| Node.js | ≥ 18 (only to rebuild UI) |
| Git | any recent |
| Optional | neuPrint token for LEVEL-0 imports |

---

## 1. Clone

```bash
git clone https://github.com/theworker02/new-connectome-project.git
cd new-connectome-project
```

---

## 2. Python environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -e ".[dev,neuprint]"
```

Copy secrets template (optional, for neuPrint):

```bash
cp .env.example .env
# edit .env → NEUPRINT_APPLICATION_CREDENTIALS or NEUPRINT_TOKEN
```

---

## 3. Open the studio (one command)

```bash
insectome open
```

This builds `atlas/dist` if needed, starts the API on `127.0.0.1:8765`, and opens the browser.

Alternatives:

```bash
# Windows double-click
scripts\open-studio.bat

# Make
make studio
```

---

## 4. Browse without local packs (Pages)

If you only need the public snapshot:

**https://theworker02.github.io/new-connectome-project/**

No install required. Autonomy / EM cutouts / cache controls are local-only.

---

## 5. Populate or refresh packs (optional)

```bash
# Score registry before any download
insectome reuse

# LEVEL-0 typed subgraph (needs neuPrint token)
insectome import-hemibrain --type-regex "EPG.*"

# CREMI LEVEL-1 annotations
insectome import-cremi --authorize-download

# Autonomous dense catalogs (graph/index only)
insectome autonomy run
```

Rebuild indexes after imports:

```bash
insectome connectome rebuild-catalog
```

---

## 6. Publish / refresh static site (optional)

```bash
insectome pages export
insectome pages build --base /new-connectome-project/
git add atlas/public/data
git commit -m "Refresh Pages snapshot"
git push
```

Or: `scripts\build-pages.bat` / `make pages-build`.

---

## Verification checklist

- [ ] `insectome --help` prints the CLI
- [ ] `insectome open` serves `http://127.0.0.1:8765`
- [ ] Home shows packs (local) or Pages shows the static catalog
- [ ] `insectome cache status` reports soft/hard limits (≤10 GB hard)
- [ ] No multi-GB EM files under the repo

---

## Citation

See [CITATION.cff](CITATION.cff). Cite **upstream datasets** for science; cite this software for the studio/tooling.

```bash
# Machine-readable
# CITATION.cff at repo root — GitHub “Cite this repository”
```

---

## Support paths

| Need | Go to |
|---|---|
| Everyday commands | [examples/cli-cheatsheet.md](examples/cli-cheatsheet.md) |
| neuPrint import | [examples/recipes/import-neuprint.md](examples/recipes/import-neuprint.md) |
| Autonomy | [examples/recipes/autonomy-cycle.md](examples/recipes/autonomy-cycle.md) |
| Docs hub | [docs/README.md](docs/README.md) |
| Issues | GitHub Issues on this repo |

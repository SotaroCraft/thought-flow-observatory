# Data directory

## Public vs private

| Path | Git | Contents |
|---|---|---|
| `data/samples/` | Tracked | Public-safe or synthetic minimal samples only |
| `workspace-data/` | Ignored | Local Raw, Canonical, results, manifests (source of truth for runs) |

## Rules

- Do **not** commit credentials, Tenant IDs, personal data, business secrets, or redistributability-unclear Raw.
- Prefer DOI / URL / metadata for papers; do not add PDFs with unclear redistribution rights.
- Real sensor Raw from later milestones stays under the configured local data root unless a rights-cleared sample is explicitly approved for `data/samples/`.

## M1 sample

`samples/m1_synthetic_raw.json` is a synthetic fixture used by `thought-flow smoke`.

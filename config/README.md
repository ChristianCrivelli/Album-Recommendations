# config/

Database schema and override reference material for the ingestion pipeline
(not application config in the environment-variable sense — those are
documented in the root [README.md](../README.md#running-it) and
`.env.example`).

- `schema.sql` — the full Supabase table layout (`albums`, `artists`, `tags`,
  `album_contributions`, `album_tags`, `manual_overrides`, `failed_lookups`).
- `manual_override_examples.sql` — example rows for both `manual_overrides`
  modes (search-hint vs. full-manual skip).
- `queries/` — one-off and migration SQL run directly against Supabase over
  the project's history (kept as a record, not re-run automatically).

Required environment variables (Notion, Supabase, MusicBrainz, Spotify) are
listed in the root README's "Running it" section and mirrored in
`.env.example` at the repo root.

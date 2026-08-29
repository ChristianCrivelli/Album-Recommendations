-- Issue #11 (public repo): Spotify integration, three angles picked:
--  1. Fallback metadata enrichment for albums MusicBrainz can't find
--  2. Cover art fallback when Cover Art Archive 404s
--  3. Spotify album ID to power the #12 in-app preview embed
-- All three are populated by the ingestion pipeline
-- (src/ingestion/spotify_client.py), never looked up live by the
-- public-facing backend, so the webapp never needs its own Spotify
-- credentials or a live API call on the request path.
--
-- Applied directly against Supabase on 2026-08-29 (via the Supabase MCP
-- tool's apply_migration, migration name add_spotify_fallback_columns_to_albums).
-- Kept here as a record, same as the other files in this folder.

ALTER TABLE public.albums
  ADD COLUMN IF NOT EXISTS spotify_album_id text,
  ADD COLUMN IF NOT EXISTS spotify_cover_url text,
  ADD COLUMN IF NOT EXISTS metadata_source text;

COMMENT ON COLUMN public.albums.spotify_album_id IS 'Spotify album ID (not MBID) — set when this row was resolved via Spotify fallback (metadata_source = ''spotify''), or backfilled for MusicBrainz-sourced rows solely to power the #12 in-app preview embed. Build the embed URL as https://open.spotify.com/embed/album/{id}.';
COMMENT ON COLUMN public.albums.spotify_cover_url IS 'Precomputed fallback cover image URL from Spotify, set only when Cover Art Archive (coverartarchive.org/release-group/{mbid}) was probed at ingestion time and found to 404. NULL means the CAA URL computed from mbid is expected to work.';
COMMENT ON COLUMN public.albums.metadata_source IS 'Provenance of this row''s metadata: NULL/''musicbrainz'' (default, pre-existing rows), ''manual'' (manual_overrides with skip_musicbrainz), or ''spotify'' (MusicBrainz had no match, Spotify fallback succeeded).';

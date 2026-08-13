-- Run this once against your Supabase project to add manual-override support
-- to the ingestion pipeline. Safe to run on an existing database — it only
-- adds a new table, nothing else is touched.
--
-- Two independent ways to use a row in this table, keyed by the exact
-- Notion `title` (same key the rest of the pipeline uses):
--
-- 1. SEARCH-HINT override (skip_musicbrainz = false):
--    The album IS on MusicBrainz, but the Notion title/artist text doesn't
--    match well enough for get_metadata() to find it confidently (typo,
--    alternate spelling, parenthetical noise, etc). Set search_title and/or
--    search_artist to the corrected query text — the normal MusicBrainz
--    enrichment (tags, mbid, producers, avg length) still runs, just with
--    better search terms. Prefer this over full manual entry whenever
--    possible, since you keep all the automatically-derived metadata.
--
-- 2. FULL MANUAL override (skip_musicbrainz = true):
--    The album genuinely isn't on MusicBrainz at all (common for small/DIY/
--    SoundCloud-first artists). MusicBrainz is skipped entirely and the
--    manual_* columns below are used as-is. The resulting album row has
--    mbid = NULL and no producer data (MusicBrainz is the only producer
--    source this pipeline has).

CREATE TABLE public.manual_overrides (
  title text PRIMARY KEY,                    -- must match the Notion title exactly

  -- Search-hint fields (ignored if skip_musicbrainz = true)
  search_title text,                         -- corrected title to search MusicBrainz with
  search_artist text,                        -- corrected artist string to search MusicBrainz with

  -- Full-manual fields (ignored if skip_musicbrainz = false)
  skip_musicbrainz boolean NOT NULL DEFAULT false,
  manual_primary_type text,
  manual_release_year text,
  manual_avg_length numeric,
  manual_tags text[],                        -- e.g. '{hyperpop,bedroom pop}'
  manual_artist_names text[],                -- artist NAMES only — no MBIDs exist for these by definition

  notes text,                                -- why this override exists / where you sourced the metadata
  created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now())
);

-- Add to database_info/schema.sql alongside the other CREATE TABLEs once
-- you've run this, so schema.sql stays an accurate full reference.
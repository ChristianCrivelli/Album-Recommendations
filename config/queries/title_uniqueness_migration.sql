-- Migration for issue #14: "albums.title unique constraint breaks when
-- different real albums share a title."
--
-- NOT YET APPLIED. Prepared for review — run manually against Supabase
-- (SQL editor, or `supabase db execute`) once you're happy with it.
--
-- --------------------------------------------------------------------------
-- Background
-- --------------------------------------------------------------------------
-- albums.title has a plain UNIQUE constraint (albums_title_key). Two
-- different real albums by different artists can legitimately share an
-- exact title — confirmed cases: "The Purple Album" (Young Thug vs. an
-- unrelated release) and "Welcome to the Future" (Future vs. several
-- unrelated artists). Today only one can be stored correctly; the other's
-- data is blocked. This same constraint is also what caused the FULL_SYNC
-- crash on 2026-08-21 (~15 titles hit "duplicate key value violates unique
-- constraint albums_title_key" when an upsert keyed on mbid tried to INSERT
-- a new mbid and had nothing to conflict on).
--
-- Verified against live data before writing this (2026-08-25): zero titles
-- currently have duplicate rows in `albums`, and 116 of 117 manual_overrides
-- rows already carry a usable artist value in either manual_artist_names or
-- search_artist. So this migration makes no assumption that turns out to be
-- false today — see the design notes below for why it still doesn't force a
-- backfill.
--
-- --------------------------------------------------------------------------
-- Design
-- --------------------------------------------------------------------------
-- `mbid` (already UNIQUE, unaffected by this migration) stays the identity
-- key for MusicBrainz-backed albums — dropping the plain title constraint
-- lets two different real albums with different mbids share a title with no
-- conflict, which is the correct behavior. album_push_logic.py's main
-- upsert already keys on mbid; no code change needed there beyond this
-- constraint drop.
--
-- manual_overrides rows have no mbid by definition (skip_musicbrainz=true),
-- so title was its only lookup/dedup key. Re-keying it outright to
-- (title, artist) would require backfilling every existing row's artist
-- value right now, including titles that never actually collide — real
-- risk for zero benefit today. Instead: add a nullable `artist` column and
-- a (title, artist) uniqueness rule that only matters once a second row for
-- the same title actually shows up. All 117 existing rows keep `artist`
-- NULL and keep working exactly as before (ingestion/manual_overrides.py's
-- get_override() only consults `artist` when more than one row shares a
-- title). Fill in `artist` only when you deliberately add a second override
-- for a title that's a genuine collision.
--
-- --------------------------------------------------------------------------
-- Migration
-- --------------------------------------------------------------------------

-- 1. albums: drop the plain per-title uniqueness. mbid's own UNIQUE
--    constraint continues to guarantee one row per real MusicBrainz release.
ALTER TABLE public.albums DROP CONSTRAINT IF EXISTS albums_title_key;

-- 2. manual_overrides: replace the title-only primary key with a surrogate
--    id (matching every other table in this schema), add a nullable
--    `artist` column, and enforce (title, artist) uniqueness via an
--    expression index — COALESCE(artist, '') so existing NULL-artist rows
--    are still protected against accidental exact duplicates, without
--    requiring every row to have `artist` populated up front.
ALTER TABLE public.manual_overrides
  ADD COLUMN IF NOT EXISTS id uuid NOT NULL DEFAULT uuid_generate_v4();

ALTER TABLE public.manual_overrides
  ADD COLUMN IF NOT EXISTS artist text;

ALTER TABLE public.manual_overrides DROP CONSTRAINT IF EXISTS manual_overrides_pkey;

ALTER TABLE public.manual_overrides ADD CONSTRAINT manual_overrides_pkey PRIMARY KEY (id);

CREATE UNIQUE INDEX IF NOT EXISTS manual_overrides_title_artist_key
  ON public.manual_overrides (title, COALESCE(artist, ''));

-- --------------------------------------------------------------------------
-- Using this going forward
-- --------------------------------------------------------------------------
-- To add an override for a title that's a genuine collision with an
-- existing override/album, set `artist` on the new row (same comma-joined
-- format as everywhere else in the pipeline, e.g. 'Young Thug' or
-- 'JACKBOYS, Travis Scott') so ingestion/manual_overrides.py's get_override()
-- can tell the two apart. Existing rows don't need any changes.

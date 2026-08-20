-- Resolves the three Supabase advisor findings tracked as issues #7, #8, #9
-- in Album-Recommendations-Public, plus data cleanup for part of #15.
-- Already applied against the live project as of 2026-08-18 — kept here as
-- a record and so a fresh database (or a restore) can be brought to the
-- same state. Every statement below is safe to re-run (idempotent).

-- --------------------------------------------------------------------------
-- #7: open_bad_eggs view uses SECURITY DEFINER — switch to SECURITY INVOKER
-- --------------------------------------------------------------------------
-- SECURITY DEFINER views run with the privileges (and RLS bypass) of the
-- view's owner rather than the querying user. This view only reads
-- failed_lookups, which the ingestion pipeline already accesses with the
-- service-role key (RLS doesn't apply to it) — there's no reason for the
-- view itself to also run definer-style. SECURITY INVOKER (Postgres 15+;
-- this project is on 17) makes it respect the querying role's own RLS
-- instead, which is the safer default.
ALTER VIEW public.open_bad_eggs SET (security_invoker = true);

-- --------------------------------------------------------------------------
-- #8: set_updated_at() has a mutable search_path
-- --------------------------------------------------------------------------
-- Trigger functions with no fixed search_path can be tricked into resolving
-- an object in a schema an attacker controls, if such a schema is ever
-- placed earlier in search_path than 'public'. This function only calls
-- timezone(), a pg_catalog builtin that resolves regardless of search_path,
-- so pinning it to empty is a pure hardening move with no behavior change.
ALTER FUNCTION public.set_updated_at() SET search_path = '';

-- --------------------------------------------------------------------------
-- #9: missing indexes on album_contributions.person_id / album_tags.tag_id
-- --------------------------------------------------------------------------
-- Both foreign keys are queried in the reverse direction (recommendations
-- and the public API look up "everything for this artist / this tag") and
-- were doing a sequential scan of album_contributions / album_tags to do
-- it. Tables are small (~1,200 albums worth of links), so a plain index
-- build is fine — no need for CREATE INDEX CONCURRENTLY here.
CREATE INDEX IF NOT EXISTS idx_album_contributions_person_id
  ON public.album_contributions (person_id);

CREATE INDEX IF NOT EXISTS idx_album_tags_tag_id
  ON public.album_tags (tag_id);

-- --------------------------------------------------------------------------
-- Issue #10 (Public repo, closed): "Confirm intentional no-policy RLS on
-- failed_lookups and manual_overrides" — no SQL change. Confirmed
-- intentional: album_push_logic.py connects with the service-role key
-- (bypasses RLS), and backend/main.py's SUPABASE_KEY is explicitly a
-- read-only key with no SELECT policy granted on either table.
-- --------------------------------------------------------------------------

-- --------------------------------------------------------------------------
-- Issue #15, sub-item: "Fuse Hip Hop and Hip-Hop into one tag"
-- --------------------------------------------------------------------------
-- ingestion/cleaning_methods.py's TAG_MAPPING normalizes both "Hip Hop" and
-- "Hip-Hop" to the same canonical "hip-hop" string going forward, but that
-- only runs at ingestion time — the two tag rows created before that
-- normalization existed needed a one-time merge:
--   'hip hop'  -> d36f794f-4d7a-488b-bc6e-6d27f9d1c829  (stale, now deleted)
--   'hip-hop'  -> 1db5b422-5167-43f1-96e1-6be5b8686ff0  (canonical, kept)
INSERT INTO public.album_tags (album_id, tag_id)
SELECT album_id, '1db5b422-5167-43f1-96e1-6be5b8686ff0'
FROM public.album_tags
WHERE tag_id = 'd36f794f-4d7a-488b-bc6e-6d27f9d1c829'
ON CONFLICT (album_id, tag_id) DO NOTHING;

DELETE FROM public.album_tags WHERE tag_id = 'd36f794f-4d7a-488b-bc6e-6d27f9d1c829';
DELETE FROM public.tags WHERE id = 'd36f794f-4d7a-488b-bc6e-6d27f9d1c829';

-- --------------------------------------------------------------------------
-- Issue #15, sub-items: wrong artist attributions
-- --------------------------------------------------------------------------
-- Notion is the source of truth for Artist(s); MusicBrainz matched all
-- three of these to the wrong act. search_artist overrides tell the
-- pipeline what to actually search MusicBrainz with (search-hint mode —
-- MusicBrainz enrichment still runs, just with corrected search terms).
INSERT INTO manual_overrides (title, search_artist, notes) VALUES
  ('Bangers and Mash', 'LYVIA', 'Pipeline previously matched wrong artist (The Explorer''s Collective) on MusicBrainz. Correct artist confirmed by Chris: LYVIA.'),
  ('$ad Boy', 'TOB Duke', 'Pipeline previously matched wrong artist (Madalen Duke) on MusicBrainz. Correct artist per Notion source-of-truth: TOB Duke.'),
  ('Wave Control', 'Tom. G', 'Pipeline previously matched wrong artist (Tom Peters) on MusicBrainz. Correct artist per Notion source-of-truth: Tom. G.')
ON CONFLICT (title) DO UPDATE SET search_artist = EXCLUDED.search_artist, notes = EXCLUDED.notes;

-- Run this once against the Supabase project to resolve the three advisor
-- findings tracked as issues #7, #8, #9 in Album-Recommendations-Public.
-- Safe to run on the existing database — no data is touched, only a view's
-- security mode, a function's search_path, and two new indexes.

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
-- currently do a sequential scan of album_contributions / album_tags to do
-- it. Tables are small (~1,200 albums worth of links), so a plain index
-- build is fine — no need for CREATE INDEX CONCURRENTLY here.
CREATE INDEX IF NOT EXISTS idx_album_contributions_person_id
  ON public.album_contributions (person_id);

CREATE INDEX IF NOT EXISTS idx_album_tags_tag_id
  ON public.album_tags (tag_id);

-- --------------------------------------------------------------------------
-- Issue #10 (Public repo): "Confirm intentional no-policy RLS on
-- failed_lookups and manual_overrides" — no SQL change needed here.
-- Confirmed intentional: album_push_logic.py connects with the service-role
-- key (bypasses RLS), and backend/main.py's SUPABASE_KEY is explicitly a
-- read-only key with no SELECT policy granted on either table. RLS-enabled/
-- no-policy is exactly the "deny all except service role" posture you want
-- for two tables that are pipeline-internal bookkeeping, not app-facing
-- data. Recommend closing #10 with this explanation rather than adding
-- policies.

-- --------------------------------------------------------------------------
-- Public-repo issue #15 ("Formatting issue"), sub-item: "Fuse Hip Hop and
-- Hip-Hop into one tag"
-- --------------------------------------------------------------------------
-- ingestion/cleaning_methods.py's TAG_MAPPING already normalizes both
-- "Hip Hop" and "Hip-Hop" to the same canonical "hip-hop" string going
-- forward — but that only runs at ingestion time, so the two tag rows that
-- were created before this normalization existed are still sitting in the
-- table separately today:
--   'hip hop'  -> d36f794f-4d7a-488b-bc6e-6d27f9d1c829
--   'hip-hop'  -> 1db5b422-5167-43f1-96e1-6be5b8686ff0  (canonical)
-- Repoint every album_tags link from the stale tag to the canonical one,
-- then drop the now-empty stale tag row. ON CONFLICT DO NOTHING handles any
-- album that (unusually) already has both tags linked.
INSERT INTO public.album_tags (album_id, tag_id)
SELECT album_id, '1db5b422-5167-43f1-96e1-6be5b8686ff0'
FROM public.album_tags
WHERE tag_id = 'd36f794f-4d7a-488b-bc6e-6d27f9d1c829'
ON CONFLICT (album_id, tag_id) DO NOTHING;

DELETE FROM public.album_tags WHERE tag_id = 'd36f794f-4d7a-488b-bc6e-6d27f9d1c829';
DELETE FROM public.tags WHERE id = 'd36f794f-4d7a-488b-bc6e-6d27f9d1c829';

-- --------------------------------------------------------------------------
-- Public-repo issue #15, sub-items: wrong artist attributions
-- --------------------------------------------------------------------------
-- "Bangers and Mash" (The Explorer's Collective -> should be LYVIA), "$ad
-- Boy" (not by Madalen Duke), "Wave Control" (not by Tom Peters) — these are
-- MusicBrainz mismatches, exactly what manual_overrides exists for (see
-- config/manual_override_examples.sql for the pattern). Left as a
-- scaffold rather than filled in: I don't have a source to confirm what the
-- *correct* artist/search terms actually are for these three — fill in
-- search_artist (if MusicBrainz has the right release under a different
-- artist listing) or the manual_* fields (if it's not on MusicBrainz at
-- all) once you've checked, then run this block.
--
-- INSERT INTO manual_overrides (title, search_artist, notes) VALUES
--   ('Bangers and Mash', 'LYVIA', 'Notion/pipeline matched wrong artist (The Explorer''s Collective) — confirm LYVIA is correct before running.'),
--   ('$ad Boy', '<correct artist>', 'Currently mismatched to Madalen Duke — fill in correct artist.'),
--   ('Wave Control', '<correct artist>', 'Currently mismatched to Tom Peters — fill in correct artist.')
-- ON CONFLICT (title) DO UPDATE SET search_artist = EXCLUDED.search_artist, notes = EXCLUDED.notes;

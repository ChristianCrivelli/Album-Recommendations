-- Example rows for database_info/migrations/manual_overrides.sql, covering
-- the failed_lookups.csv entries diagnosed in this conversation. Edit
-- values before running — these are starting points, not verified facts.

-- SEARCH-HINT example: "1 Doulbe 0" is a typo in Notion for "1 Double 0"
-- (That Mexican OT, 2021 mixtape) — MusicBrainz has the real thing, the
-- search text just needs correcting. Prefer fixing the typo directly in
-- Notion; this row is a stopgap that works either way (once Notion is
-- fixed, this override becomes a harmless no-op since search_title will
-- match the corrected title anyway).
INSERT INTO manual_overrides (title, search_title, search_artist, notes)
VALUES (
  '1 Doulbe 0',
  '1 Double 0',
  'That Mexican OT',
  'Typo in Notion title — should be "1 Double 0". Fix Notion when convenient.'
)
ON CONFLICT (title) DO UPDATE SET
  search_title = EXCLUDED.search_title,
  search_artist = EXCLUDED.search_artist,
  notes = EXCLUDED.notes;

-- FULL-MANUAL example: donavns is a small SoundCloud/bedroom-pop artist —
-- "MoveDon" is a real 2024 EP (confirmed on Spotify/Deezer) but isn't
-- indexed on MusicBrainz at all. Fill in tags/year by ear/by hand.
INSERT INTO manual_overrides (
  title, skip_musicbrainz, manual_primary_type, manual_release_year,
  manual_tags, manual_artist_names, notes
)
VALUES (
  'MoveDon',
  true,
  'EP',
  '2024',
  ARRAY['bedroom pop', 'hyperpop'],   -- adjust to taste
  ARRAY['donavns'],
  'Not on MusicBrainz — small/DIY artist. Confirmed real release via Spotify/Deezer.'
)
ON CONFLICT (title) DO UPDATE SET
  skip_musicbrainz = EXCLUDED.skip_musicbrainz,
  manual_primary_type = EXCLUDED.manual_primary_type,
  manual_release_year = EXCLUDED.manual_release_year,
  manual_tags = EXCLUDED.manual_tags,
  manual_artist_names = EXCLUDED.manual_artist_names,
  notes = EXCLUDED.notes;

-- Same donavns EP appears twice in failed_lookups under different titles —
-- check whether "Summer Of Separation" is the same release or a different
-- one before adding it here; don't assume from the title alone.

-- Repeat the FULL-MANUAL pattern above for the other likely DIY/SoundCloud
-- artists in failed_lookups.csv (underscores, glaive, Caleb Gordon) once
-- you've confirmed each release is real and gathered your own tags/year —
-- don't guess at their metadata on their behalf.
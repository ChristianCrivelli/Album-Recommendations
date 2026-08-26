-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.album_contributions (
  album_id uuid NOT NULL,
  person_id uuid NOT NULL,
  role text NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  CONSTRAINT album_contributions_pkey PRIMARY KEY (album_id, person_id, role),
  CONSTRAINT album_contributions_album_id_fkey FOREIGN KEY (album_id) REFERENCES public.albums(id),
  CONSTRAINT album_contributions_person_id_fkey FOREIGN KEY (person_id) REFERENCES public.artists(id)
);
CREATE TABLE public.album_tags (
  album_id uuid NOT NULL,
  tag_id uuid NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  CONSTRAINT album_tags_pkey PRIMARY KEY (album_id, tag_id),
  CONSTRAINT album_tags_album_id_fkey FOREIGN KEY (album_id) REFERENCES public.albums(id),
  CONSTRAINT album_tags_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES public.tags(id)
);
CREATE TABLE public.albums (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  -- title is intentionally NOT unique (issue #14) — two different real
  -- albums by different artists can legitimately share an exact title.
  -- mbid (below) is the real identity key for MusicBrainz-backed rows.
  -- See database_info/queries/title_uniqueness_migration.sql.
  title text NOT NULL,
  mbid text UNIQUE,
  rating numeric,
  primary_type text,
  release_year text,
  avg_length numeric,
  created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  CONSTRAINT albums_pkey PRIMARY KEY (id)
);
CREATE TABLE public.artists (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  name text NOT NULL,
  mbid text UNIQUE,
  created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  CONSTRAINT artists_pkey PRIMARY KEY (id)
);
CREATE TABLE public.tags (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  name text NOT NULL UNIQUE,
  created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  CONSTRAINT tags_pkey PRIMARY KEY (id)
);
CREATE TABLE public.manual_overrides (
  -- Re-keyed on a surrogate id (issue #14) — title alone stopped being a
  -- safe primary key once two different real albums were confirmed to
  -- share a title. `artist` disambiguates the rare case where more than
  -- one override shares a title; NULL for every row today. See
  -- database_info/queries/title_uniqueness_migration.sql.
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  title text NOT NULL,
  artist text,
  search_title text,
  search_artist text,
  skip_musicbrainz boolean NOT NULL DEFAULT false,
  manual_primary_type text,
  manual_release_year text,
  manual_avg_length numeric,
  manual_tags text[],
  manual_artist_names text[],
  notes text,
  created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  CONSTRAINT manual_overrides_pkey PRIMARY KEY (id)
);
-- Plus an expression unique index (can't be expressed as a table CONSTRAINT
-- since it involves COALESCE) — see title_uniqueness_migration.sql:
-- CREATE UNIQUE INDEX manual_overrides_title_artist_key
--   ON public.manual_overrides (title, COALESCE(artist, ''));
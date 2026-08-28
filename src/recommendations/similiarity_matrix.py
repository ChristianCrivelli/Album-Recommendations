import os
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client
from sklearn.preprocessing import MultiLabelBinarizer, MinMaxScaler

load_dotenv()

# ── 1. PULL DATA FROM SUPABASE ───────────────────────────────────────────────

def fetch_data() -> pd.DataFrame:
    """
    Pulls albums and their tags + artists from Supabase and returns
    a single flat DataFrame ready for feature engineering.
    """
    url = os.environ.get("supabase_url")
    key = os.environ.get("supabase_key")
    supabase: Client = create_client(url, key)

    # Albums
    albums_resp = supabase.table("albums").select("id, title, release_year, avg_length, rating").execute()
    albums_df = pd.DataFrame(albums_resp.data)

    # Tags (via junction table)
    tags_resp = (
        supabase.table("album_tags")
        .select("album_id, tags(name)")
        .execute()
    )
    # Group tags by album_id into a list
    tag_rows = [{"album_id": r["album_id"], "tag": r["tags"]["name"]} for r in tags_resp.data]
    tags_df = (
        pd.DataFrame(tag_rows)
        .groupby("album_id")["tag"]
        .apply(list)
        .reset_index()
        .rename(columns={"tag": "tags"})
    )

    # Artists (via junction table, role = 'artist' only)
    artists_resp = (
        supabase.table("album_contributions")
        .select("album_id, artists(mbid)")
        .eq("role", "artist")
        .execute()
    )
    artist_rows = [{"album_id": r["album_id"], "artist_mbid": r["artists"]["mbid"]} for r in artists_resp.data]
    artists_df = (
        pd.DataFrame(artist_rows)
        .groupby("album_id")["artist_mbid"]
        .apply(list)
        .reset_index()
        .rename(columns={"artist_mbid": "artist_mbids"})
    )

    # Merge everything onto the albums base
    df = albums_df.merge(tags_df, left_on="id", right_on="album_id", how="left").drop(columns="album_id")
    df = df.merge(artists_df, left_on="id", right_on="album_id", how="left").drop(columns="album_id")

    # Fill missing lists with empty lists
    df["tags"] = df["tags"].apply(lambda x: x if isinstance(x, list) else [])
    df["artist_mbids"] = df["artist_mbids"].apply(lambda x: x if isinstance(x, list) else [])

    print(f"Loaded {len(df)} albums from Supabase.")
    return df


# ── 2. BUILD FEATURE MATRIX ──────────────────────────────────────────────────

def build_feature_matrix(df: pd.DataFrame):
    """
    Combines tag, numeric, and artist features into a single
    normalised matrix for cosine similarity.
    """

    # --- Tags (MultiLabelBinarizer) ---
    # Each tag becomes its own binary column: 1 if the album has it, 0 if not.
    # This is the right approach for short curated tag lists.
    mlb = MultiLabelBinarizer()
    tag_matrix = mlb.fit_transform(df["tags"])

    # --- Numeric features (release year + avg track length) ---
    # MinMaxScaler squashes both into [0, 1] so neither dominates.
    numeric = df[["release_year", "avg_length"]].fillna(0)
    scaler = MinMaxScaler()
    numeric_matrix = scaler.fit_transform(numeric)

    # --- Artist overlap (MultiLabelBinarizer on MBIDs) ---
    # Two albums sharing an artist/producer gets a meaningful similarity boost.
    artist_mlb = MultiLabelBinarizer()
    artist_matrix = artist_mlb.fit_transform(df["artist_mbids"])

    # --- Combine with weights ---
    # Tags are the strongest signal; artists add a boost for shared collaborators;
    # numeric features provide softer era/length context.
    TAG_WEIGHT    = 2.0
    ARTIST_WEIGHT = 1.5
    NUMERIC_WEIGHT = 0.5

    feature_matrix = np.hstack([
        tag_matrix    * TAG_WEIGHT,
        artist_matrix * ARTIST_WEIGHT,
        numeric_matrix * NUMERIC_WEIGHT,
    ])

    return feature_matrix

# ── 3. MAIN ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    df = fetch_data()
    feature_matrix = pd.DataFrame(build_feature_matrix(df)) # Double check if this works
    feature_matrix.to_csv("feature_matrix.csv", index=False)

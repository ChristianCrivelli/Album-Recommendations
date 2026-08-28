import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity


def recommend(album_title: str, df: pd.DataFrame, feature_matrix: np.ndarray, n: int = 5) -> pd.DataFrame:

    # Find the index of the seed album
    matches = df[df["title"].str.lower() == album_title.strip().lower()]
    if matches.empty:
        print(f"'{album_title}' not found in the database.")
        print("Available titles:", df["title"].tolist())
        return pd.DataFrame()

    idx = matches.index[0]

    # Compute cosine similarity between the seed and every other album
    sim_scores = cosine_similarity([feature_matrix[idx]], feature_matrix)[0]

    # Build results — exclude the seed album itself
    results = df.copy()
    results["similarity"] = sim_scores
    results = (
        results[results.index != idx]
        .sort_values("similarity", ascending=False)
        .head(n)
        [["title", "release_year", "avg_length", "rating", "tags", "similarity"]]
        .reset_index(drop=True)
    )

    # Pretty-print
    print(f"\nTop {n} recommendations for '{album_title}':\n")
    for i, row in results.iterrows():
        tags_preview = ", ".join(row["tags"][:3]) if row["tags"] else "—"
        print(f"  {i+1}. {row['title']} ({int(row['release_year']) if row['release_year'] else '?'})")
        print(f"     Tags: {tags_preview}  |  Similarity: {row['similarity']:.2f}  |  Your rating: {row['rating']}")

    return results
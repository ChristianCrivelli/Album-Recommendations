import time
from album_finder import get_metadata
from pull_albums import fetch_notion_dataframe

# === Get the Data From Notion ===
df = fetch_notion_dataframe()
df = df[['Title', 'Artist(s)', 'Rating/10']]

# === Prepare the Dataframe to Recieve Meta Data
new_cols = ['Primary Type', 'Secondary Types', 'Release Year', 'Top Tags', 'Avg Track Length (Mins)', 'Labels', 'Artist MBIDs']
df = df.reindex(columns=df.columns.tolist() + new_cols)

# === Clean Data ===
# Check data against the server (if an album has already been uploaded drop it)
# NOTES[2]

# === Loop through the table from Notion to enrich it with Musicbrainz Data ===
metadata_results = []

for row in df.itertuples():
    meta = get_metadata(row.Title, row.Artist) # NOTES[3]

    if meta:
        df.at[row.Index, 'Primary Type'] = meta.get('primary_type')
        df.at[row.Index, 'Secondary Types'] = meta.get('secondary_types')
        df.at[row.Index, 'Release Year'] = meta.get('release_year')
        df.at[row.Index, 'Top Tags'] = meta.get('top_tags')
        df.at[row.Index, 'Avg Track Length (Mins)'] = meta.get('avg_length')
        df.at[row.Index, 'Labels'] = meta.get('labels')
        df.at[row.Index, 'Artist MBIDs'] = meta.get('artist_mbids')
    
    time.sleep(1.5) # Sleep to respect rate limits

# === Push Clean Data Into a Server ===

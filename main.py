from pull_albums import fetch_notion_dataframe

# 1. Get the Database From Notion
df = fetch_notion_dataframe()
print(df.columns.tolist())

df = df[['Title', 'Artist(s)', 'Rating/10']]

# 2. Enrich the Data with Spotify Meta Data
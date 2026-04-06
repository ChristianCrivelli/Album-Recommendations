#imports
import streamlit as st
from notion_client import Client
import pandas as pd
import random

#notion keys
notion = Client(auth=st.secrets["notion_albumdata_token"])
DATABASE_ID = st.secrets["notion_projects_id"]

response = notion.databases.query(database_id=DATABASE_ID)

#album data
@st.cache_data
def get_album_data():
    rows = []
    start_cursor = None

    while True:
        response = notion.databases.query(database_id=DATABASE_ID, start_cursor=start_cursor)
        
        for result in response["results"]:
            props = result["properties"]
            title = props.get("Title", {}).get("title")
            artist_multi = props.get("Artist(s)", {}).get("multi_select", [])
            artist_list = [a["name"] for a in artist_multi] if artist_multi else ["Unknown Artist"]
            artist_str = ", ".join(artist_list)

            rating_select = props.get("Rating/10", {}).get("select")
            rating_10_raw = rating_select["name"] if rating_select else None
            try:
                rating_10 = float(rating_10_raw)
                if rating_10.is_integer():
                    rating_10 = int(rating_10)
            except (TypeError, ValueError):
                rating_10 = 0

            rows.append({
                "Title": title[0]["text"]["content"] if title else "No Title",
                "Artist": artist_str,
                "Artist List": artist_list,  # 🔑 for filtering
                "Rating/10": rating_10,
            })

        if not response.get("has_more"):
            break
        start_cursor = response.get("next_cursor")

    return pd.DataFrame(rows)

df = get_album_data()

#streamlit intro
st.title("🎵 Album Recommender")
st.write("Welcome to Chris Album Ratings. Powered by Chris.")

rec_type = st.selectbox(
    "Would you like to see the whole database, filter by artist or just get a random recommendation?",
    ("", "See the database", "Filter by Artist", "Random Recommendation"),
    index=0,
    key="rec_type"
)

#utility
def display_album(album):
    st.write(f"**Title:** {album['Title']}")
    st.write(f"**Artist:** {album['Artist']}")
    st.write(f"**Rating:** {album['Rating/10']}")

#artist
if rec_type == "Filter by Artist":
    # Make an exploded version of the DataFrame for individual artist filtering
    exploded_df = df.explode("Artist List")
    
    artist_list = exploded_df["Artist List"].dropna().unique()
    artist_choice = st.selectbox("Which artist?", sorted(artist_list, key=lambda x: x.lower()))

    artist_albums = exploded_df[exploded_df["Artist List"] == artist_choice].sort_values(by="Rating/10", ascending=False)

    if not artist_albums.empty:
        st.dataframe(artist_albums[["Title", "Artist", "Rating/10"]])
    else:
        st.write("No albums found for this artist.")

##random
elif rec_type == "Random Recommendation":
    st.subheader("Here's your new favourite album!")
    good_albums = df[df["Rating/10"] >= 7]
    rng = random.randrange(0, len(good_albums), 1)
    display_album(good_albums.iloc[rng])
    
##full database
elif rec_type == "See the database":
    min_rating = st.slider("Minimum rating", 0, 10, 0)
    st.dataframe(df[df["Rating/10"] >= min_rating].sort_values(by="Rating/10", ascending=False))

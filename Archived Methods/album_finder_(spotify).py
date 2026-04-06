from connect_spotify import get_connection

def get_metadata(album_name, artist_name):
    sp = get_connection()

    # 1. Search for the album to find the unique ID
    query = f"album:{album_name} artist:{artist_name}"
    search_results = sp.search(q=query, type='album', limit=1)

    if not search_results['albums']['items']:
        return None

    album_id = search_results['albums']['items'][0]['id']

    # 2. Fetch the "Full" Album Metadata
    full_album = sp.album(album_id)

    # 3. Extract Main Artist(s)
    main_artists = [artist['name'] for artist in full_album['artists']]
    main_artist_str = ", ".join(main_artists)

    # 4. Calculate Track Length (Total Album Duration)
    total_ms = sum(track['duration_ms'] for track in full_album['tracks']['items'])
    
    # Convert ms to Total Minutes (rounded)
    total_mins = round(total_ms / 60000, 2) 

    # 5. Fetch Genre from the primary Main Artist
    primary_artist_id = full_album['artists'][0]['id']
    artist_info = sp.artist(primary_artist_id)

    return {
        "Main Artist": main_artist_str,
        "Release Date": full_album['release_date'],
        "Total Duration (Mins)": total_mins
    }
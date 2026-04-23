import os
import musicbrainzngs
from dotenv import load_dotenv

load_dotenv()

# User Agent
musicbrainzngs.set_useragent(
    app = "SimilarityMatrixBuilder", 
    version = "1.0", 
    contact = os.getenv("email")
)

def get_metadata(album_name, artist_name):
    try:
        # 1. Search for the Release Group
        # Searching by Release Group is better for catching the "master" record
        search = musicbrainzngs.search_release_groups(artist=artist_name, releasegroup=album_name, limit=1)
        
        if not search.get('release-group-list'):
            return None
            
        rg_id = search['release-group-list'][0]['id']
        
        # 2. Fetch Full Release Group Data
        # Includes tags (genres/vibes) and the list of specific releases (CDs, Vinyls, etc.)
        rg_data = musicbrainzngs.get_release_group_by_id(rg_id, includes=["tags", "releases"])['release-group']
        
        # --- EXTRACT HIGHER-LEVEL TAXONOMY ---
        primary_type = rg_data.get('primary-type', 'Unknown')
        secondary_types = rg_data.get('secondary-type-list', [])
        
        # Sort tags by community votes (count) and take the top 5
        raw_tags = rg_data.get('tag-list', [])
        sorted_tags = sorted(raw_tags, key=lambda x: int(x.get('count', 0)), reverse=True)
        top_tags = [tag['name'] for tag in sorted_tags[:5]]
        
        # Get the original release year
        first_date = rg_data.get('first-release-date', 'Unknown')
        year = first_date.split('-')[0] if first_date != 'Unknown' else None
        
        # --- EXTRACT SONIC FOOTPRINT & CREDITS ---
        avg_track_length = None
        labels = []
        artist_mbids = []
        
        # We need a specific release to get tracks and labels. We'll just grab the first one.
        if 'release-list' in rg_data and len(rg_data['release-list']) > 0:
            release_id = rg_data['release-list'][0]['id']
            
            # Fetch the specific release including tracks, labels, and artist credits
            release_data = musicbrainzngs.get_release_by_id(release_id, includes=["recordings", "labels", "artist-credits"])['release']
            
            # Extract Labels
            if 'label-info-list' in release_data:
                labels = [l['label']['name'] for l in release_data['label-info-list'] if 'label' in l]
                
            # Extract Artist MBIDs (Great for finding overlapping producers/personnel later)
            if 'artist-credit' in release_data:
                artist_mbids = [c['artist']['id'] for c in release_data['artist-credit'] if isinstance(c, dict) and 'artist' in c]
                
            # Calculate Average Track Length
            total_ms = 0
            track_count = 0
            for medium in release_data.get('medium-list', []):
                for track in medium.get('track-list', []):
                    if 'recording' in track and 'length' in track['recording']:
                        total_ms += int(track['recording']['length'])
                        track_count += 1
                        
            if track_count > 0:
                avg_ms = total_ms / track_count
                avg_track_length = round(avg_ms / 60000, 2) # Convert to minutes
                
        # 3. Return the compiled feature vector
        print(f"Found data for {album_name} by {artist_name}")

        return {
            "Album": album_name,
            "Primary Type": primary_type,
            "Secondary Types": secondary_types,
            "Release Year": year,
            "Top Tags": top_tags,
            "Avg Track Length (Mins)": avg_track_length,
            "Labels": labels,
            "Artist MBIDs": artist_mbids
        }
        
    except musicbrainzngs.WebServiceError as exc:
        print(f"MusicBrainz Error for {album_name}: {exc}")
        return None
    
def get_producers(release_id):
    result = musicbrainzngs.get_release_by_id(release_id, includes=["artist-rels"])
    
    producers = []
    
    # Look through the relationships for this release
    if 'artist-relation-list' in result['release']:
        for rel in result['release']['artist-relation-list']:
            # We specifically look for the 'producer' type
            if rel['type'] == 'producer':
                artist_info = rel['artist']
                producers.append({
                    'name': artist_info['name'],
                    'mbid': artist_info['id']
                })
                
    return producers
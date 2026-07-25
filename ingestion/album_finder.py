import os
import time
import difflib
import musicbrainzngs
from dotenv import load_dotenv
 
load_dotenv()
 
# User Agent
musicbrainzngs.set_useragent(
    app = "SimilarityMatrixBuilder", 
    version = "1.0", 
    contact = os.getenv("email")
)
 
# MusicBrainz allows 1 request/sec. We make multiple calls per album,
# so we sleep between each one to stay safe.
MB_SLEEP = 1.1

# If a release-group has fewer community tags than this, supplement with the
# artist's own tag-list (aggregated across all their releases, so it tends to
# carry far more votes than one obscure album ever gets on its own).
TAG_FALLBACK_THRESHOLD = 3

# MusicBrainz's own search ranking sometimes prioritizes an exact title match
# over the correct artist (e.g. two different artists both released an album
# called "$ad Boy" — search can return the wrong one as its top hit). Below
# this combined title+artist similarity score, we treat the search as a miss
# rather than silently attach a wrong album's metadata.
MIN_MATCH_CONFIDENCE = 0.5


def _similarity(a, b):
    return difflib.SequenceMatcher(None, (a or "").lower().strip(), (b or "").lower().strip()).ratio()


def _candidate_artist_str(rg):
    return ", ".join(
        c['artist']['name'] for c in rg.get('artist-credit', [])
        if isinstance(c, dict) and 'artist' in c
    )


def get_artist_tags(artist_mbid):
    """Fetch an artist's own MusicBrainz tag-list, sorted by community votes.
    Used as a fallback when a specific release-group has few/no tags of its own."""
    if not artist_mbid:
        return []
    try:
        result = musicbrainzngs.get_artist_by_id(artist_mbid, includes=["tags"])
        time.sleep(MB_SLEEP)  # Tip 5: sleep after every MB request
        raw_tags = result.get('artist', {}).get('tag-list', [])
        sorted_tags = sorted(raw_tags, key=lambda x: int(x.get('count', 0)), reverse=True)
        return [tag['name'] for tag in sorted_tags[:5]]
    except musicbrainzngs.WebServiceError as exc:
        print(f"MusicBrainz Error fetching artist tags for {artist_mbid}: {exc}")
        return []


def get_metadata(album_name, artist_name):
    try:
        # 1. Search for the Release Group
        # Searching by Release Group is better for catching the "master" record.
        # Fetch several candidates rather than trusting MusicBrainz's #1 result
        # blindly — its search ranking sometimes favors an exact title match
        # over the correct artist, which can silently attach the wrong
        # album's metadata (e.g. two different artists both have a release
        # called "$ad Boy" — the wrong one can rank first).
        search = musicbrainzngs.search_release_groups(artist=artist_name, releasegroup=album_name, limit=5)
        time.sleep(MB_SLEEP)  # Tip 5: sleep after every MB request
        
        candidates = search.get('release-group-list', [])
        if not candidates:
            return None

        scored = []
        for rg in candidates:
            title_score = _similarity(rg.get('title'), album_name)
            artist_score = _similarity(_candidate_artist_str(rg), artist_name)
            scored.append((title_score * 0.5 + artist_score * 0.5, rg))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        best_score, best_rg = scored[0]

        if best_score < MIN_MATCH_CONFIDENCE:
            print(f"No confident MusicBrainz match for {album_name} by {artist_name} (best candidate: {best_rg.get('title')} by {_candidate_artist_str(best_rg)}, score {best_score:.2f})")
            return None

        rg_id = best_rg['id']
        
        # 2. Fetch Full Release Group Data
        # Includes tags (genres/vibes), the list of specific releases (CDs, Vinyls, etc.),
        # and artist-credits (used below as the tag/artist-fallback source — this is a
        # free addition to the same request, not an extra MusicBrainz call).
        # NOTE: "artists" and "artist-credits" are two different valid includes for
        # release-group — "artists" is an unrelated subquery include and does NOT
        # populate the artist-credit field read below. Must be "artist-credits".
        rg_data = musicbrainzngs.get_release_group_by_id(rg_id, includes=["tags", "releases", "artist-credits"])['release-group']
        time.sleep(MB_SLEEP)  # Tip 5: sleep after every MB request
        
        # --- EXTRACT HIGHER-LEVEL TAXONOMY ---
        primary_type = rg_data.get('primary-type', 'Unknown')
        secondary_types = rg_data.get('secondary-type-list', [])
        
        # Sort tags by community votes (count) and take the top 5
        raw_tags = rg_data.get('tag-list', [])
        sorted_tags = sorted(raw_tags, key=lambda x: int(x.get('count', 0)), reverse=True)
        top_tags = [tag['name'] for tag in sorted_tags[:5]]
        tag_source = "release-group"

        # --- FALLBACK: sparse release-group tags → supplement with artist tags ---
        # Many lesser-known or newer releases simply never accumulate community
        # tags on MusicBrainz. The artist entity usually has richer tag data
        # (votes aggregated across every release), so fill gaps from there.
        if len(top_tags) < TAG_FALLBACK_THRESHOLD:
            rg_artist_mbids = [
                c['artist']['id'] for c in rg_data.get('artist-credit', [])
                if isinstance(c, dict) and 'artist' in c
            ]
            seen = {t.lower() for t in top_tags}
            gained_any = False
            for artist_mbid in rg_artist_mbids:
                for tag in get_artist_tags(artist_mbid):
                    if tag.lower() not in seen:
                        top_tags.append(tag)
                        seen.add(tag.lower())
                        gained_any = True
            top_tags = top_tags[:5]
            if gained_any:
                tag_source = "release-group+artist-fallback"
        
        # Get the original release year
        first_date = rg_data.get('first-release-date', 'Unknown')
        year = first_date.split('-')[0] if first_date != 'Unknown' else None
        
        # --- EXTRACT SONIC FOOTPRINT & CREDITS ---
        avg_track_length = None
        labels = []
        artist_mbids = []
        artist_dicts = []  # Tip 2: initialise here so it always exists
        release_id = None  # Tip 2: initialise here so it always exists
 
        # We need a specific release to get tracks and labels. We'll just grab the first one.
        if 'release-list' in rg_data and len(rg_data['release-list']) > 0:
            release_id = rg_data['release-list'][0]['id']
            
            # Fetch the specific release including tracks, labels, and artist credits
            release_data = musicbrainzngs.get_release_by_id(release_id, includes=["recordings", "labels", "artist-credits"])['release']
            time.sleep(MB_SLEEP)  # Tip 5: sleep after every MB request
            
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
 
            # Tip 2: build artist_dicts inside the block where release_data is guaranteed to exist
            if 'artist-credit' in release_data:
                for c in release_data['artist-credit']:
                    if isinstance(c, dict) and 'artist' in c:
                        artist_dicts.append({
                            'name': c['artist']['name'],
                            'mbid': c['artist']['id']
                        })

        # Fallback: the specific release sometimes has no artist-credit data
        # at all (not just a missing mbid — the whole block absent), which
        # is a separate cause of "Unknown artist" from the missing-mbid case
        # handled downstream in album_push_logic.py. The release-group level
        # almost always has artist-credit, and we already fetch it above
        # (via includes=["artist-credits"]) for the tag fallback, so this
        # costs no extra request.
        if not artist_dicts:
            rg_artist_dicts = [
                {'name': c['artist']['name'], 'mbid': c['artist']['id']}
                for c in rg_data.get('artist-credit', [])
                if isinstance(c, dict) and 'artist' in c
            ]
            if rg_artist_dicts:
                artist_dicts = rg_artist_dicts
                if not artist_mbids:
                    artist_mbids = [a['mbid'] for a in rg_artist_dicts if a.get('mbid')]
                
        # 3. Return the compiled feature vector
        print(f"Found data for {album_name} by {artist_name}")
 
        return {
            "Album": album_name,
            "Primary Type": primary_type,
            "Secondary Types": secondary_types,
            "Release Year": year,
            "Top Tags": top_tags,
            "Tag Source": tag_source,
            "Avg Track Length (Mins)": avg_track_length,
            "Labels": labels,
            "Artist MBIDs": artist_mbids,
            "Release ID": release_id,
            "Artists": artist_dicts  
        }
        
    except musicbrainzngs.WebServiceError as exc:
        print(f"MusicBrainz Error for {album_name}: {exc}")
        return None
    
def get_producers(release_id):
    result = musicbrainzngs.get_release_by_id(release_id, includes=["artist-rels"])
    time.sleep(MB_SLEEP)  # Tip 5: sleep after every MB request
    
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
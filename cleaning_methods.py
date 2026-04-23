import pandas as pd

def clean_artist_list(artist_val):
    if not artist_val: return []
    if isinstance(artist_val, list): return artist_val
    # Remove brackets and quotes, then split by comma if necessary
    clean_str = str(artist_val).strip("[]").replace("'", "").replace('"', '')
    return [a.strip() for a in clean_str.split(',')]

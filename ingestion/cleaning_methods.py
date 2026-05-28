def clean_artist_list(artist_val):
    if not artist_val:
        return []

    # Tip 4: if Notion already gave us a list, use it as-is — no string mangling needed
    if isinstance(artist_val, list):
        return [str(a).strip() for a in artist_val if a]

    # Fallback: handle accidentally stringified lists like "['Artist A', 'Artist B']"
    clean_str = str(artist_val).strip("[]").replace("'", "").replace('"', '')
    return [a.strip() for a in clean_str.split(',') if a.strip()]

# Dictionary to map messy/duplicate tags to a single standardized tag
TAG_MAPPING = {
    # Hip-hop / Rap variants → canonical "hip-hop"
    "rap": "hip-hop",
    "rap/hip-hop": "hip-hop",
    "rap/hip hop": "hip-hop",
    "rap hip hop": "hip-hop",
    "hip-hop/rap": "hip-hop",
    "hip hop/rap": "hip-hop",
    "hip hop": "hip-hop",
    "hiphop": "hip-hop",

    # R&B variants
    "r b": "r&b",
    "rnb": "r&b",
    "r and b": "r&b",
    "rhythm and blues": "r&b",
    "rhythm & blues": "r&b",

    # R&B sub-genre variants
    "alt r&b": "alternative r&b",
    "alt rnb": "alternative r&b",
    "alternative rnb": "alternative r&b",

    # Rock variants
    "alt rock": "alternative rock",
    "alternative-rock": "alternative rock",
    "indie rock": "indie rock",  # keeps as-is, but normalises spacing
    "indie-rock": "indie rock",

    # Electronic / Dance variants
    "electronica": "electronic",
    "electro": "electronic",
    "dance music": "dance",

    # Pop variants
    "art pop": "art pop",  # normalise spacing
    "art-pop": "art pop",
    "synth pop": "synth-pop",
    "synthpop": "synth-pop",

    # Soul variants
    "neo soul": "neo-soul",
    "neo-soul": "neo-soul",  # already canonical, keeps it consistent
}

# Tags to remove entirely — not genre/style information
TAGS_TO_REMOVE = {
    "laut.de",
    "self-titled",
    "stars",
    "ep",
    "billboard",
}

def clean_and_normalize_tags(tags_list):
    if not tags_list:
        return []
        
    cleaned_tags = []
    for tag in tags_list:
        clean_tag = str(tag).lower().strip()
        
        if "on cover" in clean_tag or "woechen" in clean_tag or "weeks" in clean_tag or "charts" in clean_tag:
            continue

        # Remove junk/non-genre tags
        if clean_tag in TAGS_TO_REMOVE:
            continue
            
        # .get() will return the mapped value if found, otherwise it keeps the original tag
        clean_tag = TAG_MAPPING.get(clean_tag, clean_tag)
        
        cleaned_tags.append(clean_tag)
        
    return list(set(cleaned_tags))
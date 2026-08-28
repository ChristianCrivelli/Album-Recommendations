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
    "ep",
    "billboard",
}

# Substrings that mark a tag as junk regardless of what else is in the string
# (e.g. "billboard hot 100; 2014; year end chart", "billboard hot 100 tags",
# "ph_2_stars"). These catch chart/ranking/rating-encoded tags that embed a
# year, chart name, or numeric prefix, which exact-match TAGS_TO_REMOVE can't.
JUNK_SUBSTRINGS = (
    "on cover",
    "woechen",
    "wochen",      # correct German spelling ("weeks") — "woechen" alone missed this
    "weeks",
    "chart",       # catches both "chart" and "charts", singular or plural
    "billboard",   # catches any billboard-prefixed variant, not just the bare tag
    "stars",       # catches "5 stars", "ph_2_stars", etc. — rating junk, not genre info
)

def clean_and_normalize_tags(tags_list):
    if not tags_list:
        return []
        
    cleaned_tags = []
    for tag in tags_list:
        clean_tag = str(tag).lower().strip()
        
        # Skip junk charts/weeks/billboard tags (substring match catches variants
        # with years or extra words baked in, e.g. "billboard hot 100; 2014; year end chart")
        if any(junk in clean_tag for junk in JUNK_SUBSTRINGS):
            continue

        # Skip exact junk/non-genre tags
        if clean_tag in TAGS_TO_REMOVE:
            continue
            
        # --- NEW LOGIC: Handle composite / slash-separated tags ---
        if "/" in clean_tag:
            # Split the tag by the slash (e.g., "pop/hip-hop" -> ["pop", "hip-hop"])
            sub_tags = [sub.strip() for sub in clean_tag.split("/")]

            # Map each sub-tag individually using your dictionary
            normalized_sub_tags = [TAG_MAPPING.get(sub, sub) for sub in sub_tags]

            # De-duplicate while preserving order (issue #15 — "Fuse Hip Hop
            # and Hip-Hop into one tag"). Without this, a composite tag whose
            # parts map to the same canonical genre — e.g. "hip-hop/rap" or
            # "hiphop/rap/r&b", both of which normalize each half to
            # "hip-hop" — recombines into "hip-hop/hip-hop" (or
            # "hip-hop/hip-hop/r&b") instead of collapsing down to the single
            # tag it should be. If only one distinct sub-tag remains after
            # dedup, that's the whole point: fuse into just "hip-hop" rather
            # than a slash-joined tag with itself.
            seen = []
            for sub in normalized_sub_tags:
                if sub not in seen:
                    seen.append(sub)
            normalized_sub_tags = seen

            # Recombine them into a standardized format
            clean_tag = "/".join(normalized_sub_tags)
        else:
            # Standard exact-match lookup for single tags
            clean_tag = TAG_MAPPING.get(clean_tag, clean_tag)
        
        cleaned_tags.append(clean_tag)
        
    # Remove duplicates
    return list(set(cleaned_tags))
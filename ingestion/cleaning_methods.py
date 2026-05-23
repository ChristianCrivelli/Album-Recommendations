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
    "alt r&b": "alternative r&b",
    "alt rock": "alternative rock"
}
    #add any others here

def clean_and_normalize_tags(tags_list):
    if not tags_list:
        return []
        
    cleaned_tags = []
    for tag in tags_list:
        clean_tag = str(tag).lower().strip()
        
        if "on cover" in clean_tag or "woechen" in clean_tag or "weeks" in clean_tag or "charts" in clean_tag:
            continue
            
        # .get() will return the mapped value if found, otherwise it keeps the original tag
        clean_tag = TAG_MAPPING.get(clean_tag, clean_tag)
        
        cleaned_tags.append(clean_tag)
        
    return list(set(cleaned_tags))
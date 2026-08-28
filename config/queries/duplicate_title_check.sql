SELECT title, COUNT(*) as row_count, array_agg(id) as album_ids, array_agg(mbid) as mbids
FROM albums
GROUP BY title
HAVING COUNT(*) > 1
ORDER BY title;

-- For each duplicate pair found above, check which one has the correct contributor links before deleting the wrong one:
SELECT a.title, ar.name, ac.role
FROM albums a
JOIN album_contributions ac ON ac.album_id = a.id
JOIN artists ar ON ar.id = ac.person_id
WHERE a.id = '<album_id_to_check>';

--Once you've identified the wrong row's id, delete it (junction rows first for the FK constraints, same pattern as tag_cleanup.sql):
DELETE FROM album_contributions WHERE album_id = '<wrong_id>';
DELETE FROM album_tags WHERE album_id = '<wrong_id>';
DELETE FROM albums WHERE id = '<wrong_id>';
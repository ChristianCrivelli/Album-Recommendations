-- Tag List
SELECT id, name 
FROM tags 
ORDER BY name ASC;

-- Most (and Least) Popular Tags
SELECT t.name, COUNT(at.album_id) as album_count
FROM tags t
JOIN album_tags at ON t.id = at.tag_id
GROUP BY t.name
ORDER BY album_count DESC; -- Change to ASC to see the least used tags first

-- Variations of R&B
SELECT name FROM tags WHERE name ILIKE '%r&b%' OR name ILIKE '%r and b%';

-- Variations of Rock
SELECT name FROM tags WHERE name ILIKE '%rock%';
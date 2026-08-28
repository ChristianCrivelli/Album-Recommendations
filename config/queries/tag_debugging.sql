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
SELECT name FROM tags WHERE name ILIKE '%r&b%' OR name ILIKE '%r and b%' OR name ILIKE '%rnb%' OR name ILIKE '%rhythm%';

-- Variations of Rock
SELECT name FROM tags WHERE name ILIKE '%rock%';

-- Variations of Hip-Hop / Rap
SELECT name FROM tags WHERE name ILIKE '%hip%hop%' OR name ILIKE '%hip-hop%' OR name ILIKE '%rap%';

-- Tags used by only 1 album (potential junk or typos)
SELECT t.name, COUNT(at.album_id) as album_count
FROM tags t
JOIN album_tags at ON t.id = at.tag_id
GROUP BY t.name
HAVING COUNT(at.album_id) = 1
ORDER BY t.name ASC;
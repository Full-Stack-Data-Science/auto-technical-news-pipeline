-- DROP VIEW IF EXISTS powerbi.twitter_30days;
-- GO

CREATE VIEW powerbi.twitter_30days AS
SELECT *
FROM powerbi.twitter
WHERE twitter_date >= DATEADD(DAY, -30, GETUTCDATE());
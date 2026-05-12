-- DROP VIEW IF EXISTS powerbi.linkedin_30days;
-- GO

CREATE VIEW powerbi.linkedin_30days AS
SELECT *
FROM powerbi.linkedin
WHERE date >= DATEADD(DAY, -30, GETUTCDATE());
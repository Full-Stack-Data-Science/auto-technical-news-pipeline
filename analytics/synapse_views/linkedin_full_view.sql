-- DROP VIEW IF EXISTS powerbi.linkedin;
-- GO

CREATE VIEW powerbi.linkedin AS
WITH source_data AS(
    SELECT
        COALESCE(content, text) AS content,
        COALESCE(influencer_name, '') AS influencer_name,
        COALESCE(influencer_title, '') AS influencer_title,
        TRY_CAST(REPLACE(followers_count, ',', '') AS INT) AS followers_count,
        post_url,
        activity_id,
        topic,
        supported_industry,
        keywords,
        reactions,
        comments,
        reposts,
        media_url,
        time_ago,
        TRY_CAST(REPLACE(REPLACE(scraped_at, 'T', ' '), 'Z', '') AS DATETIME2) AS date,
        engagement_score,
        author,
        is_tech_related
    FROM OPENROWSET(
        BULK '/linkedin/raw/*.parquet',
        DATA_SOURCE = 'bronze_container',
        FORMAT = 'PARQUET'
    ) WITH(
        content NVARCHAR(MAX),
        text NVARCHAR(MAX),
        influencer_name VARCHAR(MAX),
        influencer_title VARCHAR(MAX),
        followers_count VARCHAR(100),
        post_url VARCHAR(500),
        activity_id VARCHAR(500),
        topic VARCHAR(500),
        supported_industry VARCHAR(50),
        keywords VARCHAR(20),
        reactions INT,
        comments INT,
        reposts INT,
        media_url VARCHAR(500),
        time_ago VARCHAR(20),
        scraped_at VARCHAR(50),  
        engagement_score INT,
        author VARCHAR(50),
        is_tech_related BIT
    ) AS linkedin_source
),
ranked_data AS (
    SELECT *,
    ROW_NUMBER() OVER(
        PARTITION BY activity_id
        ORDER BY date DESC
    ) AS dedup,
    ROW_NUMBER() OVER(
        PARTITION BY content
        ORDER BY date ASC
    ) AS dedup_using_content
    FROM source_data
)
SELECT *
FROM ranked_data
WHERE dedup = 1
AND dedup_using_content = 1; 
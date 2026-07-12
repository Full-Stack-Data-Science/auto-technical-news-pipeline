-- DROP VIEW IF EXISTS powerbi.twitter;
-- GO

CREATE VIEW powerbi.twitter AS
WITH source_data AS(
    SELECT
        COALESCE(followers_count, 0) AS followers_count,
        COALESCE(influencer_title, '') AS influencer_title,
        COALESCE(comments, replies) AS comments,
        COALESCE(reposts, retweets) AS reposts,
        COALESCE(reactions, likes) AS reactions,
        COALESCE(author, '') AS author,
        TRY_CAST(REPLACE(REPLACE(date, 'T', ' '), 'Z', '') AS DATETIME2) AS twitter_date,
        post_url,
        content,
        bookmarks,
        views,
        topic,
        supported_industry,
        is_tech_related,
        TRY_CAST(REPLACE(REPLACE(scraped_at, 'T', ' '), 'Z', '') as DATETIME2) as date
    FROM OPENROWSET(
        BULK '/twitter/raw/*.parquet',
        DATA_SOURCE = 'bronze_container',
        FORMAT = 'PARQUET'
    ) WITH(
        author VARCHAR(100),
        followers_count INT,
        influencer_title VARCHAR(500),
        post_url VARCHAR(100),
        content NVARCHAR(MAX),
        date VARCHAR(50),
        comments VARCHAR(50),
        reposts VARCHAR(50),
        reactions VARCHAR(50),
        replies VARCHAR(50),
        retweets VARCHAR(50),
        likes VARCHAR(50),
        bookmarks VARCHAR(50),
        views VARCHAR(50),
        topic VARCHAR(500),
        supported_industry VARCHAR(200),
        is_tech_related BIT,
        scraped_at VARCHAR(100)
    ) AS twitter_source
),
ranked_data AS(
    SELECT *,
    ROW_NUMBER() OVER(
        PARTITION BY post_url
        ORDER BY twitter_date DESC
    ) AS dedup,
    ROW_NUMBER() OVER(
        PARTITION BY content
        ORDER BY twitter_date ASC
    ) AS dedup_using_content
)
SELECT *
FROM ranked_data
WHERE dedup = 1
AND dedup_using_content = 1; 
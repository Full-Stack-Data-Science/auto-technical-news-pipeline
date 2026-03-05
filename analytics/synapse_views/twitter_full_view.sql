-- DROP VIEW IF EXISTS powerbi.twitter;
-- GO

CREATE VIEW powerbi.twitter AS
WITH ranked_data AS(
    SELECT
        COALESCE(followers_count, 0) as followers_count,
        COALESCE(influencer_title, '') as influencer_title,
        COALESCE(comments, replies) as comments,
        COALESCE(reposts, retweets) as reposts,
        COALESCE(reactions, likes) as reactions,
        COALESCE(author, '') as author,
        TRY_CAST(REPLACE(REPLACE(date, 'T', ' '), 'Z', '') as DATETIME2) as twitter_date,
        post_url,
        content,
        bookmarks,
        views,
        topic,
        supported_industry,
        is_tech_related,
        TRY_CAST(REPLACE(REPLACE(scraped_at, 'T', ' '), 'Z', '') as DATETIME2) as date,
        ROW_NUMBER() OVER(
            PARTITION BY post_url
            ORDER BY TRY_CAST(REPLACE(REPLACE(date, 'T', ' '), 'Z', '') as DATETIME2) DESC
        ) as dedup,
        ROW_NUMBER() OVER(
            PARTITION BY content
            ORDER BY TRY_CAST(REPLACE(REPLACE(date, 'T', ' '), 'Z', '') as DATETIME2) ASC
        ) as dedup_using_content
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
    ) as twitter_source
)
SELECT *
FROM ranked_data
WHERE dedup = 1
AND dedup_using_content = 1; 
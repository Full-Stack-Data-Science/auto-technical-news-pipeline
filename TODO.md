| Title | Description |
|---|---|
| Data model definition | Define and implement a common data model (dataclass) with clearly defined attributes for post entities across the codebase to improve maintainability, consistency, and robustness. |
| Scrape any K latest posts | The Twitter scraper currently supports fetching only 3–6 recent posts per user. Extend it to support an arbitrary K with configurable limits and performance safeguards. |
| Full new post detection pipeline | The Service Bus publisher is in place. Implement a fully generic consumer service within an event-driven architecture to process new-post events and publish curated content to downstream platforms. |
| Improve tech/non-tech classification | The current false-negative rate is high, causing quality technical posts to be missed. Improve accuracy and expand categorization into more precise technical domains. Research available in `notebooks/classification/`. |
| Post summarization | Improve the post summarization pipeline in the consumer service. Current experimentation is available in `notebooks/`. |
| Dynamic influencer graph | The influencer network graph is static. Make it dynamic by updating relationships based on follower count, engagement rate, and activity level to surface higher-quality trending posts and remove inactive authors. |
| Fix engagement bias | Total engagement is biased toward famous influencers and older posts that accumulate over time. Suggested metric: total engagement / number of posts. |
| Topic trend tracking | Implement time-based topic tracking to measure growth instead of just total engagement. Example: "Generative AI +180% vs. last week." Enables momentum-based trend detection. |
| Author profile images | Integrate author profile images into published summaries where helpful. |
| Dockerize scraper service | Fully containerize the scraper service to eliminate the dependency on manual VM-based authentication for X (Twitter) / LinkedIn. |
| Evaluate alternative scraping frameworks | The Selenium WebDriver approach may be blocked by anti-bot systems. Evaluate alternatives such as `undetected-chromedriver` or `nodriver` to improve reliability. |

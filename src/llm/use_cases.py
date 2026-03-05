from llm.prompt_templates import x_post_summary, linkedin_post_summary

def summerize_X_posts(llm_client, posts):
    messages = [
        {"role": "system", "content": x_post_summary.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": x_post_summary.build_user_prompt(posts),
            },
        ]

    return llm_client.chat_complete(messages)

def summerize_linkedin_posts(llm_client, posts):
    """
    Summarize LinkedIn posts with LinkedIn-specific formatting.
    Similar to summerize_X_posts but optimized for LinkedIn data with engagement metrics.
    """
    messages = [
        {"role": "system", "content": linkedin_post_summary.SYSTEM_PROMPT},
        {
            "role": "user",
            "content": linkedin_post_summary.build_user_prompt(posts),
        },
    ]

    return llm_client.chat_complete(messages)
from post_writer.llm.prompt_templates import post_summary

def summerize_posts(llm_client, posts):
    messages = [
        {
            "role": "system", 
            "content": post_summary.SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": post_summary.build_user_prompt(posts),
        },
    ]

    return llm_client.chat_complete(messages)
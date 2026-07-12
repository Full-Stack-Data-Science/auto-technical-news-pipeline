import pandas as pd

from post_writer.llm.prompt_templates import post_summary


def summerize_posts(llm_client, posts: pd.DataFrame) -> str:
    if llm_client is None:
        return _format_without_llm(posts)

    messages = [
        {"role": "system", "content": post_summary.SYSTEM_PROMPT},
        {"role": "user", "content": post_summary.build_user_prompt(posts)},
    ]
    return llm_client.chat_complete(messages)


def _format_without_llm(posts: pd.DataFrame) -> str:
    lines = ["**Trending Tech Posts hôm nay**\n"]
    for i, row in enumerate(posts.itertuples(), start=1):
        preview = (row.content[:280] + "…") if len(row.content) > 280 else row.content
        lines.append(
            f"**Post {i}: @{row.author}**\n"
            f"{preview}\n"
            f"Đọc thêm tại: {row.post_url}\n"
            f"{{HASHTAGS_{i}}}"
        )
    return "\n\n".join(lines)

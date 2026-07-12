SYSTEM_PROMPT = (
    "You write concise, engaging tech news summaries "
    "for Vietnamese tech communities on Discord."
)

content_requirements = """
        CONTENT REQUIREMENTS:
        - Write in natural, fluent Vietnamese for a Vietnamese tech audience
        - Friendly, engaging tone
        - Total length: 200–300 words
        - Clearly explain why each post is trending, based on engagement metrics
        - Open with a short greeting to the tech community and mention that these are the hottest posts of the day
        """

format_requirements = """
        FORMATTING REQUIREMENTS:
        - Output plain text with Discord markdown only
        - Use **text** for bold titles and emphasis
        - Use plain newlines to separate sections
        - Do NOT use HTML tags (<p>, <strong>, <br>, etc.)
        - Do NOT use code blocks or backticks
        """

structure_requirements = """
        STRUCTURE REQUIREMENTS:
        1. First line: a bold global headline for the entire summary (**headline**)

        2. For each post, output in this exact order:
           - A bold post-specific title on its own line (**Post X: TITLE**)
           - One or two plain sentences summarizing the post
           - A call-to-action line with the URL (example: Đọc thêm tại: https://...)

        3. Separate each post block with a blank line.
        4. Titles must be descriptive and meaningful, not generic labels.
        """


def build_user_prompt(posts):
    post_str = ""

    for i in range(len(posts)):
        post_str += f"""
            Post {i + 1}:
            {posts.iloc[i].to_json()}

            HASHTAG PLACEMENT RULE FOR POST {i + 1}:
            - After the URL line, output this EXACT placeholder on its own line:
            {{HASHTAGS_{i + 1}}}
            - Do NOT generate hashtags
            - Do NOT modify the placeholder
        """

    user_prompt = f"""
        You are a tech content curator.
        Create an engaging summary for a tech community Discord channel based on the top {len(posts)} posts today.

        {post_str}

        {content_requirements}
        {structure_requirements}
        {format_requirements}

        The output must be ready to send directly as a Discord message.
    """
    return user_prompt
SYSTEM_PROMPT = (
    "You write clean, well-structured HTML content "
    "for Vietnamese tech news communities."
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
        - Output VALID HTML ONLY
        - Use <p> for all paragraphs
        - Use <strong> for titles and emphasis
        - Do NOT use Markdown syntax (###, **, *, _, -)
        - Do NOT use unsupported HTML tags
        - Do NOT include code blocks or backticks
        """

structure_requirements = """
        STRUCTURE REQUIREMENTS:
        1. First paragraph:
           - A global headline for the entire summary
           - Wrapped in <p><strong>...</strong></p>

        2. For each post, output in this exact order:
           - A post-specific title in <p><strong>Post X: TITLE</strong></p>
           - One or more <p> paragraphs summarizing the post
           - One <p> containing the post URL, written as a short call-to-action
             (example: Đọc thêm tại: https://...)

        3. Titles must be descriptive and meaningful, not generic labels.
        """


def build_user_prompt(posts):
    post_str = ""
    
    for i in range(len(posts)):
        post_str += f"""
            Post {i + 1}:
            {posts.iloc[i].to_json()}

            HASHTAG PLACEMENT RULE FOR POST {i + 1}:
            - After the URL paragraph, output this EXACT line:
            <p>{{HASHTAGS_{i + 1}}}</p>
            - Do NOT generate hashtags
            - Do NOT modify the placeholder
        """

    user_prompt =  f"""
        You are a tech content curator.
        Create an engaging summary for a tech community channel based on the top {len(posts)} posts today.

        {post_str}
        
        {content_requirements}
        {structure_requirements}
        {format_requirements}

        The output must be ready to paste directly into a rich-text editor.
    """
    return user_prompt
import ast

SYSTEM_PROMPT = (
    "You write clean, well-structured HTML content "
    "for Vietnamese tech news communities based on LinkedIn posts."
)

content_requirements = """
        CONTENT REQUIREMENTS:
        - Write in natural, fluent Vietnamese for a Vietnamese tech audience
        - Friendly, engaging tone
        - Total length: 200–300 words
        - Clearly explain why each post is trending, based on engagement metrics
        - Include engagement numbers in the text (e.g., "hơn 35,000 lượt tương tác" - over 35,000 interactions)
        - Mention the influencer's title/role when relevant (e.g., "từ [influencer_title]")
        - Calculate total interactions = reactions + comments + reposts
        - Format engagement numbers nicely (e.g., "hơn 35,000 lượt tương tác" for 35,000+)
        """

format_requirements = """
        FORMATTING REQUIREMENTS:
        - Output VALID HTML ONLY
        - Use <p> for all paragraphs
        - Use <strong> for titles and emphasis
        - Use <a href="URL">link text</a> for hyperlinks
        - Do NOT use Markdown syntax (###, **, *, _, -)
        - Do NOT use unsupported HTML tags
        - Do NOT include code blocks or backticks
        """

structure_requirements = """
        STRUCTURE REQUIREMENTS:
        1. First paragraph:
           - Must start with: "Cập nhật công nghệ nổi bật hôm nay cho cộng đồng công nghệ Việt Nam"
           - Wrapped in <p><strong>...</strong></p>

        2. For each post, output in this exact order:
           - A post-specific title in <p><strong>Post X: TITLE</strong></p>
           - One or more <p> paragraphs summarizing the post
           - Include engagement metrics naturally in the text (e.g., "Bài viết nhận được hơn X lượt tương tác")
           - Include influencer info if available (e.g., "từ [influencer_title]")
           - If the post is a repost, mention it naturally (e.g., "Bài viết được repost từ [original_author]" or "Đây là bài repost từ [original_author]")
           - If profiles are tagged/mentioned, mention them naturally (e.g., "Bài viết đề cập đến [tagged_profile]" or "Bài viết tag [tagged_profile]")
           - One <p> containing the post URL as a clickable hyperlink: "Đọc thêm tại: <a href=\"[post_url]\">[post_url]</a>"
           - URLs MUST be wrapped in <a href="...">...</a> tags to make them clickable
           - After the URL paragraph, output this EXACT line: <p>{{HASHTAGS_{i + 1}}}</p>
           - Do NOT generate hashtags
           - Do NOT modify the placeholder

        3. Titles must be descriptive and meaningful, not generic labels.
        4. Engagement metrics should be naturally integrated into the text.
        """


def build_user_prompt(posts):
    post_str = ""
    
    for i in range(len(posts)):
        post_data = posts.iloc[i]
        total_interactions = (
            int(post_data.get('reactions', 0) or 0) +
            int(post_data.get('comments', 0) or 0) +
            int(post_data.get('reposts', 0) or 0)
        )
        
        # Extract repost and tagging information
        is_repost = post_data.get('is_repost', False)
        original_author = post_data.get('original_author', '')
        tagged_profiles = post_data.get('tagged_profiles', [])
        
        repost_info = ""
        if is_repost and original_author:
            repost_info = f"\n            - This is a REPOST - Original Author: {original_author}"
        elif is_repost:
            repost_info = "\n            - This is a REPOST"
        
        tagged_info = ""

        # Normalize tagged_profiles to list-like
        if isinstance(tagged_profiles, str):
            try:
                tagged_profiles = ast.literal_eval(tagged_profiles)
            except (ValueError, SyntaxError):
                tagged_profiles = []

        # Handle numpy array → convert to list
        if hasattr(tagged_profiles, 'size'):  
            if tagged_profiles.size == 0:
                tagged_profiles = []
            else:
                tagged_profiles = tagged_profiles.tolist()

        # Now safe to check length
        if isinstance(tagged_profiles, (list, tuple)) and len(tagged_profiles) > 0:
            tagged_info = f"\n - Tagged Profiles: {', '.join(str(tagged_profile) for tagged_profile in tagged_profiles[:3])}"
        elif tagged_profiles:  # fallback for other truthy values
            tagged_info = f"\n- Tagged Profiles: {tagged_profiles}"
        
        post_str += f"""
            Post {i + 1}:
            - Author: {post_data.get('author', 'N/A')}{repost_info}
            - Influencer Name: {post_data.get('influencer_name', 'N/A')}
            - Influencer Title: {post_data.get('influencer_title', 'N/A')}
            - Followers: {post_data.get('followers_count', 'N/A')}{tagged_info}
            - Content: {post_data.get('content', post_data.get('text', 'N/A'))}
            - Reactions: {post_data.get('reactions', 0)}
            - Comments: {post_data.get('comments', 0)}
            - Reposts: {post_data.get('reposts', 0)}
            - Total Interactions: {total_interactions}
            - Total Engagement: {post_data.get('total_engagement', total_interactions)}
            - Post URL: {post_data.get('post_url', 'N/A')}

            HASHTAG PLACEMENT RULE FOR POST {i + 1}:
            - After the URL paragraph, output this EXACT line:
            <p>{{HASHTAGS_{i + 1}}}</p>
            - Do NOT generate hashtags
            - Do NOT modify the placeholder
        """

    user_prompt = f"""
        You are a tech content curator.
        Create an engaging summary for a tech community channel based on the top {len(posts)} LinkedIn posts today.

        {post_str}
        
        {content_requirements}
        {structure_requirements}
        {format_requirements}

        IMPORTANT: 
        - Use "lượt tương tác" (interactions) when mentioning total engagement
        - Format large numbers nicely (e.g., "hơn 35,000" for 35,000+)
        - Include influencer title/role when it adds context
        - URLs MUST be wrapped in <a href="URL">URL</a> tags to create clickable hyperlinks
        - Example: <p>Đọc thêm tại: <a href="https://www.linkedin.com/feed/update/urn:li:activity:123">https://www.linkedin.com/feed/update/urn:li:activity:123</a></p>
        - The output must be ready to paste directly into a rich-text editor.
    """
    return user_prompt

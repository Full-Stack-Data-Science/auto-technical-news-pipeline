import requests
import logging
from typing import Optional, Dict, Any

from common.utils import setup_logging
from common.config import Config

setup_logging()
logger = logging.getLogger(__name__)

class MemePostException(Exception):
    pass

class MemePoster:
    def __init__(self, session_cookie):
        self.base_url = Config.FSDS_URL
        self.session_cookie = session_cookie

        if not self.session_cookie:
            raise MemePostException(
                "Session cookie is None or empty. FSDS login may have failed."
            )

        self.cookies = {"fsdslsvmfqcber": self.session_cookie}

        masked_cookie = (
            self.session_cookie[:6] + "..." + self.session_cookie[-4:]
            if isinstance(self.session_cookie, str) and len(self.session_cookie) > 10
            else "***"
        )
        logger.info(
            "Initialized MemePoster | base_url=%s | cookie=%s",
            self.base_url,
            masked_cookie,
        )

    def test_api_connection(self):
        try:
            response = requests.get(
                f"{self.base_url}/meme/posts",
                timeout=5
            )
            logger.info(f"API reachable: {response.status_code}")
            return response.status_code < 500
        except requests.exceptions.RequestException as e:
            logger.error(f"API not reachable: {e}")
        return False
    
    def post_meme(
        self,
        content: str,
        channel_id: str,
        image_files: Optional[list]=None,
        hashtags: Optional[str]=None,
        is_anonymous: bool=False,
        timeout: int = 10
    ) -> Dict[str, Any]:
        """
        Post a meme to the FSDS platform.
        
        Args:
            content: The meme content (text/markdown)
            channel_id: The channel ID to post to
            image_files: List of tuples (filename, file_bytes, content_type) or file-like objects
                         Example: [("image1.jpg", bytes_data, "image/jpeg"), ...]
            hashtags: Comma-separated hashtags (ignored per user request)
            is_anonymous: Whether to post anonymously
            timeout: Request timeout in seconds
            
        Returns:
            Dictionary containing response data
        """
        url = f"{self.base_url}/meme/posts"
        
        content_preview = (content[:200] + "...") if len(content) > 200 else content
        logger.info(
            "About to POST meme | url=%s | channelId=%s | isAnonymous=%s | "
            "content_length=%s | content_preview=%r",
            url,
            channel_id,
            str(is_anonymous).lower(),
            len(content),
            content_preview,
        )

        # We always send multipart/form-data, to match the working `curl -F` usage.
        # Text fields are encoded as multipart parts with no filename.
        multipart: list = [
            ("content", (None, content)),
            ("isAnonymous", (None, str(is_anonymous).lower())),
        ]

        if channel_id:
            multipart.append(("channelId", (None, channel_id)))

        # Attach any image files
        if image_files:
            for img_file in image_files:
                if isinstance(img_file, tuple):
                    # Format: (filename, file_bytes, content_type)
                    filename, file_bytes, content_type = img_file
                    multipart.append(("files", (filename, file_bytes, content_type)))
                else:
                    # Assume it's a file-like object
                    multipart.append(("files", img_file))

        if image_files:
            file_names = []
            for part in multipart:
                if part[0] == "files":
                    try:
                        file_names.append(part[1][0])
                    except Exception:
                        file_names.append(str(part))
            logger.info(
                "MemePoster will upload %d file(s): %s",
                len(file_names),
                ", ".join(file_names),
            )
        else:
            logger.info("MemePoster will send request without image files")

        try:
            response = requests.post(
                url,
                cookies=self.cookies,
                files=multipart,
                timeout=timeout,
            )
            logger.info(
                "FSDS POST /meme/posts response | status=%s | body_preview=%r",
                response.status_code,
                (response.text[:300] + "...")
                if response.text and len(response.text) > 300
                else response.text,
            )

            if response.status_code in (200, 201):
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "data": response.json() if response.text else {}
                }
            else:
                raise MemePostException(f"Failed to post meme. Status: {response.status_code}, "
                                        f"Response: {response.text}")
        
        except requests.exceptions.Timeout:
            logger.error("Request timed out")
            raise MemePostException("Request timed out")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise MemePostException(f"Request failed: {str(e)}")
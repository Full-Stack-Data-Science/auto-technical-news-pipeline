from fsds.meme_poster import MemePoster
from fsds.session_cookies import get_session_cookies
import unittest


class TestMemePoster(unittest.TestCase):
    def setUp(self):
        self.poster = MemePoster(get_session_cookies())
    
    def test_fsds_api_connection(self):
        result = self.poster.test_api_connection()
        self.assertTrue(result)

from scraping.twitter.twitter_parser import TwitterParser
from common.config import Config

def main():
    # run_in_local = False <=> send commands to a remote
    # Selenium server that already has a browser
    with TwitterParser(run_in_local=True) as parser:
        parser.login(Config.TWITTER_EMAIL, Config.TWITTER_PASSWORD)

if __name__ == "__main__":
    main()
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DEBUG_DIR = os.path.join(os.path.dirname(__file__), "debug")
STORY_DIR = os.path.join(os.path.dirname(__file__), "story")
IG_URL = "https://www.instagram.com/"
MAX_PHOTO = 4
MAX_TWEET_LEN = 280

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
if not os.path.exists(DEBUG_DIR):
    os.makedirs(DEBUG_DIR)
if not os.path.exists(STORY_DIR):
    os.makedirs(STORY_DIR)

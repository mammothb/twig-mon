import json
import logging
import os
import re
import time
import urllib

import tweepy

from twigmon.const import DATA_DIR
from twigmon.utility import download_media

LOG = logging.getLogger("TwtStream")

class SListener(tweepy.StreamListener):
    def __init__(self, client, api=None):
        super().__init__(api)
        self.client = client

    def on_data(self, raw_data):
        data = json.loads(raw_data)
        if "in_reply_to_status_id" in data:
            self.on_status(data)

    def on_status(self, status):
        # ignore retweets
        if status.get("retweeted_status") is not None:
            return
        LOG.info("Tweet at %s", time.strftime(r"%Y%m%d-%H%M%S"))
        status_text = (status["extended_tweet"]["full_text"]
                       if status["truncated"] else status["text"])
        media_paths = list()
        if status.get("extended_entities") is not None:
            for media in status["extended_entities"]["media"]:
                if media["type"] == "photo":
                    url = media["media_url"]
                elif media["type"] == "video":
                    # video variants contains an .m3u8 element so we filter
                    # that out and download the video with the highest bitrate
                    url = sorted([d for d in media["video_info"]["variants"]
                                  if "bitrate" in d],
                                 key=lambda k: k["bitrate"])[-1]["url"]
                    # ignore extra substring behind the .mp4 extension
                    url = url[: url.index(".mp4")] + ".mp4"
                else:
                    continue
                media_path = os.path.join(DATA_DIR,
                                          urllib.parse.quote(url, safe=""))
                if download_media(url, media_path):
                    media_paths.append(media_path)
        # "de-link" all twitter handles with @/
        status_text = "@/{}: {}".format(
            status["user"]["screen_name"],
            re.sub(r"(?<=[@])(?=[^/])", r"/", status_text))
        tweet = {"text": status_text, "media": media_paths}
        self.client.tweets.append(tweet)
        self.client.has_update = True

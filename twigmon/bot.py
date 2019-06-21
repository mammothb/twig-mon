from itertools import islice
import logging
import math
import os
import re
import threading
import time
import urllib

import tweepy

from twigmon.const import MAX_PHOTO, MAX_TWEET_LEN, STORY_DIR
from twigmon.decorators import bg_task
from twigmon.plugins.igfeed import IgFeed
from twigmon.plugins.igstory import IgStory
from twigmon.plugins.twtstream import TwtStream

LOG = logging.getLogger("TwIgMon  ")

class TwIgMonitor(object):
    def __init__(self, token):
        auth = tweepy.auth.OAuthHandler(token["consumer_key"],
                                        token["consumer_secret"])
        auth.set_access_token(token["access_key"], token["access_secret"])
        self.api = tweepy.API(auth)
        self.threads = list()
        self.ig_feed = IgFeed()
        self.ig_story = IgStory()
        self.twt_stream = TwtStream()

    def run(self):
        t_ig_feed = threading.Thread(name="IgFeed", target=self.ig_feed.run)
        t_ig_feed.daemon = True
        t_ig_story = threading.Thread(name="IgStory",
                                      target=self.ig_story.run)
        t_ig_story.daemon = True
        t_twt_stream = threading.Thread(name="TwtStream",
                                        target=self.twt_stream.run)
        t_twt_stream.daemon = True
        t_poster = threading.Thread(name="TwIgMon", target=self.post)
        t_poster.daemon = True

        self.threads.append(t_ig_feed)
        self.threads.append(t_ig_story)
        self.threads.append(t_twt_stream)
        self.threads.append(t_poster)

        LOG.info("Starting threads")
        t_ig_feed.start()
        t_ig_story.start()
        t_twt_stream.start()
        t_poster.start()

        LOG.info("Threads started %s", self.threads)

        while True:
            pass

    def post_tweet(self, status_text, media_paths):
        media_uploads = list()
        try:
            for m_path in media_paths:
                media_uploads.append(self.api.upload_chunked(m_path))
                time.sleep(10)
            # when we're uploading our own media, remove all hyperlinks in the
            # tweet, even if they are not the original media
            if media_uploads:
                status_text = re.sub(r"https\S+", "", status_text)
            if len(status_text) > MAX_TWEET_LEN:
                idx = status_text[: MAX_TWEET_LEN - 3].rfind(" ")
                status_text_1 = status_text[: idx] + "..."
                # Tweet the first half so we can get the tweet id to form
                # a thread
                tweet = self.api.update_status(status_text_1)
                status_text_2 = "@{} ...{}".format(tweet.user.screen_name,
                                                   status_text[idx :])
                self.api.update_status(
                    status_text_2, tweet.id_str,
                    media_ids=[m.media_id for m in media_uploads])
            else:
                self.api.update_status(
                    status_text, media_ids=[m.media_id
                                            for m in media_uploads])
            LOG.info("%s Posted tweet: %s", time.strftime(r"%Y%m%d-%H%M%S"),
                     status_text)
        except tweepy.error.TweepError as err:
            if err.api_code == 187:  # duplicate tweet
                pass
        time.sleep(10)

    @bg_task(600)
    def post(self):
        time.sleep(60)
        while not self.ig_feed.posts.empty():
            feed_data = self.ig_feed.posts.get()
            video_paths = [m_path for m_path in feed_data["source"]
                           if ".mp4" in m_path]
            photo_paths = [m_path for m_path in feed_data["source"]
                           if ".jpg" in m_path]
            # split list into uneven groups, from:
            # https://stackoverflow.com/questions/38861457
            it_photo_paths = iter(photo_paths)
            n_photo_list = [
                min(MAX_PHOTO, len(photo_paths) - i * MAX_PHOTO)
                for i in range(math.ceil(len(photo_paths) / MAX_PHOTO))]
            photo_paths = [
                sli for sli in (list(islice(it_photo_paths, 0, i))
                                for i in n_photo_list)]
            total = len(video_paths) + len(photo_paths)
            counter = 1
            for video_path in video_paths:
                status_text = "ig_feed ({}/{}): {}".format(
                    counter, total, feed_data["caption"])
                self.post_tweet(status_text, [video_path])
                counter += 1
            for photo_path in photo_paths:
                status_text = "ig_feed ({}/{}): {}".format(
                    counter, total, feed_data["caption"])
                self.post_tweet(status_text, photo_path)
                counter += 1

            # remove the downloaded media after tweeting since we will
            # not be overwriting them
            for media_path in feed_data["source"]:
                os.remove(media_path)

#        while not self.ig_story.stories.empty():
#            story = self.ig_story.stories.get()
#            media_path = os.path.join(STORY_DIR,
#                                      urllib.parse.quote(story, safe=""))
#            status_text = "ig_story: {}".format(
#                time.strftime(r"%Y%m%d-%H%M%S"))
#            self.post_tweet(status_text, [media_path])

        while not self.twt_stream.tweets.empty():
            tweet = self.twt_stream.tweets.get()
            self.post_tweet(tweet["text"], tweet["media"])
            # remove the downloaded media after tweeting since we will
            # not be overwriting them
            for media_path in tweet["media"]:
                os.remove(media_path)

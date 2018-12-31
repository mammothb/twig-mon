import logging
from queue import Queue
import time

import tweepy

from twigmon.config import READ_KEY, USER
from twigmon.plugins.slistener import SListener

LOG = logging.getLogger("TwtStream")

class TwtStream(object):
    def __init__(self):
        self.tweets = Queue()
        self.auth = tweepy.auth.OAuthHandler(READ_KEY["consumer_key"],
                                             READ_KEY["consumer_secret"])
        self.auth.set_access_token(READ_KEY["access_key"],
                                   READ_KEY["access_secret"])
        self.api = tweepy.API(self.auth)
        self.listener = SListener(self, self.api, USER["twt"])
        self.stream = tweepy.Stream(self.auth, self.listener)

    def run(self):
        while not self.stream.running:
            try:
                LOG.info("%s Streaming started", time.strftime("%Y%m%d-%H%M%S"))
                self.stream.filter(follow=USER["twt"])
            except Exception as exception:  # pylint: disable=W0703
                logging.exception(exception)
                continue

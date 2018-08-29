#!/usr/bin/python3
import logging

from twigmon.bot import TwIgMonitor
from twigmon.config import POST_KEY

logging.basicConfig(level=logging.INFO)

MONITOR = TwIgMonitor(token=POST_KEY)
MONITOR.run()

from functools import wraps
import logging
import random
import time

LOG = logging.getLogger("TwIg")

def bg_task(sleep_time, ignore_errors=True):
    def actual_decorator(func):
        @wraps(func)
        def wrapper(self):
            while True:
                rand_sleep = sleep_time + random.randrange(sleep_time * 0.1)
                if ignore_errors:
                    try:
                        func(self)
                    except Exception as exception:  # pylint: disable=W0703
                        LOG.info("An error occured in the %s bg task "
                                 "retrying in %d seconds", func.__name__,
                                 rand_sleep)
                        LOG.exception(exception)
                else:
                    func(self)
                time.sleep(rand_sleep)
        return wrapper
    return actual_decorator

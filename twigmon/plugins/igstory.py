import filecmp
import logging
import os
from queue import Queue
import random
import shelve
import time
import urllib

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from twigmon.config import IG_LOGIN, USER
from twigmon.const import DATA_DIR, DEBUG_DIR, IG_URL, STORY_DIR
from twigmon.decorators import bg_task
from twigmon.utility import download_media, timedelta

LOG = logging.getLogger("IgStory  ")

class IgStory(object):
    indicator_class = "_7zQEa"

    def __init__(self, last_clean_up=None):
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--mute-audio")
        self.driver = webdriver.Chrome(options=chrome_options)
        # pylint: disable=C0103
        self.db = shelve.open(os.path.join(DATA_DIR, "ig_story_db"))
        self.last_clean_up = (time.gmtime() if last_clean_up is None
                              else last_clean_up)
        self.stories = Queue()
        self._is_logged_in = False

    def login(self):
        self.driver.get(IG_URL + "accounts/login")
        username = self.driver.find_element_by_xpath(
            "//input[@name='username']")
        password = self.driver.find_element_by_xpath(
            "//input[@name='password']")
        btn_login = self.driver.find_element_by_xpath("//button[1]")

        username.send_keys(IG_LOGIN["username"])
        password.send_keys(IG_LOGIN["password"])
        btn_login.click()

        # Wait for login process
        time.sleep(10 + random.randrange(10))
        self._is_logged_in = True
        LOG.info("%s Logged in to IG", time.strftime(r"%Y%m%d-%H%M%S"))

    def _clean_up(self):
        counter = 0
        for key in self.db:
            if time.strptime(self.db[key], r"%Y-%m-%dT%H:%M:%S") < self.last_clean_up:
                counter += 1
                del self.db[key]
                try:
                    os.remove(os.path.join(STORY_DIR,
                                           urllib.parse.quote(key, safe="")))
                except FileNotFoundError:
                    pass
        LOG.info("%s Cleaned up %d entries", time.strftime(r"%Y%m%d-%H%M%S"),
                 counter)

    def _get_stories(self, url):
        stories = list()
        self.driver.get(url)
        if "stories" not in self.driver.current_url:
            LOG.info("%s No stories", time.strftime(r"%Y%m%d-%H%M%S"))
            self._clean_up()
        else:
            try:
                WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.CLASS_NAME,
                                                    self.indicator_class)))
            except TimeoutException:
                return stories
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            num_story = len(soup.find_all(
                "div", attrs={"class", self.indicator_class}))
            for i in range(num_story):
                time.sleep(0.5)
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                with open(os.path.join(
                    DEBUG_DIR, "ig_story{}.html".format(i)), "w",
                          encoding="utf-8") as outfile:
                    outfile.write(self.driver.page_source)
                # Try for video story, then look for image story
                try:
                    src = soup.find("source")["src"]
                    stories.append(src)
                except TypeError:
                    # First <img> is the profile picture, we'll skip that
                    src = soup.find_all("img")[-1]["src"]
                    stories.append(src)
                btn_next = self.driver.find_element_by_xpath(
                    "//div[contains(concat(' ', @class, ' '), "
                    "' coreSpriteRightChevron ')]/..")
                btn_next.click()
        return stories

    def _check_new_stories(self, stories):
        new_stories = list()
        for url in stories:
            # use original url only for downloading, and use truncated
            # url for everything else
            trunc_url = url[: url.index("?")]
            if trunc_url in self.db:
                continue
            story_quote = urllib.parse.quote(trunc_url, safe="")
            media_path = os.path.join(DATA_DIR, story_quote)
            if download_media(url, media_path):
                # use filecmp to compare file content with previously
                # downloaded media to make sure it's not just the same
                # media with different source url
                is_found = False
                for file in os.listdir(STORY_DIR):
                    if filecmp.cmp(os.path.join(STORY_DIR, file), media_path,
                                   shallow=False):
                        is_found = True
                        os.remove(media_path)
                        break
                if not is_found:
                    self.db[trunc_url] = time.strftime("%Y-%m-%dT%H:%M:%S",
                                                       time.gmtime())
                    new_stories.append(trunc_url)
                    os.rename(media_path, os.path.join(STORY_DIR,
                                                       story_quote))
        if stories:
            LOG.info("%s %d new stories", time.strftime("%Y%m%d-%H%M%S"),
                     len(new_stories))
        return new_stories

    @bg_task(600)
    def run(self):
        if not self._is_logged_in:
            self.login()
        if timedelta(time.gmtime(), self.last_clean_up) > 48 * 60 * 60:
            self._clean_up()
            self.last_clean_up = time.gmtime()
        stories = self._get_stories(IG_URL + "stories/" + USER["ig"])
        stories = self._check_new_stories(stories)
        for story in stories:
            self.stories.put(story)

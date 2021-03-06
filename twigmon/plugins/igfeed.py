import json
import logging
import os
import os.path
from queue import Queue
import random
import time
import urllib

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By

from twigmon.config import IG_LOGIN, USER
from twigmon.const import DATA_DIR, DEBUG_DIR, IG_URL
from twigmon.decorators import bg_task
from twigmon.utility import download_media

LOG = logging.getLogger("IgFeed   ")

class IgFeed(object):
    def __init__(self, last_update=None):
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--log-level=3")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.last_update = (time.gmtime() if last_update is None
                            else last_update)
        self.posts = Queue()

    def login(self):
        self.driver.get(IG_URL + "accounts/login")
        # wait for page to load
        time.sleep(5)
        with open(os.path.join(DEBUG_DIR, "ig_login.html"), "w",
                  encoding="utf-8") as outfile:
            outfile.write(self.driver.page_source)
        username = self.driver.find_element(By.XPATH,
                                            "//input[@name='username']")
        password = self.driver.find_element(By.XPATH,
                                            "//input[@name='password']")
        btn_login = self.driver.find_element(By.XPATH, "//button[1]")

        username.send_keys(IG_LOGIN["username"])
        password.send_keys(IG_LOGIN["password"])
        btn_login.click()

        # Wait for login process
        time.sleep(10 + random.randrange(10))
        LOG.info("%s Logged in to IG", time.strftime(r"%Y%m%d-%H%M%S"))

    def _query_page(self, url):
        self.driver.get(url)
        with open(os.path.join(DEBUG_DIR, "ig_feed.html"), "w",
                  encoding="utf-8") as outfile:
            outfile.write(self.driver.page_source)
        return list(MediaPost.parse_html(self.driver.page_source,
                                         self.driver))

    def _is_logged_out(self, url):
        self.driver.get(url)
        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        logo = soup.find("h1", attrs={"class": "coreSpriteLoggedOutWordmark"})
        return logo is None

    @bg_task(120)
    def run(self):
        url = IG_URL + USER["ig"]
        if not self._is_logged_out(url):
            self.login()

        media_posts = self._query_page(url)

        counter = 0
        for post in media_posts:
            if post.timestamp <= self.last_update:
                break
            counter += 1
            media_paths = list()
            for url in post.source:
                media_path = os.path.join(DATA_DIR,
                                          urllib.parse.quote(url, safe=""))
                media_path = media_path[: media_path.index("%3F")]
                if download_media(url, media_path):
                    media_paths.append(media_path)
            data = {
                "timestamp": time.strftime(r"%Y-%m-%dT%H:%M:%S",
                                           post.timestamp),
                "caption": post.caption,
                "source": media_paths
            }
            self.posts.put(data)
            with open(os.path.join(DEBUG_DIR, "ig_post.json"), "w",
                      encoding="utf-8") as outfile:
                outfile.write(json.dumps(data))
        LOG.info("%s Fetched %d new feed posts",
                 time.strftime(r"%Y%m%d-%H%M%S"), counter)
        if media_posts:
            self.last_update = media_posts[0].timestamp

class MediaPost(object):
    caption_class = "C4VMK"
    img_class = "FFVAD"
    indicator_class = "Yi5aA"
    post_class = "v1Nh3 kIKUG _bz0w"  # Posts from main feed page
    video_class = "tWeCl"

    def __init__(self, timestamp, caption, source):
        self.timestamp = timestamp
        self.caption = caption
        self.source = source

    @classmethod
    def parse_soup(cls, idx, post, driver):
        driver.get(IG_URL + post.find("a")["href"][1 :])
        with open(os.path.join(DEBUG_DIR, "ig_post{}.html".format(idx)), "w",
                  encoding="utf-8") as outfile:
            outfile.write(driver.page_source)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        timestamp = time.strptime(soup.find("time")["datetime"][: -5],
                                  "%Y-%m-%dT%H:%M:%S")
        caption = soup.find("div", attrs={"class", cls.caption_class})
        # Handle instances where posts have no caption
        caption = "" if caption is None else caption.find("span").text

        source = list()
        num = max(1, len(soup.find_all("div", attrs={"class",
                                                     cls.indicator_class})))
        for i in range(num):
            if soup.find("video"):
                source.extend([video["src"] for video in soup.find_all(
                    "video", attrs={"class", cls.video_class})])
            if soup.find("img"):
                source.extend([img["src"] for img in soup.find_all(
                    "img", attrs={"class", cls.img_class})])
            # click through the album to get all media
            if num > 1 and i < num - 1:
                # https://stackoverflow.com/questions/1604471
                btn_next = driver.find_element_by_xpath(
                    "//div[contains(concat(' ', @class, ' '), "
                    "' coreSpriteRightChevron ')]/..")
                btn_next.click()
                time.sleep(0.5)
                soup = BeautifulSoup(driver.page_source, "html.parser")
        source = list(set(source))
        return cls(timestamp=timestamp, caption=caption, source=source)

    @classmethod
    def parse_html(cls, html, driver):
        soup = BeautifulSoup(html, "html.parser")
        posts = soup.find_all("div", attrs={"class": cls.post_class})
        if posts:
            for i, post in enumerate(posts):
                try:
                    yield cls.parse_soup(i, post, driver)
                except AttributeError:
                    # Discard incomplete info
                    pass

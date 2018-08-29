import time

import requests

def timedelta(new_time, old_time):
    return time.mktime(new_time) - time.mktime(old_time)

def download_media(url, media_path):
    req = requests.get(url, stream=True)
    if req.status_code == 200:
        with open(media_path, "wb") as outmedia:
            for chunk in req:
                outmedia.write(chunk)
        return True
    else:
        return False

#! /usr/bin/env python

import requests
import os
from time import sleep

bearer_token = os.environ['SPOTIFYTOKEN']

headers = {'Authorization': 'Bearer {}'.format(bearer_token)}

base_url = "https://api.spotify.com/v1/me/tracks"
request_url = base_url
params = {'limit': 1}

while request_url:
    response = requests.get(base_url,
                            headers=headers,
                            params=params)
    if response.status_code == 429:
        retry_time = response.headers['retry-after']
        sleep(retry_time)
        continue

    if response.status_code == 200:
        data = response.json()
    else:
        raise RuntimeError('received {}, {}'.format(response.status_code,
                                                    response.text))

    request_url = data['next']

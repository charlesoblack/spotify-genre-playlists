#! /usr/bin/env python

import multiprocessing


def api_get_tracks(mng, q):
    from time import sleep
    import requests
    import os

    bearer_token = os.environ['SPOTIFYTOKEN']

    headers = {'Authorization': 'Bearer {}'.format(bearer_token)}
    base_url = "https://api.spotify.com/v1/me/tracks"
    request_url = base_url
    params = {'limit': 10}

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

        for track in data['items']:
            q.put(track)
        break

        request_url = data['next']
    mng.put('DONE')
    return


if __name__ == '__main__':
    q = multiprocessing.Queue()
    mng = multiprocessing.Queue()
    p1 = multiprocessing.Process(target=api_get_tracks, args=(mng, q))
    p1.start()
    while mng.get() != 'DONE':
        pass
    p1.terminate()
    p1.join()

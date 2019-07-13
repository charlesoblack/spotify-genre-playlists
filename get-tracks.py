#! /usr/bin/env python

import multiprocessing


def api_request(url, headers, params):
    import requests
    from time import sleep

    response = requests.get(url,
                            headers=headers,
                            params=params)
    if response.status_code == 429:
        retry_time = response.headers['retry-after']
        sleep(retry_time)
        response = requests.get(url,
                                headers=headers,
                                params=params)

    if response.status_code == 200:
        data = response.json()
    else:
        raise RuntimeError('received {}, {}, {}'.format(url,
                                                        response.status_code,
                                                        response.text))
    return data


def api_get_tracks(mng, q):
    import os

    bearer_token = os.environ['SPOTIFYTOKEN']

    headers = {'Authorization': 'Bearer {}'.format(bearer_token)}
    base_url = "https://api.spotify.com/v1/me/tracks"
    request_url = base_url
    params = {'limit': 10}

    while request_url:
        data = api_request(request_url, headers, params)
        for item in data['items']:
            q.put(item['track']['id'])

        request_url = None  # data['next']

    mng.put('SAVED TRACKS DONE')
    return


def api_get_track_features(mng, q, results):
    from queue import Empty
    import os

    bearer_token = os.environ['SPOTIFYTOKEN']

    tracks = []
    while True:
        while len(tracks) < 10:
            try:
                tracks.append(q.get(block=False))
            except Empty:
                pass

        if tracks:
            headers = {'Authorization': 'Bearer {}'.format(bearer_token)}
            base_url = "https://api.spotify.com/v1/audio-features"
            params = {'ids': ','.join(tracks)}

            data = api_request(base_url, headers, params)

            for feature_set in data['audio_features']:
                results.put(feature_set)
            tracks = []
            break

    mng.put('FEATURES DONE')
    return


if __name__ == '__main__':
    q = multiprocessing.Queue()
    mng = multiprocessing.Queue()
    results = multiprocessing.Queue()

    api_get_saved = multiprocessing.Process(target=api_get_tracks,
                                            args=(mng, q))
    api_get_saved.start()

    api_get_features = multiprocessing.Process(target=api_get_track_features,
                                               args=(mng, q, results))
    api_get_features.start()

    processes = [api_get_saved, api_get_features]

    while any(process.is_alive() for process in processes):
        try:
            event = mng.get(block=False, timeout=1)
            if event == 'SAVED TRACKS DONE':
                print('saved tracks done', flush=True)
                api_get_saved.terminate()
                api_get_saved.join()
            elif event == 'FEATURES DONE':
                print('features done', flush=True)
                api_get_features.terminate()
                api_get_features.join()
        except:  # noqa
            pass
        pass

    print(results.get())

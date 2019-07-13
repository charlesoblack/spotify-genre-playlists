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
        return 'received {}, {}, {}'.format(url,
                                            response.status_code,
                                            response.text)
    return data


def api_get_tracks(mng, q):
    import os

    bearer_token = os.environ['SPOTIFYTOKEN']

    headers = {'Authorization': 'Bearer {}'.format(bearer_token)}
    base_url = "https://api.spotify.com/v1/me/tracks"
    request_url = base_url
    params = {'limit': 50}

    print('getting tracks', flush=True)

    while request_url:
        data = api_request(request_url, headers, params)

        if isinstance(data, str):
            mng.append('TERMINATE')
            raise RuntimeError(data)

        for item in data['items']:
            q.put(item['track']['id'])

        request_url = data['next']

    mng.append('SAVED TRACKS DONE')
    return


def api_get_track_features(mng, q, results):
    from queue import Empty
    import os

    bearer_token = os.environ['SPOTIFYTOKEN']

    tracks = []
    tracks_processed = 0
    print('getting track features', flush=True)
    while True:
        while len(tracks) < 100:
            try:
                tracks.append(q.get(block=False))
            except Empty:
                if 'SAVED TRACKS DONE' in mng:
                    break

        if tracks:
            tracks_processed += len(tracks)
            print(tracks_processed, flush=True)
            headers = {'Authorization': 'Bearer {}'.format(bearer_token)}
            base_url = "https://api.spotify.com/v1/audio-features"
            params = {'ids': ','.join(tracks)}

            data = api_request(base_url, headers, params)

            if isinstance(data, str):
                mng.append('TERMINATE')
                raise RuntimeError(data)

            for feature_set in data['audio_features']:
                results.append(feature_set)
            tracks = []

        if 'SAVED TRACKS DONE' in mng:
            break

    mng.append('FEATURES DONE')
    return


if __name__ == '__main__':
    import pickle

    q = multiprocessing.Queue()
    results = []
    mng = multiprocessing.Manager().list()

    api_get_saved = multiprocessing.Process(target=api_get_tracks,
                                            args=(mng, q))
    api_get_saved.start()

    api_get_features = multiprocessing.Process(target=api_get_track_features,
                                               args=(mng, q, results))
    api_get_features.start()

    processes = [api_get_saved, api_get_features]

    while any(process.is_alive() for process in processes):
        if 'SAVED TRACKS DONE' in mng and api_get_saved.is_alive():
            print('saved tracks done', flush=True)
            api_get_saved.terminate()
            api_get_saved.join()
        if 'FEATURES DONE' in mng and api_get_features.is_alive():
            print('features done', flush=True)
            api_get_features.terminate()
            api_get_features.join()
        if 'TERMINATE' in mng:
            print('terminated', flush=True)
            [process.terminate() for process in processes]
            [process.join() for process in processes]

    result_dict = {result['uri']: result for result in results}

    with open('user-data.pckl', 'wb') as f:
        pickle.dump(result_dict, f, protocol=-1)

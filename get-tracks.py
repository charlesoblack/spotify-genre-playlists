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


def api_get_tracks(mng, q, q2, spotifytoken):
    bearer_token = spotifytoken

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
            q2.put((item['track']['artists'][0]['name'],
                    item['track']['name']))

        request_url = data['next']

    mng.append('SAVED TRACKS DONE')
    return


def api_get_track_features(mng, q, results, spotifytoken):
    from queue import Empty

    bearer_token = spotifytoken

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
            print('track features: {}'.format(tracks_processed), flush=True)
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


def api_get_lastfm_tags(mng, q, results, lastfmkey):
    from queue import Empty
    import requests
    from time import sleep

    api_key = lastfmkey

    track = None
    tracks_processed = 0
    print('getting track tags from last.fm', flush=True)
    while True:
        try:
            track = q.get(block=False)
        except Empty:
            if 'SAVED TRACKS DONE' in mng:
                break

        if track:
            print('track tags: {}'.format(tracks_processed), flush=True)
            base_url = "http://ws.audioscrobbler.com/2.0/"
            headers = {'User-Agent': 'Spotify Genre Playlist Generator'}
            params = {'method': 'track.gettoptags',
                      'artist': '+'.join(track[0].split(' ')),
                      'track': '+'.join(track[1].split(' ')),
                      'format': 'json',
                      'api_key': api_key,
                      'autocorrect': '1'}
            params_str = '&'.join([k + '=' + v for k, v in params.items()])
            url = base_url + '?' + params_str
            resp = requests.get(url, headers=headers)

            if resp.status_code != 200:
                print('error {}, {}, {}'.format(url,
                                                resp.status_code,
                                                resp.text))
                q.put(track)
            else:
                tracks_processed += 1
                data = resp.json()
                if 'error' not in data:
                    data = data['toptags']
                    i = min(3, len(data['tag']))
                    result = tuple(data['tag'][x]['name'] for x in range(i))
                    results.append((track, result))
                elif data['error'] == 29:
                    print('rate limited')
                    sleep(1)
                    q.put(track)
                elif data['error'] == 6:
                    print('track {} not found'.format(track))
                    print(data)
                    print(resp.url)

        track = None

    mng.append('TAGS DONE')
    return


if __name__ == '__main__':
    import pickle
    import sys

    if len(sys.argv) < 3:
        print('missing one of the api keys')
        sys.exit()
    else:
        spotifytoken = sys.argv[1]
        lastfmkey = sys.argv[2]

    q = multiprocessing.Queue()
    q2 = multiprocessing.Queue()
    results = multiprocessing.Manager().list()
    tag_results = multiprocessing.Manager().list()
    mng = multiprocessing.Manager().list()

    api_get_saved = multiprocessing.Process(target=api_get_tracks,
                                            args=(mng, q, q2, spotifytoken))
    api_get_saved.start()

    api_get_features = multiprocessing.Process(target=api_get_track_features,
                                               args=(mng,
                                                     q,
                                                     results,
                                                     spotifytoken))
    api_get_features.start()

    api_get_tags = multiprocessing.Process(target=api_get_lastfm_tags,
                                           args=(mng,
                                                 q2,
                                                 tag_results,
                                                 lastfmkey))
    api_get_tags.start()

    processes = [api_get_saved, api_get_features, api_get_tags]

    while any(process.is_alive() for process in processes):
        if 'SAVED TRACKS DONE' in mng and api_get_saved.is_alive():
            print('saved tracks done', flush=True)
            api_get_saved.terminate()
            api_get_saved.join()
        if 'FEATURES DONE' in mng and api_get_features.is_alive():
            print('features done', flush=True)
            api_get_features.terminate()
            api_get_features.join()
        if 'TAGS DONE' in mng and api_get_tags.is_alive():
            print('tags done', flush=True)
            api_get_tags.terminate()
            api_get_tags.join()
        if 'TERMINATE' in mng:
            print('terminated', flush=True)
            [process.terminate() for process in processes]
            [process.join() for process in processes]

    result_dict = {result['uri']: result for result in results}
    tag_dict = list(tag_results)

    with open('user-data.pckl', 'wb') as f:
        pickle.dump(result_dict, f, protocol=-1)

    with open('tag-data.pckl', 'wb') as f:
        pickle.dump(tag_dict, f, protocol=-1)

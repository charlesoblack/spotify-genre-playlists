#! /usr/bin/env python


def put_playlist(song_uris):
    import requests
    import os

    url = "https://api.spotify.com/v1/playlists/{}/tracks"
    url = url.format('67q0rVnjWAaJeOExGhcIC5')

    bearer_token = os.environ['SPOTIFYTOKEN']

    headers = {'Authorization': 'Bearer {}'.format(bearer_token),
               'Content-Type': 'application/json'}
    body = {'uris': song_uris}

    response = requests.put(url,
                            json=body,
                            headers=headers)

    if response.status_code != 201:
        return 'received {}, {}, {}'.format(url,
                                            response.status_code,
                                            response.text)
    return 'success'


if __name__ == '__main__':
    import pickle
    import random

    with open('user-data.pckl', 'rb') as f:
        data = pickle.load(f)

    payload = [random.choice(list(data.keys())) for uri in range(10)]
    result = put_playlist(payload)
    print(result, flush=True)

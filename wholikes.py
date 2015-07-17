from gevent.pool import Pool
import gevent.monkey
gevent.monkey.patch_all()

import os
import sys
import calendar
import time
import operator

import ujson as json
import requests

#requests.packages.urllib3.disable_warnings()

BASE_ENDPOINT = 'https://api.instagram.com/v1'
INSTAGRAM_CLIENT_ID = os.getenv('INSTAGRAM_CLIENT_ID_BKUP')
INSTAGRAM_CLIENT_SECRET = os.getenv('INSTAGRAM_CLIENT_SECRET_BKUP')


def get_base_args():
    return {
        'client_id': INSTAGRAM_CLIENT_ID,
        'client_secret': INSTAGRAM_CLIENT_SECRET
    }


def get_response(endpoint, params={}):
    if params != {}:
        r = requests.get(endpoint, params=params)
    else:
        r = requests.get(endpoint)
    tries = 0
    max_tries = 5
    while tries < max_tries:
        try:
            if r.status_code == 400:
                return json.loads(r.content)
            if r.status_code == 404:
                return HI
            r.raise_for_status()
            break
        except:
            print r
            print r.content
            print endpoint
            print params
            print 'Received bad status_code. Sleeping \
                    for 5 seconds.'

            time.sleep(5)
            if params:
                r = requests.get(endpoint, params=params)
            else:
                r = requests.get(endpoint)
            tries += 1
    print endpoint
    print params
    print r
    return json.loads(r.content)


def get_next_page_data(response):
    try:
        return response['pagination']
    except:
        print 'No pagination data!'
        return None


def get_user_id(username, access_token):
    endpoint = BASE_ENDPOINT + '/users/search'
    args = {'access_token': access_token}
    args['q'] = username
    data = get_response(endpoint, args)
    data = data['data']

    if len(data) > 0:
        return data[0]['id']


def get_user_data(user_id, access_token):
    endpoint = BASE_ENDPOINT + '/users/' + str(user_id)
    args = {'access_token': access_token}
    resp = get_response(endpoint, args)
    if resp and resp.get('data', None):
        return resp['data']
    else:
        return {}


def get_username(user_id, access_token):
    data = get_user_data(user_id, access_token)
    if data == {}:
        return user_id
    return data['username']


def get_num_follows(user_id, access_token):
    data = get_user_data(user_id, access_token)
    return data['counts']['follows']


def get_num_followers(user_id, access_token):
    data = get_user_data(user_id, access_token)
    return data['counts']['followers']


"""
Returns a list of user_ids that a user follows.
"""


def get_user_ids_followed(user_id, num_follows, access_token):
    endpoint = BASE_ENDPOINT + '/users/' + str(user_id) + '/follows'
    args = {'access_token': access_token}
    resp = get_response(endpoint, args)
    next_page = get_next_page_data(resp)

    user_ids = []
    ctr = 0
    while (next_page != None) or (ctr == 0):
        for item in resp['data']:
            user_ids.append(item['id'])
        if len(set(user_ids)) >= num_follows - 10:  #todo fix
            break
        else:
            if next_page.get('next_url', None):
                resp = get_response(next_page['next_url'], None)
                next_page = get_next_page_data(resp)
        ctr += 1
    return set(user_ids)


"""
Returns a list of user_ids that follow a user.
"""


def get_users_ids_followers(user_id, num_followers, access_token):
    endpoint = BASE_ENDPOINT + '/users/' + str(user_id) + '/followers'
    args = {'access_token': access_token}
    resp = get_response(endpoint, args)
    next_page = first_next_page

    user_ids = []
    ctr = 0
    while (next_page != None) or (ctr == 0):
        for item in resp['data']:
            user_ids.append(item['id'])
        if len(set(user_ids)) >= num_followers:
            break
        else:
            if next_page.get('next_url', None):
                resp = get_response(next_page['next_url'], None)
                next_page = get_next_page_data(resp)
        ctr += 1
    return user_ids


"""
Returns JSON list of a user's most recent posts.
"""


def get_latest_media_ids(user_id, num_images, access_token):
    endpoint = BASE_ENDPOINT + '/users/' + str(user_id) + '/media/recent'
    args = {'access_token': access_token}
    args['count'] = num_images
    resp = get_response(endpoint, args)
    if resp == []:
        return []
    return [media['id'] for media in resp['data']]


"""
Get a list of users that liked a post.
"""


def get_user_ids_that_like(item):
    media_id, access_token = item

    if media_id != -1:
        endpoint = BASE_ENDPOINT + '/media/' + str(media_id) + '/likes'
        args = {'access_token': access_token}
        resp = get_response(endpoint, args)
        if resp and resp.get('data', None):
            return [user['id'] for user in resp['data']]
    return [None]


"""
Returns a sorted list of users that provide the most likes.
"""


def sort_likes(like_dict):
    return sorted(like_dict.items(), key=operator.itemgetter(1), reverse=True)


def yield_latest_media_ids(user_id, num_images, access_token):
    endpoint = BASE_ENDPOINT + '/users/' + str(user_id) + '/media/recent'
    args = {'access_token': access_token}
    args['count'] = num_images
    resp = get_response(endpoint, args)
    if resp.get('data', None) == None:
        yield (-1, access_token)
    else:
        for media in resp['data']:
            yield (media['id'], access_token)


def who_do_i_like(access_token):
    like_dict = {}
    endpoint = BASE_ENDPOINT + '/users/self/media/liked'
    resp = get_response(endpoint, {'access_token': access_token})
    next_url = resp['pagination']['next_url']

    user_ids = []
    for i in range(0, 3):
        resp = get_response(next_url)
        next_url = resp['pagination']['next_url']

        user_ids += [u['user']['username'] for u in resp['data']]

    return set(user_ids)


def who_does_user_like(username, access_token):
    like_dict = {}
    target_user_id = get_user_id(username, access_token)
    num_follows = get_num_follows(target_user_id, access_token)
    user_ids_followed = get_user_ids_followed(target_user_id, num_follows,
                                              access_token)

    fetch_pool = Pool(100)

    for user_id in user_ids_followed:
        for user_ids in fetch_pool.imap_unordered(
            get_user_ids_that_like, yield_latest_media_ids(user_id, 10,
                                                           access_token)):
            if user_ids and target_user_id in user_ids:
                try:
                    like_dict[user_id] += 1
                except:
                    like_dict[user_id] = 1

    top_ten = sort_likes(like_dict)
    if len(top_ten) > 10:
        top_ten = sort_likes(like_dict)

    user_names = []
    for item in top_ten:
        user_id, like_count = item
        user_names.append(get_username(user_id, access_token))
    return user_names


def who_likes_user(username, access_token):
    like_dict = {}
    target_user_id = get_user_id(username, access_token)
    fetch_pool = Pool(100)

    for user_ids in fetch_pool.imap_unordered(
        get_user_ids_that_like, yield_latest_media_ids(target_user_id, 30,
                                                       access_token)):
        for user_id in user_ids:
            try:
                like_dict[user_id] += 1
            except:
                like_dict[user_id] = 1

    top_ten = sort_likes(like_dict)
    if len(top_ten) > 10:
        top_ten = sort_likes(like_dict)[:10]

    user_ids = []
    user_names = []
    for item in top_ten:
        user_id, like_count = item
        user_ids.append(user_id)
        user_names.append(get_username(user_id, access_token))
    return user_names


if __name__ == "__main__":
    usage = 'usage: python wholikes.py followers|followed user_name'
    if len(sys.argv) == 3:
        if sys.argv[1] in ['followers', 'followed']:
            if sys.argv[1] == 'followers':
                who_likes_user(sys.argv[2])
            else:
                who_does_user_like(sys.argv[2])
        else:
            print usage
    else:
        print usage

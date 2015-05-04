import os
import sys
import calendar
import time
import operator

import ujson as json
import requests

BASE_ENDPOINT = 'https://api.instagram.com/v1'
INSTAGRAM_CLIENT_ID = os.getenv('INSTAGRAM_CLIENT_ID')
INSTAGRAM_CLIENT_SECRET = os.getenv('INSTAGRAM_CLIENT_SECRET')

def get_base_args():
    return {
            'client_id': INSTAGRAM_CLIENT_ID,
            'client_secret': INSTAGRAM_CLIENT_SECRET }

def get_response(endpoint, params):
    print endpoint
    if params:
        r = requests.get(endpoint, params=params)
    else:
        r = requests.get(endpoint)
    tries = 0
    max_tries = 5
    while tries < max_tries:
        try:
            if r.status_code == 400:
                return []
            r.raise_for_status()
            break
        except:
            print 'Received status_code {}. Sleeping \
                    for {} seconds.'.format(r.status_code, 5)
            time.sleep(5)
            if params:
                r = requests.get(endpoint, params=params)
            else:
                r = requests.get(endpoint)
            tries += 1

    return json.loads(r.content)

def get_next_page_data(response):
    try:
        'getting next page'
        return response['pagination']
        print response['pagination']
    except:
        print 'No pagination data!'
        return None

def get_user_id(username):
    endpoint = BASE_ENDPOINT + '/users/search'
    args = get_base_args()
    args['q'] = username
    data = get_response(endpoint, args)['data']
    if len(data) > 0:
        return data[0]['id']

def get_user_data(user_id):
    endpoint = BASE_ENDPOINT + '/users/{}'\
            .format(user_id)
    args = get_base_args()
    resp = get_response(endpoint, args)
    if not resp == []:
        return resp['data']
    else:
        return []

def get_username(user_id):
    data = get_user_data(user_id)
    if data == []:
        return 'n/a'
    return data['username']

def get_num_follows(user_id):
    data = get_user_data(user_id)
    return data['counts']['follows']

def get_num_followers(user_id):
    data = get_user_data(user_id)
    return data['counts']['followers']

"""
Returns a list of user_ids that a user follows.
"""
def get_user_ids_followed(user_id, num_follows):
    endpoint = BASE_ENDPOINT + '/users/{}/follows'\
            .format(user_id)
    args = get_base_args()
    resp = get_response(endpoint, args)
    next_page = get_next_page_data(resp)
    
    user_ids = []
    ctr = 0
    while (next_page != None) or (ctr == 0):
        for item in resp['data']:
            user_ids.append(item['id'])
        print 'num_users: {}'.format(len(set(user_ids)))
        print 'num_follows: {}'.format(num_follows)
        if len(set(user_ids)) >= num_follows - 10: #todo fix
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
def get_users_ids_followers(user_id, num_followers):
    endpoint = BASE_ENDPOINT + '/users/{}/followers'\
            .format(user_id)
    args = get_base_args()
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
def get_latest_media_ids(user_id, num_images):
    endpoint = BASE_ENDPOINT + '/users/{}/media/recent'\
            .format(user_id)
    args = get_base_args()
    args['count'] = num_images
    resp = get_response(endpoint, args)
    if resp == []:
        return []
    return [media['id'] for media in resp['data']]


"""
Get a list of users that liked a post.
"""
def get_user_ids_that_like(media_id):
    endpoint = BASE_ENDPOINT + '/media/{}/likes'\
            .format(media_id)
    args = get_base_args()
    resp = get_response(endpoint, args)
    return [user['id'] for user in resp['data']]


"""
Returns a sorted list of users that provide the most likes.
"""
def sort_likes(like_dict):     
    return sorted(like_dict.items(),
            key=operator.itemgetter(1),
            reverse=True)

def who_does_user_like(username):
    like_dict = {}
    target_user_id = get_user_id(username)
    num_follows = get_num_follows(target_user_id)
    user_ids_followed = get_user_ids_followed(target_user_id, num_follows)
    for user_id in user_ids_followed:
        for media_id in get_latest_media_ids(user_id, 10):
            if target_user_id in get_user_ids_that_like(media_id):
                try:
                    like_dict[user_id] += 1
                except:
                    like_dict[user_id] = 1
    

    top_ten = sort_likes(like_dict)
    if len(top_ten) > 10:
        top_ten = sort_likes(like_dict)
    for item in top_ten:
        user_id, like_count = item
        print get_username(user_id) + ': ' + str(like_count)


def who_likes_user(username):
    like_dict = {}
    target_user_id = get_user_id(username)
    for media_id in get_latest_media_ids(target_user_id, 50):
        for user_id in get_user_ids_that_like(media_id):
            try:
                like_dict[user_id] += 1
            except:
                like_dict[user_id] = 1
    top_ten = sort_likes(like_dict)
    if len(top_ten) > 10:
        top_ten = sort_likes(like_dict)[:10]
    for item in top_ten:
        user_id, like_count = item
        print get_username(user_id) + ': ' + str(like_count)
        
            
if __name__ == "__main__":
    usage = 'usage: python wholikes.py followers|followed user_name'
    if len(sys.argv) == 3:
        if sys.argv[1] in ['followers','followed']:
            if sys.argv[1] == 'followers':
                who_likes_user(sys.argv[2])
            else:
                who_does_user_like(sys.argv[2])
        else:
            print usage
    else:
        print usage


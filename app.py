import os
import cPickle as pickle
from pprint import pprint
import bottle
import beaker.middleware
from bottle import route, redirect, post, run, request, hook
from instagram import client, subscriptions
import networkx as nx
import wholikes as wl
bottle.debug(False)

session_opts = {
    'session.type': 'file',
    'session.data_dir': './session/',
    'session.auto': True,
}

app = beaker.middleware.SessionMiddleware(bottle.app(), session_opts)
access_token = None

CONFIG = {
    'client_id': 'f2ad558000f54a519d11c47c1ae8cc70',
    'client_secret': '8ef039d5b72646378e9a034ca9039a0c',
    'redirect_uri': 'http://localhost:8515/oauth_callback'
}

unauthenticated_api = client.InstagramAPI(**CONFIG)


def get_nav():
    nav_menu = (
        "<h1>Python Instagram</h1>"
        "<ul>"
        #"<li><a href='/i_like?'>What do I like?</a> Returns liked activity. </li>"
        #"<li><a href='/who_likes_user/rtpr'>Who likes user?</a> Returns a user's activity from followers. </li>"
        #"<li><a href='/who_does_user_like/rtpr?'>Who does the user like the of the people they follow?</a> </li>"
        "<li><a href='/collect_data'>Collect Data</a>"
        "</ul>")
    return nav_menu


@hook('before_request')
def setup_request():
    request.session = request.environ['beaker.session']


def process_tag_update(update):
    print(update)


reactor = subscriptions.SubscriptionsReactor()
reactor.register_callback(subscriptions.SubscriptionType.TAG,
                          process_tag_update)


@route('/')
def home():
    try:
        url = unauthenticated_api.get_authorize_url(
            scope=["likes", "comments"])
        return '<a href="%s">Connect with Instagram</a>' % url
    except Exception as e:
        print(e)

#@route('/i_like')
#def i_like():
#    print request.session['access_token']
#    users = wholikes.who_do_i_like(request.session['access_token'])
#    out = []
#    for user in users:
#        print user
#        out.append("<h1>%s</h1>" % (str(user)))
#    return ''.join(out)

#@route('/who_likes_user/<username>')
#def who_likes_user(username):
#    out = []
#    usernames = wholikes.who_likes_user(username,
#                                        request.session['access_token'])
#    for un in usernames:
#        out.append("<h1>%s</h1>" % (str(un)))
#    return out

#@route('/who_does_user_like/<username>')
#def who_does_user_like(username):
#    out = []
#    usernames = wholikes.who_does_user_like(username,
#                                            request.session['access_token'])
#    return usernames


@route('/collect_data')
def collect_data():
    G = nx.DiGraph()
    in_graph = []
    token = request.session['access_token']
    my_userid = wl.get_user_id('rtpr', token)
    G.add_node(my_userid)
    print 'adding self to graph'
    in_graph.append(my_userid)
    print 'collecting my followers'
    my_followers = wl.get_user_ids_followers(
        my_userid, int(wl.get_num_followers(my_userid, token)), token)
    print 'collected my followers'
    my_followed = [__id for __id in wl.get_user_ids_followed(
        my_userid, int(wl.get_num_follows(my_userid, token)), token)
                   if __id != '528817151' and __id != '20311520']
    print 'collecting who i follow'

    for follower in my_followers:
        print 'iterating followers: {}'.format(follower)
        if follower not in in_graph:
            in_graph.append(follower)
            G.add_node(follower)
        _followers = wl.get_user_ids_followers(
            follower, int(wl.get_num_followers(follower, token)), token)
        print 'found followers of {}'.format(follower)
        _followees = wl.get_user_ids_followed(
            follower, int(wl.get_num_follows(follower, token)), token)
        for _follower in _followers:
            if _follower not in in_graph:
                in_graph.append(_follower)
                G.add_node(_follower)
                G.add_edge(_follower, follower)
        for _followee in _followees:
            if _followee not in in_graph:
                in_graph.append(_followee)
                G.add_node(_followee)
                G.add_edge(follower, _followee)
        #[G.add_edge(f, follower) for f in _followers]
        #[G.add_edge(follower, f) for f in _followees]

    for followee in my_followed:
        print 'iterating followed: {}'.format(followee)
        if followee not in in_graph:
            print 'followee {}'.format(followee)
            in_graph.append(followee)
            G.add_node(followee)
        _followers = wl.get_user_ids_followers(
            followee, int(wl.get_num_followers(followee, token)), token)
        _followees = wl.get_user_ids_followed(
            followee, int(wl.get_num_follows(followee, token)), token)
        for _follower in _followers:
            if _follower not in in_graph:
                in_graph.append(_follower)
                G.add_node(_follower)
                G.add_edge(_follower, followee)
        for _followee in _followees:
            if _followee not in in_graph:
                in_graph.append(_followee)
                G.add_node(_followee)
                G.add_edge(followee, _followee)
        #[G.add_edge(f, followee) for f in _followers]
        #[G.add_edge(followee, f) for f in _followees]

    if not os.path.exists('newgraph.pickle'):
        os.system('touch newgraph.pickle')
    with open('newgraph.pickle', 'w') as f:
        pickle.dump(G, f)
        print 'Pickled the graph'


@route('/oauth_callback')
def on_callback():
    code = request.GET.get("code")
    if not code:
        return 'Missing code'
    try:
        access_token, user_info = unauthenticated_api.exchange_code_for_access_token(
            code)
        if not access_token:
            return 'Could not get access token'
        api = client.InstagramAPI(access_token=access_token,
                                  client_secret=CONFIG['client_secret'])
        request.session['access_token'] = access_token
    except Exception as e:
        print(e)
    return get_nav()


@route('/realtime_callback')
@post('/realtime_callback')
def on_realtime_callback():
    mode = request.GET.get("hub.mode")
    challenge = request.GET.get("hub.challenge")
    verify_token = request.GET.get("hub.verify_token")
    if challenge:
        return challenge
    else:
        x_hub_signature = request.header.get('X-Hub-Signature')
        raw_response = request.body.read()
        try:
            reactor.process(CONFIG['client_secret'], raw_response,
                            x_hub_signature)
        except subscriptions.SubscriptionVerifyError:
            print("Signature mismatch")


bottle.run(app=app, host='localhost', port=8515, reloader=False, debug=False)

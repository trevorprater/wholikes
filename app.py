import bottle
import beaker.middleware
from bottle import route, redirect, post, run, request, hook
from instagram import client, subscriptions

import wholikes

bottle.debug(True)

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
        "<li><a href='/i_like?'>What do I like?</a> Returns liked activity. </li>"
        "<li><a href='/who_likes_user/rtpr'>Who likes user?</a> Returns a user's activity from followers. </li>"
        "<li><a href='/who_does_user_like/rtpr?'>Who does the user like the of the people they follow?</a> </li>"
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


@route('/i_like')
def i_like():
    print request.session['access_token']
    users = wholikes.who_do_i_like(request.session['access_token'])
    out = []
    for user in users:
        print user
        out.append("<h1>%s</h1>" % (str(user)))
    return ''.join(out)


@route('/who_likes_user/<username>')
def who_likes_user(username):
    out = []
    usernames = wholikes.who_likes_user(username,
                                        request.session['access_token'])
    for un in usernames:
        out.append("<h1>%s</h1>" % (str(un)))
    return out


@route('/who_does_user_like/<username>')
def who_does_user_like(username):
    out = []
    usernames = wholikes.who_does_user_like(username,
                                            request.session['access_token'])
    return usernames


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


bottle.run(app=app, host='localhost', port=8515, reloader=True)

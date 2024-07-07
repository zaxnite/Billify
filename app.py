from flask import Flask, request, session, url_for, redirect, render_template, jsonify
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from credentials import CLIENT_ID, CLIENT_SECRET, SECRET_KEY
import time
from datetime import datetime
import random

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['SESSION_COOKIE_NAME'] = 'Spotify Cookie'
TOKEN_INFO = 'token_info'

# Spotify Authentication Scopes
SCOPE = 'user-top-read'

# Hard-coded redirect URI
REDIRECT_URI = 'http://localhost:5000/redirectPage'


def format_duration(duration_ms):
    minutes, seconds = divmod(duration_ms // 1000, 60)
    return f"{minutes}:{seconds:02d}"


# Register mmss filter with Jinja2 environment
@app.template_filter('mmss')
def _jinja2_filter_mmss(duration_ms):
    return format_duration(duration_ms)


def generate_random_card_number():
    # Generate the first 12 digits as asterisks
    first_part = '**** **** *** '

    # Generate the last 4 digits randomly
    last_part = ''.join(str(random.randint(0, 9)) for _ in range(4))

    # Concatenate and return the full card number
    return f"{first_part}{last_part}"


def generate_random_auth_code():
    return f"{random.randint(100000, 999999)}"


# Custom filter function to format dates
@app.template_filter('strftime')
def _jinja2_filter_datetime(date, fmt=None):
    if isinstance(date, str):
        try:
            date = datetime.strptime(date, '%Y-%m-%dT%H:%M:%S.%fZ')
        except ValueError:
            return date  # Return original date if parsing fails
    if isinstance(date, datetime):
        return date.strftime(fmt) if fmt else date
    return ''


def get_token():
    token_info = session.get(TOKEN_INFO, None)
    if not token_info:
        return None

    now = int(time.time())
    is_expired = token_info['expires_at'] - now < 60

    if is_expired:
        sp_oauth = SpotifyOAuth(
            client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope=SCOPE)
        token_info = sp_oauth.get_cached_token()
        if not token_info:
            return None  # Token could not be refreshed
        session[TOKEN_INFO] = token_info

    return token_info


def get_spotify_track_link(track_name, artist_name):
    token_info = get_token()
    if not token_info:
        return None

    sp = spotipy.Spotify(auth=token_info['access_token'])
    query = f"{track_name} {artist_name}"
    results = sp.search(q=query, type='track', limit=1)
    if results and results['tracks']['items']:
        track_id = results['tracks']['items'][0]['id']
        return f"https://open.spotify.com/track/{track_id}"
    return None


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/login')
def login():
    sp_oauth = SpotifyOAuth(
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope=SCOPE)
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)


@app.route('/redirectPage')
def redirectPage():
    sp_oauth = SpotifyOAuth(
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope=SCOPE)
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session[TOKEN_INFO] = token_info
    return redirect(url_for('trackify'))  # Update endpoint name here


@app.route('/trackify')
def trackify():
    token_info = get_token()
    if not token_info:
        return redirect(url_for('login'))

    sp = spotipy.Spotify(auth=token_info['access_token'])
    user_info = sp.current_user()
    user_name = user_info['display_name']
    duration = "long_term"
    id = "top_tracks"
    top_tracks_data = sp.current_user_top_tracks(
        limit=10, time_range=duration)
    top_tracks = top_tracks_data['items']

    current_time = datetime.now().strftime('%A, %B %d, %Y')

    random_card_number = generate_random_card_number()
    random_auth_code = generate_random_auth_code()

    return render_template('trackify.html', user_name=user_name, top_tracks=top_tracks, id=id, duration=duration,
                           currentTime=current_time, card_number=random_card_number, auth_code=random_auth_code,
                           get_spotify_track_link=get_spotify_track_link)


if __name__ == '__main__':
    app.run(debug=True)

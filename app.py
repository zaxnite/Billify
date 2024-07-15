from flask import Flask, request, session, url_for, redirect, render_template, jsonify
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
from datetime import datetime
import random
from collections import Counter
from credentials import CLIENT_ID, CLIENT_SECRET, SECRET_KEY
import os

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['SESSION_COOKIE_NAME'] = 'Spotify Cookie'
TOKEN_INFO = 'token_info'

# Spotify Authentication Scopes
SCOPE = 'user-top-read'

# # Hard-coded redirect URI
REDIRECT_URI = 'https://trackify-86c02d3ef29b.herokuapp.com/redirectPage'


def clear_cache():
    try:
        os.remove(".cache")
    except OSError as e:
        print(f"Error deleting .cache file: {e}")


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


def get_spotify_artist_link(artist_id):
    return f"https://open.spotify.com/artist/{artist_id}"


def get_duration_from_button():
    duration = request.form.get('duration', 'medium_term')
    return duration


def get_limit_from_button():
    limit = request.form.get('limit', 10)
    return int(limit)


def get_audio_features(sp, track_ids):
    features = sp.audio_features(tracks=track_ids)
    return features


def calculate_insights(sp, top_tracks):
    track_ids = [track['id'] for track in top_tracks]
    audio_features = get_audio_features(sp, track_ids)

    insights = {
        'popularity_score': 0,
        'average_track_age': 0,
        'tempo': 0,
        'happiness': 0,
        'danceability': 0,
        'energy': 0,
        'acousticness': 0,
        'instrumentalness': 0,
    }

    total_popularity = 0
    total_years = 0
    current_year = datetime.now().year

    for track, features in zip(top_tracks, audio_features):
        release_year = int(track['album']['release_date'].split('-')[0])
        track_age = current_year - release_year

        total_popularity += track['popularity']
        total_years += track_age
        insights['tempo'] += features['tempo']
        insights['happiness'] += features['valence'] * 100
        insights['danceability'] += features['danceability'] * 100
        insights['energy'] += features['energy'] * 100
        insights['acousticness'] += features['acousticness'] * 100
        insights['instrumentalness'] += features['instrumentalness'] * 100
    num_tracks = len(top_tracks)

    if num_tracks > 0:
        insights['popularity_score'] = total_popularity / num_tracks
        insights['average_track_age'] = total_years / num_tracks
        insights['tempo'] /= num_tracks
        insights['happiness'] /= num_tracks
        insights['danceability'] /= num_tracks
        insights['energy'] /= num_tracks
        insights['acousticness'] /= num_tracks
        insights['instrumentalness'] /= num_tracks

    return insights


@app.route('/<path:path>')
def catch_all(path):
    print(f"Caught a request to: {path}")
    return f"Caught a request to: {path}", 404


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/login')
def login():
    clear_cache()
    sp_oauth = SpotifyOAuth(
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope=SCOPE)
    auth_url = sp_oauth.get_authorize_url()
    print(f"Auth URL: {auth_url}")  # Debug print
    return redirect(auth_url)


@app.route('/redirectPage')
def redirectPage():
    print("Reached /redirectPage endpoint")  # Debug print
    print(request.args)  # Print incoming request arguments
    sp_oauth = SpotifyOAuth(
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope=SCOPE)
    # Clear session and cache
    session.clear()
    code = request.args.get('code')
    print(f"Redirected to /redirectPage with code: {code}")  # Debug print
    print(f"Full request URL: {request.url}")  # Debug print
    if code is None:
        return "Error: Missing code parameter"
    try:
        token_info = sp_oauth.get_access_token(code)
        print(f"Token info: {token_info}")  # Debug print
        session[TOKEN_INFO] = token_info
    except Exception as e:
        print(f"Error obtaining token: {e}")  # Debug print
        return f"Error obtaining token: {e}"
    return redirect(url_for('trackify'))


@app.route('/trackify', methods=['GET', 'POST'])
def trackify():
    token_info = get_token()
    if not token_info:
        return redirect(url_for('login'))

    sp = spotipy.Spotify(auth=token_info['access_token'])
    user_info = sp.current_user()
    user_name = user_info['display_name']

    # Get the duration and limit from the form submission
    duration = get_duration_from_button()
    limit = get_limit_from_button()
    metric = request.form.get('metric', 'tracks')

    duration_text_map = {
        'short_term': 'Last Month',
        'medium_term': 'Last 6 months',
        'long_term': 'Last Year'
    }

    duration_text = duration_text_map.get(duration, 'Last Month')

    if metric == 'tracks':
        id = "top_tracks"
        top_data = sp.current_user_top_tracks(limit=limit, time_range=duration)
        top_items = top_data['items']
        get_spotify_link = get_spotify_track_link  # Assign the function reference
    elif metric == 'genres':
        id = "top_genres"
        top_artists_data = sp.current_user_top_artists(
            limit=50, time_range=duration)  # Fetch top 50 artists
        top_artists = top_artists_data['items']

        genre_counter = Counter()
        for artist in top_artists:
            genre_counter.update(artist['genres'])

        # Limit the genres based on the number of top artists
        limited_genres = genre_counter.most_common(limit)
        total_artists = len(top_artists)
        top_items = [{'name': genre, 'count': count, 'percentage': (count / total_artists) * 100}
                     for genre, count in limited_genres]

        # No direct link for genres
        def get_spotify_link(name, _): return 'https://open.spotify.com/'

    elif metric == 'stats':
        id = "top_stats"
        top_data = sp.current_user_top_tracks(limit=limit, time_range=duration)
        top = top_data['items']
        insights = calculate_insights(sp, top)

        # Prepare insights for rendering
        top_items = [
            {'name': 'Popularity Score',
                'value': f"{insights['popularity_score']:.2f}/100"},
            {'name': 'Average Track Age',
                'value': f"{insights['average_track_age']:.1f} YRS"},
            {'name': 'Tempo', 'value': f"{insights['tempo']:.1f} BPM"},
            {'name': 'Happiness', 'value': f"{insights['happiness']:.2f}"},
            {'name': 'Danceability',
                'value': f"{insights['danceability']:.2f}"},
            {'name': 'Energy', 'value': f"{insights['energy']:.2f}"},
            {'name': 'Acousticness',
                'value': f"{insights['acousticness']:.2f}"},
            {'name': 'Instrumentalness',
                'value': f"{insights['instrumentalness']:.2f}"}
        ]

        # No direct link for stats
        def get_spotify_link(name, _): return 'https://open.spotify.com/'

    else:
        id = "top_artists"
        top_data = sp.current_user_top_artists(
            limit=limit, time_range=duration)
        top_items = top_data['items']
        get_spotify_link = get_spotify_artist_link  # Assign the function reference

    current_time = datetime.now().strftime('%A, %B %d, %Y')

    random_card_number = generate_random_card_number()
    random_auth_code = generate_random_auth_code()

    return render_template('trackify.html', user_name=user_name, top_items=top_items, id=id, duration=duration,
                           duration_text=duration_text, currentTime=current_time, card_number=random_card_number,
                           auth_code=random_auth_code, get_spotify_link=get_spotify_link, metric=metric, limit=limit)


if __name__ == '__main__':
    app.run(debug=False)

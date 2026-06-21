from flask import Flask, request, session, url_for, redirect, render_template, jsonify
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
from datetime import datetime
import random
from collections import Counter
from dotenv import load_dotenv
import os
import requests
from functools import wraps


# Load environment variables from .env (local) and system
load_dotenv()

# Secrets: prefer environment, fallback to credentials.py for local dev
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SECRET_KEY = os.getenv("SECRET_KEY")

if not (CLIENT_ID and CLIENT_SECRET and SECRET_KEY):
    try:
        from credentials import CLIENT_ID as _CID, CLIENT_SECRET as _CS, SECRET_KEY as _SK
        CLIENT_ID = CLIENT_ID or _CID
        CLIENT_SECRET = CLIENT_SECRET or _CS
        SECRET_KEY = SECRET_KEY or _SK
    except Exception:
        raise RuntimeError(
            "Missing CLIENT_ID/CLIENT_SECRET/SECRET_KEY. Set env vars or provide credentials.py"
        )

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['SESSION_COOKIE_NAME'] = 'Spotify Cookie'
app.config.update({
    'SESSION_COOKIE_SECURE': True,
    'SESSION_COOKIE_HTTPONLY': True,
    'SESSION_COOKIE_SAMESITE': 'Lax',
    'PREFERRED_URL_SCHEME': 'https',
})

@app.after_request
def after_request(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "img-src 'self' data: blob: *.flagcounter.com; "
        "connect-src 'self'; "
        "style-src 'self' 'unsafe-inline' cdnjs.cloudflare.com fonts.googleapis.com; "
        "font-src 'self' cdnjs.cloudflare.com fonts.gstatic.com data:; "
        "frame-src 'self'"
    )
    return response

TOKEN_INFO = 'token_info'
SCOPE = 'user-top-read'
REDIRECT_URI = os.getenv('REDIRECT_URI', 'https://zaxnite-billify.vercel.app/redirectPage')


def retry_on_failure(max_retries=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        print(f"Final attempt failed for {func.__name__}: {e}")
                        raise e
                    else:
                        wait_time = delay * (2 ** attempt)
                        print(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
            return None
        return wrapper
    return decorator


def create_spotify_client(token):
    return spotipy.Spotify(
        auth=token,
        requests_timeout=10,
        retries=3,
        status_retries=3
    )


def format_duration(duration_ms):
    minutes, seconds = divmod(duration_ms // 1000, 60)
    return f"{minutes}:{seconds:02d}"


@app.template_filter('mmss')
def _jinja2_filter_mmss(duration_ms):
    return format_duration(duration_ms)


def generate_random_card_number():
    first_part = '**** **** *** '
    last_part = ''.join(str(random.randint(0, 9)) for _ in range(4))
    return f"{first_part}{last_part}"


def generate_random_auth_code():
    return f"{random.randint(100000, 999999)}"


@app.template_filter('strftime')
def _jinja2_filter_datetime(date, fmt=None):
    if isinstance(date, str):
        try:
            date = datetime.strptime(date, '%Y-%m-%dT%H:%M:%S.%fZ')
        except ValueError:
            return date
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
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            scope=SCOPE,
            cache_handler=spotipy.cache_handler.MemoryCacheHandler()
        )
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        if not token_info:
            return None
        session[TOKEN_INFO] = token_info

    return token_info


def get_spotify_track_link(track_name, artist_name, track_object=None):
    if track_object and 'external_urls' in track_object and 'spotify' in track_object['external_urls']:
        return track_object['external_urls']['spotify']

    token_info = get_token()
    if not token_info:
        return None

    try:
        sp = create_spotify_client(token_info['access_token'])
        query = f'track:"{track_name}" artist:"{artist_name}"'

        @retry_on_failure(max_retries=3, delay=1)
        def search_track():
            return sp.search(q=query, type='track', limit=1)

        results = search_track()
        if results and results['tracks']['items']:
            return results['tracks']['items'][0]['external_urls']['spotify']
    except Exception as e:
        print(f"Error searching for track {track_name} by {artist_name}: {e}")

    return None


def get_spotify_artist_link(artist_id):
    return f"https://open.spotify.com/artist/{artist_id}"


def get_duration_from_button():
    return request.form.get('duration', 'medium_term')


def get_limit_from_button():
    return int(request.form.get('limit', 10))


@retry_on_failure(max_retries=3, delay=1)
def get_audio_features(sp, track_ids):
    return sp.audio_features(tracks=track_ids)


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


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/privacy')
def privacy():
    return render_template('privacy.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/robots.txt')
def robots_txt():
    response = app.response_class(
        response="""User-agent: *
Allow: /
Allow: /about
Allow: /privacy
Allow: /contact
Disallow: /billify
Disallow: /login
Disallow: /redirectPage

Sitemap: {}/sitemap.xml""".format(request.url_root.rstrip('/')),
        status=200,
        mimetype='text/plain'
    )
    return response


@app.route('/sitemap.xml')
def sitemap_xml():
    base_url = request.url_root.rstrip('/')
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>{base_url}/</loc>
        <lastmod>{datetime.now().strftime('%Y-%m-%d')}</lastmod>
        <changefreq>weekly</changefreq>
        <priority>1.0</priority>
    </url>
    <url>
        <loc>{base_url}/about</loc>
        <lastmod>{datetime.now().strftime('%Y-%m-%d')}</lastmod>
        <changefreq>monthly</changefreq>
        <priority>0.8</priority>
    </url>
    <url>
        <loc>{base_url}/privacy</loc>
        <lastmod>{datetime.now().strftime('%Y-%m-%d')}</lastmod>
        <changefreq>yearly</changefreq>
        <priority>0.5</priority>
    </url>
    <url>
        <loc>{base_url}/contact</loc>
        <lastmod>{datetime.now().strftime('%Y-%m-%d')}</lastmod>
        <changefreq>monthly</changefreq>
        <priority>0.7</priority>
    </url>
</urlset>"""
    return app.response_class(response=sitemap, status=200, mimetype='application/xml')


@app.route('/debug-flag-counter')
def debug_flag_counter():
    try:
        flag_url = "https://s01.flagcounter.com/count2/HTLF/bg_FFFFFF/txt_000000/border_CCCCCC/columns_2/maxflags_10/viewers_0/labels_1/pageviews_0/flags_0/percent_0/"
        response = requests.get(flag_url, timeout=10)
        return jsonify({
            'status': 'success',
            'flag_counter_accessible': response.status_code == 200,
            'response_code': response.status_code,
            'content_type': response.headers.get('content-type', 'unknown'),
            'content_length': len(response.content),
            'user_agent': request.headers.get('User-Agent', 'unknown'),
            'ip_address': request.remote_addr,
            'referrer': request.referrer
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'user_agent': request.headers.get('User-Agent', 'unknown'),
            'ip_address': request.remote_addr
        })


@app.route('/test-flag-counter')
def test_flag_counter():
    return render_template('test-flag-counter.html')


@app.route('/login')
def login():
    sp_oauth = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_handler=spotipy.cache_handler.MemoryCacheHandler()
    )
    auth_url = sp_oauth.get_authorize_url()
    print(f"Auth URL: {auth_url}")
    return redirect(auth_url)


@app.route('/redirectPage')
def redirectPage():
    print("Reached /redirectPage endpoint")
    print(request.args)
    sp_oauth = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_handler=spotipy.cache_handler.MemoryCacheHandler()
    )
    session.clear()
    code = request.args.get('code')
    print(f"Redirected to /redirectPage with code: {code}")
    print(f"Full request URL: {request.url}")
    if code is None:
        return "Error: Missing code parameter"
    try:
        token_info = sp_oauth.get_access_token(code)
        print(f"Token info: {token_info}")
        session[TOKEN_INFO] = token_info
    except Exception as e:
        print(f"Error obtaining token: {e}")
        return f"Error obtaining token: {e}"
    return redirect(url_for('billify'))


@app.route('/billify', methods=['GET', 'POST'])
def billify():
    token_info = get_token()
    if not token_info:
        return redirect(url_for('login'))

    try:
        sp = create_spotify_client(token_info['access_token'])

        @retry_on_failure(max_retries=3, delay=1)
        def get_user_info():
            return sp.current_user()

        user_info = get_user_info()
        user_name = user_info['display_name']

        duration = get_duration_from_button()
        limit = get_limit_from_button()
        metric = request.form.get('metric', 'tracks')

        duration_text_map = {
            'short_term': 'Last Month',
            'medium_term': 'Last 6 months',
            'long_term': 'Last Year'
        }

        duration_text = duration_text_map.get(duration, 'Last Month')
        get_spotify_link = None

        if metric == 'tracks':
            id = "top_tracks"

            @retry_on_failure(max_retries=3, delay=1)
            def get_top_tracks():
                return sp.current_user_top_tracks(limit=limit, time_range=duration)

            top_data = get_top_tracks()
            top_items = top_data['items']
            get_spotify_link = get_spotify_track_link

        elif metric == 'genres':
            id = "top_genres"

            @retry_on_failure(max_retries=3, delay=1)
            def get_top_artists_for_genres():
                return sp.current_user_top_artists(limit=50, time_range=duration)

            top_artists_data = get_top_artists_for_genres()
            top_artists = top_artists_data['items']

            genre_counter = Counter()
            for artist in top_artists:
                genre_counter.update(artist['genres'])

            limited_genres = genre_counter.most_common(limit)
            total_artists = len(top_artists)
            top_items = [{'name': genre, 'count': count, 'percentage': (count / total_artists) * 100}
                         for genre, count in limited_genres]

            def get_spotify_link_for_genres(name, _):
                return 'https://open.spotify.com/'
            get_spotify_link = get_spotify_link_for_genres

        elif metric == 'stats':
            id = "top_stats"

            @retry_on_failure(max_retries=3, delay=1)
            def get_top_tracks_for_stats():
                return sp.current_user_top_tracks(limit=limit, time_range=duration)

            top_data = get_top_tracks_for_stats()
            top = top_data['items']
            insights = calculate_insights(sp, top)

            top_items = [
                {'name': 'Popularity Score', 'value': f"{insights['popularity_score']:.2f}/100"},
                {'name': 'Average Track Age', 'value': f"{insights['average_track_age']:.1f} YRS"},
                {'name': 'Tempo', 'value': f"{insights['tempo']:.1f} BPM"},
                {'name': 'Happiness', 'value': f"{insights['happiness']:.2f}"},
                {'name': 'Danceability', 'value': f"{insights['danceability']:.2f}"},
                {'name': 'Energy', 'value': f"{insights['energy']:.2f}"},
                {'name': 'Acousticness', 'value': f"{insights['acousticness']:.2f}"},
                {'name': 'Instrumentalness', 'value': f"{insights['instrumentalness']:.2f}"}
            ]

            def get_spotify_link_for_stats(name, _):
                return 'https://open.spotify.com/'
            get_spotify_link = get_spotify_link_for_stats

        else:
            id = "top_artists"

            @retry_on_failure(max_retries=3, delay=1)
            def get_top_artists():
                return sp.current_user_top_artists(limit=limit, time_range=duration)

            top_data = get_top_artists()
            top_items = top_data['items']
            get_spotify_link = get_spotify_artist_link

        current_time = datetime.now().strftime('%A, %B %d, %Y')
        random_card_number = generate_random_card_number()
        random_auth_code = generate_random_auth_code()

        return render_template('billify.html', user_name=user_name, top_items=top_items, id=id, duration=duration,
                               duration_text=duration_text, currentTime=current_time, card_number=random_card_number,
                               auth_code=random_auth_code, metric=metric, limit=limit, get_spotify_link=get_spotify_link)

    except Exception as e:
        print(f"Error in billify route: {e}")
        return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
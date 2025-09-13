from flask import Flask, request, session, url_for, redirect, render_template, jsonify
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
from datetime import datetime
import random
from collections import Counter
from dotenv import load_dotenv
import os
import re
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
# Secure cookie and URL scheme settings (effective in production/HTTPS)
app.config.update({
    'SESSION_COOKIE_SECURE': True,
    'SESSION_COOKIE_HTTPONLY': True,
    'SESSION_COOKIE_SAMESITE': 'Lax',
    'PREFERRED_URL_SCHEME': 'https',
})

# Add security headers for better flag counter compatibility
@app.after_request
def after_request(response):
    # Allow external images for flag counter
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    # Remove any restrictive CSP that might block flag counter or Google Analytics
    if 'Content-Security-Policy' in response.headers:
        csp = response.headers['Content-Security-Policy']
        if 'img-src' in csp and 'flagcounter.com' not in csp:
            csp = csp.replace('img-src', 'img-src *.flagcounter.com')
        if 'script-src' in csp and 'googletagmanager.com' not in csp:
            csp = csp.replace('script-src', 'script-src *.googletagmanager.com *.google-analytics.com')
        response.headers['Content-Security-Policy'] = csp
    return response

TOKEN_INFO = 'token_info'

# Spotify Authentication Scopes
SCOPE = 'user-top-read'

# Redirect URI from environment with local fallback
REDIRECT_URI = os.getenv('REDIRECT_URI', 'https://billify-388bd942b87f.herokuapp.com/redirectPage')


def retry_on_failure(max_retries=3, delay=1):
    """Decorator to retry API calls with exponential backoff"""
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
    """Create Spotify client with increased timeout"""
    return spotipy.Spotify(
        auth=token,
        requests_timeout=10,  # 10 second timeout
        retries=3,
        status_retries=3
    )


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


def get_spotify_track_link(track_name, artist_name, track_object=None):
    """
    Get Spotify track link. If track_object is provided (from top tracks API),
    use the direct link. Otherwise, search for it.
    """
    # If we have the track object from the API, use the direct link
    if track_object and 'external_urls' in track_object and 'spotify' in track_object['external_urls']:
        return track_object['external_urls']['spotify']
    
    # Fallback to search (for cases where you don't have the track object)
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
    duration = request.form.get('duration', 'medium_term')
    return duration


def get_limit_from_button():
    limit = request.form.get('limit', 10)
    return int(limit)


@retry_on_failure(max_retries=3, delay=1)
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


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/privacy')
def privacy():
    return render_template('privacy.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/debug-flag-counter')
def debug_flag_counter():
    """Debug endpoint to test flag counter visibility"""
    try:
        # Test if flag counter URL is accessible
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
    """Test page for flag counter visibility"""
    return render_template('test-flag-counter.html')


@app.route('/test-analytics')
def test_analytics():
    """Test page to verify Google Analytics is working"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Google Analytics Test - Billify</title>
        <!-- Google tag (gtag.js) -->
        <script async src="https://www.googletagmanager.com/gtag/js?id=G-SLC6BEGVZB"></script>
        <script>
          window.dataLayer = window.dataLayer || [];
          function gtag(){dataLayer.push(arguments);}
          gtag('js', new Date());

          gtag('config', 'G-SLC6BEGVZB');
        </script>
    </head>
    <body>
        <h1>Google Analytics Test Page</h1>
        <p>This page tests Google Analytics implementation.</p>
        <button onclick="testGAEvent()">Test Custom Event</button>
        <div id="ga-status"></div>
        
        <script>
            // Test if Google Analytics is loaded
            function checkGoogleAnalytics() {
                const status = document.getElementById('ga-status');
                if (typeof gtag === 'function') {
                    status.innerHTML = '<p style="color: green;">✅ Google Analytics is loaded successfully!</p>';
                    // Send a test pageview
                    gtag('event', 'page_view', {
                        page_title: 'Analytics Test Page',
                        page_location: window.location.href
                    });
                } else {
                    status.innerHTML = '<p style="color: red;">❌ Google Analytics failed to load.</p>';
                }
            }
            
            function testGAEvent() {
                if (typeof gtag === 'function') {
                    gtag('event', 'test_button_click', {
                        event_category: 'engagement',
                        event_label: 'analytics_test'
                    });
                    alert('Test event sent to Google Analytics!');
                } else {
                    alert('Google Analytics not loaded!');
                }
            }
            
            // Check GA status when page loads
            setTimeout(checkGoogleAnalytics, 2000);
        </script>
        
        <p><a href="{{ url_for('home') }}">← Back to Home</a></p>
    </body>
    </html>
    '''


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
        get_spotify_link = None  # Initialize the variable

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
        return redirect(url_for('login'))  # Redirect to login if there's a major error

if __name__ == '__main__':
    app.run(debug=True)

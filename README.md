# Billify

**Your Spotify listening history, served as a receipt.**

Billify connects to your Spotify account and displays your top tracks, artists, genres, and detailed audio stats in a stylized receipt format. Think Spotify Wrapped, but available any time of year and with deeper analytics.

🔗 **Live at [zaxnite-billify.vercel.app](https://zaxnite-billify.vercel.app)**

---

## Features

- **Top Tracks** — See your most played songs ranked by listening frequency
- **Top Artists** — Discover which artists dominate your listening habits
- **Top Genres** — See the genre breakdown of your top artists
- **Listening Stats** — Audio feature analysis including:
  - Danceability, Energy, Happiness (Valence)
  - Tempo (BPM), Acousticness, Instrumentalness
  - Popularity Score and Average Track Age
- **Time Periods** — Switch between Last Month, Last 6 Months, and Last Year
- **Top 10 / 20 / 30** — Control how many items appear on your receipt
- **Save as Image** — Download your receipt as a PNG to share
- **Dark Mode** — Toggle between light and dark receipt themes

---

## Tech Stack

- **Backend** — Python, Flask
- **Frontend** — HTML, CSS, JavaScript, Jinja2
- **APIs** — Spotify Web API (via Spotipy)
- **Deployment** — Vercel

---

## Running Locally

### 1. Clone the repo

```bash
git clone https://github.com/zaxnite/Billify.git
cd Billify
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up Spotify credentials

Go to [developer.spotify.com](https://developer.spotify.com/dashboard) and create an app. Set the redirect URI to `http://127.0.0.1:5000/redirectPage`.

Create a `credentials.py` file in the root:

```python
CLIENT_ID = "your_spotify_client_id"
CLIENT_SECRET = "your_spotify_client_secret"
SECRET_KEY = "any_random_string"
```

Or set environment variables:

```bash
CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret
SECRET_KEY=your_secret_key
```

### 4. Run the app

```bash
flask run
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## Deploying to Vercel

1. Fork or clone this repo and push to GitHub
2. Go to [vercel.com](https://vercel.com) and import the repo
3. Add environment variables in the Vercel dashboard:
   - `CLIENT_ID`
   - `CLIENT_SECRET`
   - `SECRET_KEY`
   - `REDIRECT_URI` — set to `https://your-app.vercel.app/redirectPage`
4. Add the Vercel redirect URI to your Spotify app's allowed redirect URIs
5. Deploy

---

## Privacy

Billify only requests read access to your Spotify listening history (`user-top-read` scope). No data is stored on any server. Your Spotify token lives only in your browser session and expires after one hour.

---

## Author

Built by [Aathif Khan](https://github.com/zaxnite)
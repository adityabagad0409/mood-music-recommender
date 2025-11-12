# Mood-to-Music Recommender

A lightweight Flask app that recommends Spotify tracks based on **mood**, **language**, and **activity** — with playlist fallback so moods like *chill* and *romantic* actually return results. Includes an HTML5 preview audio fallback when Spotify embeds are blocked.

Live demo: (Local) run `python app.py` and open `http://127.0.0.1:5000`.

---

## Features
- Mood-based recommendations (happy, sad, energetic, chill, romantic)
- Language filter (English, Hindi, Marathi, Gujarati, Tamil, Telugu, Kannada, Malayalam, Spanish)
- Activity presets (driving, studying, gym, cooking, etc.) influence tempo/energy
- Multi-layer fallback:
  1. Spotify Recommendations API
  2. Genre-only recommendations
  3. Keyword track search
  4. Playlist search fallback (human-curated)
- 30s track preview fallback (HTML5 `<audio>`) when embed playback fails
- Simple, responsive UI (Flask + Jinja2 + CSS)

---

## Tech stack
- Python 3.10+
- Flask
- Spotipy (Spotify Web API wrapper)
- HTML/CSS (Jinja2 templates)

---

## Prerequisites
1. Spotify Developer account and an app (to get `CLIENT_ID`, `CLIENT_SECRET`, `REDIRECT_URI`).
2. Python 3.10+ and `pip`.
3. (Optional) Spotify Premium for full in-app playback (not required for previews).

Put these environment variables in a `.env` file at project root:

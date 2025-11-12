from flask import Flask, render_template, request, redirect, session, url_for
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from dotenv import load_dotenv

# Load credentials from .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "moodmusicsecret")
app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'

# Activity presets -> seeds + audio-feature targets
ACTIVITY_PRESETS = {
    'driving': {'seed_genres': ['rock', 'pop'], 'target_tempo': 115, 'target_energy': 0.8},
    'roadtrip': {'seed_genres': ['pop', 'classic-rock'], 'target_tempo': 110, 'target_energy': 0.75},
    'cooking': {'seed_genres': ['indie-pop', 'acoustic'], 'target_tempo': 95, 'target_energy': 0.55},
    'studying': {'seed_genres': ['chill', 'ambient'], 'target_tempo': 65, 'target_energy': 0.2, 'target_acousticness': 0.7},
    'coding': {'seed_genres': ['chill', 'ambient'], 'target_tempo': 80, 'target_energy': 0.3},
    'running': {'seed_genres': ['dance', 'electronic'], 'target_tempo': 160, 'target_energy': 0.9},
    'gym': {'seed_genres': ['hip-hop', 'electronic'], 'target_tempo': 140, 'target_energy': 0.95},
    'chilling': {'seed_genres': ['chill', 'lofi'], 'target_tempo': 70, 'target_energy': 0.25},
    'party': {'seed_genres': ['dance', 'pop'], 'target_tempo': 125, 'target_energy': 0.95},
    'sleep': {'seed_genres': ['ambient', 'chill'], 'target_tempo': 50, 'target_energy': 0.05, 'target_acousticness': 0.9},
    'bathing': {'seed_genres': ['ambient', 'spa'], 'target_tempo': 60, 'target_acousticness': 0.8},
    'gaming': {'seed_genres': ['electronic', 'synthwave'], 'target_tempo': 120, 'target_energy': 0.7},
    'date': {'seed_genres': ['romance', 'rnb'], 'target_tempo': 80, 'target_energy': 0.35}
}

# Spotify OAuth setup
sp_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="user-read-private"
)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)


@app.route('/callback')
def callback():
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session["token_info"] = token_info
    return redirect(url_for('recommend'))


@app.route('/recommend', methods=['GET', 'POST'])
def recommend():
    token_info = session.get("token_info", None)
    if not token_info:
        return redirect(url_for('login'))

    # refresh token if expired
    try:
        if sp_oauth.is_token_expired(token_info):
            token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
            session['token_info'] = token_info
    except Exception as e:
        print("Token refresh failed:", e)
        return redirect(url_for('login'))

    sp = spotipy.Spotify(auth=token_info['access_token'])

    # read inputs
    mood = request.form.get('mood', '').strip().lower()
    language = request.form.get('language', '').strip().lower()
    activity = request.form.get('activity', '').strip().lower()

    if not mood:
        return redirect(url_for('index'))

    # mood -> genres (broad)
    mood_to_genre = {
        'happy':    ['pop', 'indie-pop', 'dance'],
        'sad':      ['acoustic', 'singer-songwriter', 'indie'],
        'energetic':['rock', 'dance', 'electronic'],
        'chill':    ['chill', 'lofi', 'ambient', 'downtempo', 'indie'],
        'romantic': ['romance', 'rnb', 'soul', 'acoustic', 'adult-contemporary']
    }

    seed_genres = mood_to_genre.get(mood, ['pop']).copy()
    feature_targets = {}
    if activity and activity in ACTIVITY_PRESETS:
        preset = ACTIVITY_PRESETS[activity]
        if 'seed_genres' in preset:
            for g in preset['seed_genres']:
                if g not in seed_genres:
                    seed_genres.append(g)
        for k, v in preset.items():
            if k.startswith('target_'):
                feature_targets[k] = v

    # prepare rec kwargs (no artist seeds anymore)
    rec_kwargs = {'limit': 12}
    rec_kwargs['seed_genres'] = seed_genres[:5]  # spotify allows up to 5 seeds
    for k, v in feature_targets.items():
        rec_kwargs[k] = v

    # DEBUG
    print("\n--- RECOMMEND DEBUG ---")
    print("mood:", mood, "language:", language, "activity:", activity)
    print("seed_genres (final):", rec_kwargs.get('seed_genres'))
    print("feature_targets:", feature_targets)
    print("rec_kwargs:", rec_kwargs)
    print("-----------------------\n")

    items = []
    # 1) Try recommendations
    try:
        recs = sp.recommendations(**rec_kwargs)
        items = recs.get('tracks', [])
        print("recommendations returned:", len(items))
    except Exception as e:
        print("recommendations error:", e)
        items = []

    # 2) genre-only recommendations retry (redundant but safe)
    if not items and rec_kwargs.get('seed_genres'):
        try:
            recs = sp.recommendations(seed_genres=rec_kwargs['seed_genres'][:5], limit=12)
            items = recs.get('tracks', [])
            print("genre-only recommendations returned:", len(items))
        except Exception as e:
            print("genre-only recs failed:", e)
            items = []

    # 3) keyword search fallback
    if not items:
        synonyms = {
            'chill': ['chill', 'lofi', 'relax', 'ambient'],
            'romantic': ['romantic', 'love', 'slow', 'rnb', 'soul']
        }
        mood_terms = synonyms.get(mood, [mood])
        qparts = []
        qparts.extend(mood_terms[:3])
        if language:
            qparts.append(language)
        q = " ".join(qparts)
        try:
            results = sp.search(q=q, type='track', limit=12)
            items = results.get('tracks', {}).get('items', [])
            print("keyword search returned:", len(items))
        except Exception as e:
            print("keyword search failed:", e)
            items = []

    # 4) playlist fallback
    if not items:
        playlist_query_parts = [mood]
        if language:
            playlist_query_parts.append(language)
        playlist_q = " ".join(playlist_query_parts)
        try:
            print("Searching playlists for:", playlist_q)
            pls = sp.search(q=playlist_q, type='playlist', limit=6)
            playlists = pls.get('playlists', {}).get('items', [])
            collected = []
            for p in playlists:
                pid = p.get('id')
                if not pid:
                    continue
                try:
                    ptracks = sp.playlist_items(pid, fields="items(track(id,name,artists,external_urls,album(name)))", limit=20)
                    for it in ptracks.get('items', []):
                        tr = it.get('track')
                        if tr:
                            collected.append(tr)
                except Exception:
                    pass
                if len(collected) >= 12:
                    break
            items = collected[:12]
            print("playlist fallback gathered:", len(items))
        except Exception as e:
            print("playlist search failed:", e)
            items = []

    # 5) per-genre search loop
    if not items:
        for g in rec_kwargs.get('seed_genres', []):
            try:
                print("Trying genre search for:", g)
                results = sp.search(q=f'genre:{g}', type='track', limit=12)
                items = results.get('tracks', {}).get('items', [])
                if items:
                    print("genre search found:", len(items), "for", g)
                    break
            except Exception as e:
                print("genre search error:", e)

    # -------------------------
    # Post-retrieval filtering: only language (best-effort)
    # -------------------------
    LANGUAGE_GENRE_KEYWORDS = {
        'english': ['english'],
        'hindi': ['hindi', 'bollywood'],
        'marathi': ['marathi'],
        'gujarati': ['gujarati'],
        'tamil': ['tamil', 'kollywood'],
        'telugu': ['telugu', 'tollywood'],
        'kannada': ['kannada'],
        'malayalam': ['malayalam'],
        'spanish': ['spanish']
    }

    lang_req = language or ''

    # simple cache for artist metadata
    artist_genres_cache = {}

    def artist_genres_for_artist_obj(ar):
        aid = ar.get('id')
        if not aid:
            return []
        if aid in artist_genres_cache:
            return artist_genres_cache[aid]
        try:
            aobj = sp.artist(aid)
            genres = aobj.get('genres', []) or []
        except Exception:
            genres = []
        artist_genres_cache[aid] = [g.lower() for g in genres]
        return artist_genres_cache[aid]

    def matches_language(track):
        if not lang_req:
            return True
        for ar in track.get('artists', []):
            genres = artist_genres_for_artist_obj(ar)
            for keyword in LANGUAGE_GENRE_KEYWORDS.get(lang_req, []):
                if any(keyword in g for g in genres):
                    return True
        tname = (track.get('name') or '').lower()
        aname = (track.get('album', {}).get('name') or '').lower()
        for keyword in LANGUAGE_GENRE_KEYWORDS.get(lang_req, []):
            if keyword in tname or keyword in aname:
                return True
        return False

    filtered = []
    for t in items:
        if not matches_language(t):
            continue
        filtered.append(t)

    if not filtered:
        filtered = items.copy()

    items = filtered

 # format songs
    songs = []
    for t in items:
     songs.append({
        'name': t.get('name'),
        'artist': ', '.join([ar.get('name') for ar in t.get('artists', [])]),
        'url': (t.get('external_urls') or {}).get('spotify'),
        'id': t.get('id'),
        'preview_url': t.get('preview_url')  # <-- add this
    })


    # summary debug
    print("\n--- SUMMARY ---")
    print(f"Mood:{mood} language:{language} activity:{activity}")
    print("seed_genres_final:", rec_kwargs.get('seed_genres'))
    print("final returned:", len(songs))
    print("---------------\n")

    return render_template('index.html', songs=songs, mood=mood)


if __name__ == '__main__':
    app.run(debug=True)

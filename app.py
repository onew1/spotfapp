from flask import Flask, render_template, request, redirect, url_for, session
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import re

app = Flask(__name__, template_folder='templates')
app.secret_key = os.urandom(24)

# Configurações da API do Spotify
CLIENT_ID = '0d147e6078cc4776b6db8ec0b48e3403'
CLIENT_SECRET = '813b0866bb26462d99113d98da98421c'
SCOPE = 'playlist-modify-private user-read-private'
REDIRECT_URI = 'http://localhost:5000/callback'

sp_oauth = SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope=SCOPE)

@app.route('/')
def index():
    user_name = None
    if 'token_info' in session:
        token_info = session['token_info']
        sp = spotipy.Spotify(auth=token_info['access_token'])
        user_name = sp.current_user()['display_name']
    return render_template('index.html', user_name=user_name)

@app.route('/login')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if code:
        token_info = sp_oauth.get_access_token(code)
        session['token_info'] = token_info
        return redirect(url_for('index'))
    else:
        return "Erro: Código de autorização não fornecido."

@app.route('/create_playlist', methods=['POST'])
def create_playlist():
    token_info = session.get('token_info')
    if not token_info:
        return redirect(url_for('login'))

    track1 = extract_track_uri(request.form['track1'])
    track2 = extract_track_uri(request.form['track2']) if 'add-track2' in request.form else None

    sp = spotipy.Spotify(auth=token_info['access_token'])
    user_id = sp.current_user()['id']

    track1_info = sp.track(track1)
    track2_info = sp.track(track2) if track2 else None

    track1_features = sp.audio_features(track1)[0]
    track2_features = sp.audio_features(track2)[0] if track2 else None

    bpm1 = track1_features['tempo']
    bpm2 = track2_features['tempo'] if track2_features else bpm1
    average_bpm = (bpm1 + bpm2) / 2 if track2_features else bpm1

    playlist_name = f"BPM {int(average_bpm)} {track1_info['name']}" + (f" + {track2_info['name']}" if track2_info else "")

    playlist = sp.user_playlist_create(user_id, playlist_name, public=False)

    tracks = [track1]
    if track2:
        tracks.append(track2)
    for track_uri in tracks:
        sp.playlist_add_items(playlist['id'], [track_uri])

    suggested_tracks = generate_suggested_tracks(sp, track1, track2, 28)
    for suggested_track_uri in suggested_tracks:
        sp.playlist_add_items(playlist['id'], [suggested_track_uri])

    return 'Playlist criada com sucesso!'

def extract_track_uri(track_url):
    match = re.match(r'.*\/track\/(\w+).*', track_url)
    if match:
        track_id = match.group(1)
        return f'spotify:track:{track_id}'
    else:
        return None

def generate_suggested_tracks(sp, track1_uri, track2_uri, num_tracks):
    suggested_tracks = []
    seed_tracks = [track1_uri]
    if track2_uri:
        seed_tracks.append(track2_uri)

    average_bpm = (sp.audio_features(track1_uri)[0]['tempo'] + sp.audio_features(track2_uri)[0]['tempo']) / 2 if track2_uri else sp.audio_features(track1_uri)[0]['tempo']
    recommendations = sp.recommendations(seed_tracks=seed_tracks, limit=num_tracks, min_tempo=average_bpm-5, max_tempo=average_bpm+5)
    for track in recommendations['tracks']:
        suggested_tracks.append(track['uri'])

    return suggested_tracks

if __name__ == '__main__':
    app.run(debug=True)

import os
import spotipy
import pandas as pd
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyClientCredentials

def get_connection():
    load_dotenv()
    auth_manager = SpotifyClientCredentials(client_id=os.getenv("spotify_id"), 
                                            client_secret=os.getenv("spotify_key"))
    
    return spotipy.Spotify(auth_manager=auth_manager)

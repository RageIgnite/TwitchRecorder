import os
import time
import sys
from datetime import datetime
import requests
import subprocess
import streamlink
import json  # Added for credentials handling

def read_users():
    """Reads the list of users from 'users.txt'."""
    try:
        with open('users.txt', 'r') as f:
            return [line.strip() for line in f.read().split(',')]
    except FileNotFoundError:
        print("Error: users.txt file not found.")
        sys.exit(1)

def get_access_token(client_id, client_secret):
    """Fetch an App Access Token from Twitch."""
    url = "https://id.twitch.tv/oauth2/token"
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }
    
    try:
        response = requests.post(url, params=payload)
        if response.status_code == 200:
            return response.json().get('access_token', None)
        else:
            print(f"Token Error: {response.text}")
            sys.exit(1)
    except Exception as e:
        print(f"Error getting token: {str(e)}")
        return None

def is_live(username, client_id, access_token):
    """Checks if a user is live using Twitch API (with proper auth)."""
    headers = {
        'Client-ID': client_id,
        'Authorization': f'Bearer {access_token}'
    }
    
    try:
        response = requests.get(
            'https://api.twitch.tv/helix/streams',
            headers=headers,
            params={'user_login': username}
        )
        
        if response.status_code == 200:
            data = response.json()
            return len(data['data']) > 0
        else:
            print(f"API Error for {username}: Status Code: {response.status_code}")
    except Exception as e:
        print(f"Request Failed for {username}: {str(e)}")
    
    return False

def get_stream_url(username):
    """Gets the stream URL using Streamlink."""
    try:
        streams = streamlink.streams(f"https://www.twitch.tv/{username}")
        if not streams:
            return None
        selected_quality = 'best'
        return streams.get(selected_quality, next(iter(streams.values()))).url
    except Exception as e:
        print(f"Stream URL Error for {username}: {str(e)}")
        return None

def start_recording(username):
    """Starts recording using FFmpeg and returns process info."""
    directory = username
    os.makedirs(directory, exist_ok=True)
    
    now = datetime.now()
    filename = f"{directory}/{now.strftime('%Y-%m-%d-%H-%M-%S')}_{username}.mp4"
    
    stream_url = get_stream_url(username)
    if not stream_url:
        print(f"Could not find suitable stream URL for {username}")
        return None
    
    try:
        ffmpeg_cmd = ["ffmpeg", "-i", stream_url, "-c", "copy", filename]
        process = subprocess.Popen(ffmpeg_cmd)
        
        return {
            'process': process,
            'started_at': now,
            'output_path': filename
        }
    except Exception as e:
        print(f"FFmpeg Error for {username}: {str(e)}")
        return None

def stop_recording(process_info):
    """Stops a recording process."""
    if process_info and 'process' in process_info:
        try:
            process = process_info['process']
            process.terminate()
            print(f"Stopped recording for {process_info}")
        except Exception as e:
            print(f"Stop Error: {str(e)}")

# --- New Credentials Management Functions ---
def load_credentials():
    """Load saved Twitch credentials from file."""
    try:
        with open('credentials.json', 'r') as f:
            data = json.load(f)
            return (data.get('client_id'), 
                    data.get('client_secret'))
    except FileNotFoundError:
        print("No credentials file found.")
        return None, None
    except json.JSONDecodeError:
        print("Invalid credentials format. Please re-enter.")
        return None, None

def save_credentials(client_id, client_secret):
    """Saves valid Twitch credentials to a JSON file."""
    try:
        with open('credentials.json', 'w') as f:
            data = {
                'client_id': client_id.strip(),
                'client_secret': client_secret.strip()
            }
            json.dump(data, f)
            print("Credentials saved successfully.")
    except Exception as e:
        print(f"Error saving credentials: {str(e)}")

def main():
    # First try loading existing credentials
    loaded_client_id, loaded_client_secret = load_credentials()
    
    access_token_valid = False
    client_id, client_secret = None, None
    
    while not access_token_valid:
        if loaded_client_id and loaded_client_secret:
            print("Using stored credentials...")
            current_access_token = get_access_token(
                loaded_client_id,
                loaded_client_secret
            )
            
            if current_access_token is not None:
                # Credentials are valid!
                client_id, client_secret = (
                    loaded_client_id,
                    loaded_client_secret
                )
                access_token_valid = True
                break
            else:
                print("Stored credentials failed validation.")
        
        # Prompt for new credentials
        entered_client_id = input(
            "Enter your Twitch Client ID (from dev.twitch.tv): "
        ).strip()
        entered_client_secret = input(
            "Enter your Twitch Client Secret: "
        ).strip()
        
        access_token = get_access_token(entered_client_id, entered_client_secret)
        
        if access_token is not None:
            # Valid credentials! Save them
            client_id, client_secret = (
                entered_client_id,
                entered_client_secret
            )
            
            save_credentials(client_id, client_secret)
            print("Credentials saved successfully.")
            access_token_valid = True
        else:
            print("\nInvalid Client ID or Secret. Try again.\n")
    
    # Main program logic now uses stored/validated credentials
    access_token = get_access_token(client_id, client_secret)
    
    if not access_token:
        print("Failed to authenticate with Twitch. Exiting.")
        return
    
    try:
        users = read_users()
    except Exception as e:
        print(f"Error loading user list: {e}")
        sys.exit(1)

    interval = int(input("Enter check interval (seconds, recommended 60): "))
    processes = {}  # Maps username to process info dict

    try:
        while True:
            current_live = []
            
            for user in users:
                if is_live(user, client_id, access_token):
                    print(f"User {user} is LIVE now.")
                    current_live.append(user)
                
            new_to_start = [u for u in current_live if u not in processes]
            existing_offline = [u for u in processes.keys() if u not in current_live]
            
            # Start new recordings
            for user in new_to_start:
                info = start_recording(user)
                if info and 'process' in info:
                    print(f"Recording started: {user} -> {info['output_path']}")
                    processes[user] = info
                else:
                    print(f"Failed to start recording for {user}.")
            
            # Stop offline recordings
            for user in existing_offline:
                if user in processes:
                    process_info = processes.pop(user)
                    stop_recording(process_info)
                    
            time.sleep(interval)  # Wait before next check
            
    except KeyboardInterrupt:
        print("Stopping all ongoing recordings...")
        while processes:
            user, info = processes.popitem()
            stop_recording(info)

if __name__ == "__main__":
    main()

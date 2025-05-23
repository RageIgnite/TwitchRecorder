import os
import time
import sys
from datetime import datetime
import requests
import subprocess
import streamlink
import json  # Added for credentials handling

def read_users():
    """Reads the list of users from 'users.txt', prompting for input if the file is missing or empty."""
    try:
        with open('users.txt', 'r') as f:
            content = f.read().strip()
            if content:
                # Ensure that we handle cases where users might have spaces around commas
                # and filter out empty strings if there are multiple commas (e.g. "user1,,user2")
                usernames = [user.strip() for user in content.split(',') if user.strip()]
                if not usernames: # If all entries were empty strings or just commas
                    raise FileNotFoundError # Treat as empty to trigger input
                return usernames
            else:
                # File is empty
                raise FileNotFoundError  # Treat as if file not found to trigger user input
    except FileNotFoundError:
        print("users.txt not found or is empty.")
        user_input = input("Please enter Twitch usernames, separated by commas: ").strip()

        if not user_input:
            print("No users provided. Exiting.")
            sys.exit(1)

        # Parse the input string into a list of usernames, ensuring no empty strings
        usernames = [user.strip() for user in user_input.split(',') if user.strip()]
        
        # if after stripping and splitting, the list is empty (e.g. input was ",,,")
        if not usernames:
            print("No valid usernames provided after parsing. Exiting.")
            sys.exit(1)

        save_choice = input("Do you want to save these usernames to users.txt for future use? (y/n): ").lower()
        if save_choice in ['y', 'yes']:
            try:
                with open('users.txt', 'w') as f:
                    f.write(','.join(usernames))
                print("Usernames saved to users.txt.")
            except IOError as e:
                print(f"Error saving usernames to users.txt: {e}")
        
        return usernames

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
            # Do not sys.exit here, let main handle attempts
            print(f"Token Error: {response.status_code} - {response.text}") 
            return None # Return None on failure
    except Exception as e:
        print(f"Error getting token: {str(e)}")
        return None 

def is_live(username, client_id, access_token):
    """Checks if a user is live using Twitch API (with proper auth). Returns None on API error."""
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
            # Detailed error for non-200 responses
            print(f"API Error for {username}: Status Code: {response.status_code}, Response: {response.text}")
            return None  # Indicate error
    except requests.exceptions.RequestException as e: # More specific exception for requests
        # Error for request failures (network issue, etc.)
        print(f"Request Failed for {username}: {str(e)}")
        return None  # Indicate error
    except Exception as e: # Catch any other unexpected errors
        print(f"An unexpected error occurred while checking live status for {username}: {str(e)}")
        return None


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
        ffmpeg_cmd = ["ffmpeg", "-i", stream_url, "-c", "copy", filename, "-loglevel", "warning"]
        process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        return {
            'process': process,
            'started_at': now,
            'output_path': filename,
            'username': username # Added username
        }
    except Exception as e:
        print(f"FFmpeg Error for {username}: {str(e)}")
        return None

def stop_recording(process_info):
    """Stops a recording process, providing context-specific messages."""
    if process_info and 'process' in process_info:
        process = process_info['process']
        username = process_info.get('username')
        output_path = process_info.get('output_path', 'N/A')

        try:
            process.terminate()  # Send SIGTERM
            stdout, stderr = process.communicate(timeout=10) # Wait for graceful termination

            if username:
                print(f"Stopped recording for {username}.")
            else:
                print(f"Stopped recording process with PID {process.pid}. Output file: {output_path}")
            
            if stdout or stderr: 
                print(f"FFmpeg output for {username or process.pid} on stop: STDOUT: {stdout.decode(errors='ignore')} STDERR: {stderr.decode(errors='ignore')}")

        except subprocess.TimeoutExpired:
            if username:
                print(f"FFmpeg process for {username} (PID {process.pid}, Output: {output_path}) did not terminate gracefully, killing.")
            else:
                print(f"FFmpeg process with PID {process.pid} (Output: {output_path}) did not terminate gracefully, killing.")
            process.kill()
        except Exception as e:
            try:
                stdout, stderr = process.communicate(timeout=1) 
                if stdout or stderr:
                    print(f"FFmpeg output for {username or process.pid} on error: STDOUT: {stdout.decode(errors='ignore')} STDERR: {stderr.decode(errors='ignore')}")
            except Exception as comm_error:
                print(f"Error during communicate on exception: {comm_error}")

            if username:
                print(f"Stop Error for {username} (Output: {output_path}): {str(e)}")
            else:
                print(f"Stop Error for process with PID {process.pid} (Output: {output_path}): {str(e)}")


# --- Credentials Management Functions ---
def load_credentials():
    """Load saved Twitch credentials from file."""
    try:
        with open('credentials.json', 'r') as f:
            data = json.load(f)
            return (data.get('client_id'), 
                    data.get('client_secret'))
    except FileNotFoundError:
        # print("No credentials file found.") # Suppress this message for cleaner attempt loop
        return None, None
    except json.JSONDecodeError:
        print("Invalid credentials format in credentials.json. Please re-enter or delete the file.")
        return None, None # Treat as no valid creds

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
    original_loaded_client_id, original_loaded_client_secret = load_credentials()
    
    access_token_valid = False
    client_id, client_secret = None, None
    access_token = None 
    credential_attempts = 0
    MAX_CREDENTIAL_ATTEMPTS = 3

    # Attempt to use loaded credentials first if they exist
    if original_loaded_client_id and original_loaded_client_secret:
        print("Attempting to use stored credentials...")
        access_token = get_access_token(original_loaded_client_id, original_loaded_client_secret)
        if access_token:
            print("Stored credentials validated successfully.")
            client_id = original_loaded_client_id
            client_secret = original_loaded_client_secret
            access_token_valid = True
        else:
            print("Stored credentials failed validation.")
            credential_attempts += 1 # Count as first failed attempt

    # Loop if stored credentials failed or were not present
    while not access_token_valid:
        if credential_attempts >= MAX_CREDENTIAL_ATTEMPTS:
            print("Maximum credential validation attempts reached. Please check your Client ID and Secret and try again later. Exiting.")
            sys.exit(1)

        print(f"Credential attempt {credential_attempts + 1} of {MAX_CREDENTIAL_ATTEMPTS}.")
        entered_client_id = input(
            "Enter your Twitch Client ID (from dev.twitch.tv): "
        ).strip()
        entered_client_secret = input(
            "Enter your Twitch Client Secret: "
        ).strip()

        if not entered_client_id or not entered_client_secret:
            print("\nClient ID or Secret cannot be empty.")
            credential_attempts += 1
            continue # Go to next attempt or exit if maxed out

        access_token = get_access_token(entered_client_id, entered_client_secret)
        
        if access_token:
            print("Credentials validated successfully.")
            client_id = entered_client_id
            client_secret = entered_client_secret
            access_token_valid = True
            save_credentials(client_id, client_secret) # Save newly entered valid credentials
        else:
            print("\nInvalid Client ID or Secret, or failed to get token.")
            credential_attempts += 1
            # Loop will check attempts at the beginning

    if not access_token: 
        print("Failed to authenticate with Twitch. Exiting.") # Should be caught by loop logic
        sys.exit(1)
    
    try:
        users = read_users()
    except SystemExit: 
        print("Exiting script due to issues in user loading.")
        sys.exit(1)
    except Exception as e: 
        print(f"Error loading user list: {e}") 
        sys.exit(1)

    interval = 0 # Initialize interval before the loop
    while True:
        interval_input = input("Enter check interval (seconds, recommended 60): ").strip()
        try:
            interval_val = int(interval_input)
            if interval_val > 0:
                interval = interval_val # Assign to the main interval variable
                break  # Exit loop on valid input
            else:
                print("Interval must be a positive number.")
        except ValueError:
            print("Invalid input. Please enter a whole number for the interval.")
        
    processes = {}

    try:
        while True:
            current_live = []
            for user in users:
                live_status = is_live(user, client_id, access_token) 
                if live_status is True:
                    print(f"User {user} is LIVE now.")
                    current_live.append(user)
                elif live_status is None:
                    print(f"Could not determine live status for {user} due to an API error. Skipping for this check.")
            
            new_to_start = [u for u in current_live if u not in processes]
            existing_offline_or_error = [u for u in processes.keys() if u not in current_live]
            
            for user_to_start in new_to_start:
                if user_to_start not in processes: 
                    print(f"Attempting to start recording for {user_to_start}...")
                    info = start_recording(user_to_start) 
                    if info and 'process' in info:
                        print(f"Recording started: {user_to_start} -> {info['output_path']}")
                        processes[user_to_start] = info
                    else:
                        print(f"Failed to start recording for {user_to_start}.")
            
            for user_to_stop in existing_offline_or_error:
                if user_to_stop in processes:
                    print(f"User {user_to_stop} is no longer confirmed live or status unknown. Stopping recording if active.")
                    process_info = processes.pop(user_to_stop)
                    stop_recording(process_info)
                    
            print(f"Check complete. Waiting {interval} seconds...")
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\nStopping all ongoing recordings due to user interruption...")
        active_recordings = list(processes.items()) 
        for user, info in active_recordings:
            print(f"Stopping recording for {info.get('username', 'unknown user')}...")
            stop_recording(info)
        print("All recordings stopped. Exiting.")
    except Exception as e:
        print(f"An unexpected error occurred in the main loop: {e}")
        active_recordings = list(processes.items())
        for user, info in active_recordings:
            print(f"Stopping recording for {info.get('username', 'unknown user')} due to error...")
            stop_recording(info)
        print("Exiting due to unexpected error.")
    finally:
        print("Script finished.")

if __name__ == "__main__":
    main()

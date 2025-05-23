import os
import time
import sys
from datetime import datetime
import requests
import subprocess
import streamlink
import json
import shutil
import configparser
import logging
import logging.handlers
import re

# --- Global logger instance ---
logger = logging.getLogger('TwitchRecorder')

# --- Default Configuration Values ---
DEFAULT_FFMPEG_PATH = ""
DEFAULT_CHECK_INTERVAL = "60"
DEFAULT_OUTPUT_DIRECTORY = "recordings"
DEFAULT_USERS_FILE = "users.txt"
DEFAULT_CLIENT_ID = ""
DEFAULT_CLIENT_SECRET = ""
DEFAULT_STREAM_QUALITY = "best"
DEFAULT_FILENAME_FORMAT = "{timestamp}_{username}_{title}.mp4"
DEFAULT_POST_PROCESSING_COMMAND = ""
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FILE = "recorder.log"
DEFAULT_QUIET_MODE = "false"


def setup_logging(log_level_str="INFO", log_file="recorder.log", quiet_mode=False):
    """Configures logging to console and a rotating file."""
    numeric_level = getattr(logging, log_level_str.upper(), None)
    if not isinstance(numeric_level, int):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stderr)
        logger.warning(f"Invalid log level: {log_level_str}. Defaulting to INFO.")
        numeric_level = logging.INFO
    
    logger.setLevel(numeric_level)
    
    if logger.hasHandlers():
        logger.handlers.clear()
        
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    if not quiet_mode:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    
    try:
        rfh = logging.handlers.RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)
        rfh.setFormatter(formatter)
        logger.addHandler(rfh)
    except Exception as e:
        basicConfig_level = logging.INFO if not quiet_mode else logging.ERROR
        logging.basicConfig(level=basicConfig_level, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stderr)
        logger.error(f"Failed to set up RotatingFileHandler for {log_file}: {e}. Logging to stderr if not quiet.", exc_info=True)


def get_ffmpeg_path(config=None):
    """Determines the path to the ffmpeg executable, checking config, env var, then PATH."""
    if config:
        ffmpeg_path_config = config.get('TwitchRecorder', 'ffmpeg_path', fallback=DEFAULT_FFMPEG_PATH)
        if ffmpeg_path_config:
            if os.path.isfile(ffmpeg_path_config):
                logger.debug(f"FFmpeg path found in config: {ffmpeg_path_config}")
                return ffmpeg_path_config
            elif os.path.isdir(ffmpeg_path_config):
                exe_name = "ffmpeg.exe" if os.name == 'nt' else "ffmpeg"
                potential_path = os.path.join(ffmpeg_path_config, exe_name)
                if os.path.isfile(potential_path):
                    logger.debug(f"FFmpeg executable found in configured directory: {potential_path}")
                    return potential_path
                potential_path_no_ext = os.path.join(ffmpeg_path_config, "ffmpeg")
                if os.name == 'nt' and os.path.isfile(potential_path_no_ext):
                     logger.debug(f"FFmpeg executable (no ext) found in configured directory: {potential_path_no_ext}")
                     return potential_path_no_ext
            logger.warning(f"ffmpeg_path '{ffmpeg_path_config}' in config is not a valid file or directory containing ffmpeg.")

    ffmpeg_path_env = os.environ.get("FFMPEG_PATH")
    if ffmpeg_path_env:
        if os.path.isfile(ffmpeg_path_env):
            logger.debug(f"FFmpeg path found in FFMPEG_PATH environment variable: {ffmpeg_path_env}")
            return ffmpeg_path_env
        elif os.path.isdir(ffmpeg_path_env):
            exe_name = "ffmpeg.exe" if os.name == 'nt' else "ffmpeg"
            potential_path = os.path.join(ffmpeg_path_env, exe_name)
            if os.path.isfile(potential_path):
                logger.debug(f"FFmpeg executable found in FFMPEG_PATH directory: {potential_path}")
                return potential_path
        logger.warning(f"FFMPEG_PATH '{ffmpeg_path_env}' is not a valid file or directory containing ffmpeg.")
    
    ffmpeg_in_path = shutil.which("ffmpeg")
    if ffmpeg_in_path:
        logger.debug(f"FFmpeg found in system PATH: {ffmpeg_in_path}")
        return ffmpeg_in_path

    logger.error("FFmpeg not found. Please install it, add to PATH, or set ffmpeg_path in config.ini or FFMPEG_PATH environment variable.")
    return None


def read_users_from_file(users_filepath_param, config_for_save):
    """Reads the list of users from the specified file, prompting for input if missing/empty."""
    try:
        with open(users_filepath_param, 'r') as f:
            content = f.read().strip()
            if content:
                initial_usernames = [user.strip() for user in content.split(',') if user.strip()]
                if not initial_usernames: # All entries were empty or just commas
                    logger.warning(f"Users file '{users_filepath_param}' contained only whitespace or commas. Prompting for input.")
                    raise FileNotFoundError 
                
                # Remove duplicates
                unique_usernames = list(dict.fromkeys(initial_usernames)) # Preserves order while removing duplicates
                if len(unique_usernames) < len(initial_usernames):
                    logger.info(f"Duplicate usernames found in '{users_filepath_param}' and were removed.")
                
                logger.info(f"Read and processed unique users from '{users_filepath_param}': {unique_usernames}")
                return unique_usernames
            else: # File is empty
                logger.warning(f"Users file '{users_filepath_param}' is empty. Prompting for input.")
                raise FileNotFoundError
    except FileNotFoundError:
        logger.warning(f"'{users_filepath_param}' not found or is empty. Prompting for usernames.")
        user_input = input(f"'{users_filepath_param}' not found or empty. Please enter Twitch usernames, separated by commas: ").strip()
        if not user_input:
            logger.error("No users provided via prompt. Exiting.")
            sys.exit(1)
        
        initial_prompted_usernames = [user.strip() for user in user_input.split(',') if user.strip()]
        if not initial_prompted_usernames:
            logger.error("No valid usernames provided after parsing prompt input. Exiting.")
            sys.exit(1)

        # Remove duplicates from prompted input as well
        unique_prompted_usernames = list(dict.fromkeys(initial_prompted_usernames))
        if len(unique_prompted_usernames) < len(initial_prompted_usernames):
            logger.info("Duplicate usernames found in prompted input and were removed.")

        logger.info(f"Users obtained from prompt: {unique_prompted_usernames}")
        
        save_choice = input(f"Do you want to save these usernames to {users_filepath_param} for future use? (y/n): ").lower()
        if save_choice in ['y', 'yes']:
            try:
                with open(users_filepath_param, 'w') as f:
                    f.write(','.join(unique_prompted_usernames)) # Save unique list
                logger.info(f"Usernames saved to {users_filepath_param}.")
                if not os.path.exists('config.ini') and config_for_save:
                    try:
                        with open('config.ini', 'w') as configfile:
                            config_for_save.write(configfile)
                        logger.info("Default config.ini created as users were saved.")
                    except IOError as e_cfg:
                        logger.error(f"Error creating default config.ini: {e_cfg}", exc_info=True)
            except IOError as e_usr:
                logger.error(f"Error saving usernames to {users_filepath_param}: {e_usr}", exc_info=True)
        return unique_prompted_usernames
    except IOError as e: 
        logger.error(f"IOError reading users file '{users_filepath_param}': {e}. Exiting.", exc_info=True)
        sys.exit(1)


def get_access_token(client_id, client_secret):
    """Fetch an App Access Token from Twitch."""
    url = "https://id.twitch.tv/oauth2/token" # Constant can be used here
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }
    try:
        response = requests.post(url, params=payload)
        response.raise_for_status() # Check for HTTP errors
        logger.debug("Access token request successful.")
        return response.json().get('access_token')
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error getting access token: {http_err.response.status_code} - {http_err.response.text}", exc_info=True)
        if http_err.response.status_code == 401 or http_err.response.status_code == 403:
             logger.warning("Check your client_id and client_secret in config.ini or credentials.json.")
        return None
    except requests.exceptions.RequestException as req_err:
        logger.error(f"RequestException getting access token: {req_err}", exc_info=True)
        return None
    except json.JSONDecodeError as json_err:
        logger.error(f"JSONDecodeError parsing access token response: {json_err}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting access token: {e}", exc_info=True)
        return None


def is_live(username, client_id, access_token):
    """
    Checks if a user is live using Twitch API and returns their status and stream title.
    Returns: A tuple (live_status, stream_title)
    """
    headers = {'Client-ID': client_id, 'Authorization': f'Bearer {access_token}'}
    url = "https://api.twitch.tv/helix/streams" # Constant can be used
    try:
        response = requests.get(url, headers=headers, params={'user_login': username})
        response.raise_for_status() 
        data = response.json()
        stream_data = data.get('data', [])
        if stream_data: 
            logger.debug(f"Stream data for {username}: {stream_data[0]}")
            return True, stream_data[0].get('title')
        else: 
            logger.debug(f"{username} is not live.")
            return False, None
    except requests.exceptions.HTTPError as http_err:
        status_code = http_err.response.status_code
        logger.error(f"API Error for {username}: Status Code: {status_code}, Response: {http_err.response.text}", exc_info=True)
        if status_code == 401 or status_code == 403:
            logger.warning(f"Authentication failed for {username} (HTTP {status_code}). Token may be invalid or expired.")
            return 'AUTH_FAILURE', None 
        return None, None 
    except requests.exceptions.RequestException as e:
        logger.error(f"Request Failed for {username}: {str(e)}", exc_info=True)
        return None, None
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON for {username}: {str(e)}", exc_info=True)
        return None, None
    except Exception as e:
        logger.error(f"Unexpected error checking live status for {username}: {str(e)}", exc_info=True)
        return None, None


def get_stream_url(username, config):
    """Gets the stream URL using Streamlink, using configured quality."""
    recorder_config = config['TwitchRecorder']
    stream_quality_config = recorder_config.get('stream_quality', DEFAULT_STREAM_QUALITY) 
    try:
        streams = streamlink.streams(f"https://www.twitch.tv/{username}")
        if not streams:
            logger.info(f"No streams found for {username} via Streamlink.")
            return None
        
        if stream_quality_config in streams:
            logger.debug(f"Quality '{stream_quality_config}' found for {username}.")
            return streams[stream_quality_config].url
        elif 'best' in streams: 
            logger.info(f"Configured quality '{stream_quality_config}' not found for {username}. Using 'best'.")
            return streams['best'].url
        else: 
            fallback_stream = next(iter(streams.values()), None)
            if fallback_stream:
                logger.info(f"Neither configured quality '{stream_quality_config}' nor 'best' found for {username}. Using first available stream.")
                return fallback_stream.url
            else:
                logger.warning(f"No streams available for {username} after checking configured and best quality.")
                return None
    except streamlink.exceptions.NoPluginError:
        logger.error(f"Streamlink plugin error for {username}: No plugin found for Twitch.tv.", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Stream URL Error for {username} (Quality: {stream_quality_config}): {str(e)}", exc_info=True)
        return None

def sanitize_filename(filename_component):
    """Sanitizes a string component to be safe for filenames."""
    if not filename_component:
        return ""
    sanitized = re.sub(r'[\\/*?:"<>|\x00-\x1f]', '_', filename_component)
    sanitized = re.sub(r'_+', '_', sanitized) 
    sanitized = sanitized.strip('_') 
    return sanitized[:100] 

def start_recording(username, config, stream_title=None):
    """Starts recording using FFmpeg and returns process info."""
    recorder_config = config['TwitchRecorder']
    output_directory_base = recorder_config.get('output_directory', DEFAULT_OUTPUT_DIRECTORY)
    filename_format_str = recorder_config.get('filename_format', DEFAULT_FILENAME_FORMAT)
    
    user_directory = os.path.join(output_directory_base, username)
    os.makedirs(user_directory, exist_ok=True)
    
    now = datetime.now()
    timestamp_str = now.strftime('%Y-%m-%d-%H-%M-%S')
    
    filename = filename_format_str.replace("{timestamp}", timestamp_str).replace("{username}", username)
    if stream_title and "{title}" in filename:
        sanitized_title = sanitize_filename(stream_title)
        filename = filename.replace("{title}", sanitized_title)
        logger.debug(f"Using sanitized title '{sanitized_title}' in filename for {username}.")
    else: 
        filename = filename.replace("_{title}", "").replace("{title}", "")
        if "{title}" in filename_format_str:
             logger.debug(f"Stream title placeholder found in format, but title not used for {username} (title not available or placeholder missing).")
    
    output_path = os.path.join(user_directory, filename)
    
    stream_url = get_stream_url(username, config) 
    if not stream_url:
        logger.error(f"Could not find suitable stream URL for {username} with quality '{recorder_config.get('stream_quality', DEFAULT_STREAM_QUALITY)}'.")
        return None

    ffmpeg_executable = get_ffmpeg_path(config=config) 
    if not ffmpeg_executable:
        # Error already logged by get_ffmpeg_path
        return None
    
    try:
        logger.info(f"Starting recording for {username}. Output: {output_path}")
        # Hide stream URL from logs for privacy/security
        logger.debug(f"FFmpeg command for {username}: {[ffmpeg_executable, '-i', '******', '-c', 'copy', output_path, '-loglevel', 'warning']}")
        ffmpeg_cmd = [ffmpeg_executable, "-i", stream_url, "-c", "copy", output_path, "-loglevel", "warning"]
        process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        return {'process': process, 'started_at': now, 'output_path': output_path, 'username': username}
    except FileNotFoundError: # If ffmpeg_executable path is somehow invalid at Popen stage
        logger.error(f"FFmpeg executable not found at path '{ffmpeg_executable}' for user {username}. Recording not started.", exc_info=True)
        return None
    except subprocess.SubprocessError as e: # More general subprocess error
        logger.error(f"Subprocess error starting FFmpeg for {username}: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error starting FFmpeg for {username}: {e}", exc_info=True)
        return None

def stop_recording(process_info):
    """Stops a recording process, providing context-specific messages."""
    if not process_info or 'process' not in process_info:
        logger.error("stop_recording called with invalid process_info.")
        return

    process = process_info['process']
    username = process_info.get('username', 'UnknownUser')
    output_path = process_info.get('output_path', 'N/A')

    try:
        logger.info(f"Stopping recording for {username} (Output: {output_path}).")
        process.terminate()
        
        try:
            stdout, stderr = process.communicate(timeout=10) 
            logger.info(f"FFmpeg process for {username} terminated gracefully.")
            if stdout: 
                logger.debug(f"FFmpeg STDOUT (on stop) for {username}: {stdout.decode(errors='ignore').strip()}")
            if stderr: # FFmpeg often logs to stderr even for info
                logger.debug(f"FFmpeg STDERR (on stop) for {username}: {stderr.decode(errors='ignore').strip()}")
        except subprocess.TimeoutExpired:
            logger.warning(f"FFmpeg process for {username} (PID {process.pid}, Output: {output_path}) did not terminate in time. Sending SIGKILL.")
            process.kill()
            stdout, stderr = process.communicate() 
            if stdout:
                logger.debug(f"FFmpeg STDOUT (on kill) for {username}: {stdout.decode(errors='ignore').strip()}")
            if stderr:
                logger.debug(f"FFmpeg STDERR (on kill) for {username}: {stderr.decode(errors='ignore').strip()}")
        except Exception as comm_err:
             logger.error(f"Error during FFmpeg process communicate for {username}: {comm_err}", exc_info=True)
    
    except ProcessLookupError:
        logger.warning(f"FFmpeg process for {username} (PID {process.pid}, Output: {output_path}) not found. Already terminated?", exc_info=True)
    except Exception as e: 
        logger.error(f"Error stopping FFmpeg process for {username} (PID {process.pid}, Output: {output_path}): {e}", exc_info=True)
        if process.poll() is None: 
            try:
                logger.warning(f"Attempting to kill FFmpeg process for {username} (PID {process.pid}) due to prior error.")
                process.kill()
            except Exception as kill_err:
                logger.error(f"Failed to kill FFmpeg process for {username} (PID {process.pid}) after error: {kill_err}", exc_info=True)


def load_credentials():
    """Load saved Twitch credentials from credentials.json (legacy)."""
    try:
        with open('credentials.json', 'r') as f:
            data = json.load(f)
            logger.info("Loaded credentials from legacy credentials.json file.")
            return data.get('client_id'), data.get('client_secret')
    except FileNotFoundError:
        return None, None
    except json.JSONDecodeError:
        logger.warning("Invalid JSON format in credentials.json. This file will be ignored if credentials are set in config.ini or via prompt.")
        return None, None
    except IOError as e:
        logger.warning(f"IOError reading credentials.json: {e}. This file will be ignored.", exc_info=True)
        return None, None

def save_credentials(client_id, client_secret):
    """Saves valid Twitch credentials to credentials.json."""
    try:
        with open('credentials.json', 'w') as f:
            data = {'client_id': client_id.strip(), 'client_secret': client_secret.strip()}
            json.dump(data, f, indent=4)
            logger.info("Credentials saved to credentials.json (used if not set in config.ini).")
    except IOError as e:
        logger.error(f"Error saving credentials to credentials.json: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error saving credentials: {e}", exc_info=True)


def main():
    # --- Initial Logging Setup (before config is fully parsed for log settings) ---
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stdout)
    logger.info("TwitchRecorder script starting...")

    # --- Configuration Loading ---
    config = configparser.ConfigParser()
    config['TwitchRecorder'] = {
        'ffmpeg_path': DEFAULT_FFMPEG_PATH,
        'check_interval': DEFAULT_CHECK_INTERVAL,
        'output_directory': DEFAULT_OUTPUT_DIRECTORY,
        'users_file': DEFAULT_USERS_FILE,
        'client_id': DEFAULT_CLIENT_ID,
        'client_secret': DEFAULT_CLIENT_SECRET,
        'stream_quality': DEFAULT_STREAM_QUALITY,
        'filename_format': DEFAULT_FILENAME_FORMAT,
        'post_processing_command': DEFAULT_POST_PROCESSING_COMMAND,
        'log_level': DEFAULT_LOG_LEVEL,
        'log_file': DEFAULT_LOG_FILE,
        'quiet_mode': DEFAULT_QUIET_MODE
    }
    
    if os.path.exists('config.ini'):
        try:
            config.read('config.ini')
            logger.info("Successfully read configuration from config.ini.")
        except configparser.Error as e:
            logger.error(f"Error reading config.ini: {e}. Using default values.", exc_info=True)
    else:
        logger.info("config.ini not found. Using default values. A default config.ini will be created if users or credentials are saved, or on first run.")
        try:
            with open('config.ini', 'w') as configfile:
                config.write(configfile)
            logger.info("Created a default config.ini with initial settings.")
        except IOError as e:
            logger.error(f"Could not write default config.ini: {e}", exc_info=True)

    # --- Setup Logging (based on config) ---
    log_level = config.get('TwitchRecorder', 'log_level', fallback=DEFAULT_LOG_LEVEL)
    log_file = config.get('TwitchRecorder', 'log_file', fallback=DEFAULT_LOG_FILE)
    quiet_mode = config.getboolean('TwitchRecorder', 'quiet_mode', fallback=config.getboolean('TwitchRecorder', DEFAULT_QUIET_MODE))
    setup_logging(log_level_str=log_level, log_file=log_file, quiet_mode=quiet_mode)
    
    logger.info("TwitchRecorder script initialized with full logging.")

    # --- Authentication ---
    original_loaded_client_id, original_loaded_client_secret = load_credentials() # Legacy
    
    client_id_conf = config.get('TwitchRecorder', 'client_id')
    client_secret_conf = config.get('TwitchRecorder', 'client_secret')

    access_token_valid = False
    client_id, client_secret = None, None
    access_token = None 
    credential_attempts = 0
    MAX_CREDENTIAL_ATTEMPTS = 3 

    if client_id_conf and client_secret_conf:
        logger.info("Attempting to use credentials from config.ini...")
        access_token = get_access_token(client_id_conf, client_secret_conf)
        if access_token:
            logger.info("Credentials from config.ini validated successfully.")
            client_id, client_secret = client_id_conf, client_secret_conf
            access_token_valid = True
        else:
            logger.warning("Credentials from config.ini failed validation.")
    
    if not access_token_valid and original_loaded_client_id and original_loaded_client_secret:
        logger.info("Attempting to use stored credentials from legacy credentials.json...")
        access_token = get_access_token(original_loaded_client_id, original_loaded_client_secret)
        if access_token:
            logger.info("Stored credentials (credentials.json) validated successfully.")
            client_id, client_secret = original_loaded_client_id, original_loaded_client_secret
            access_token_valid = True
        else:
            logger.warning("Stored credentials (credentials.json) failed validation.")
            if not (client_id_conf and client_secret_conf):
                 credential_attempts +=1

    while not access_token_valid:
        if credential_attempts >= MAX_CREDENTIAL_ATTEMPTS:
            logger.critical("Maximum credential validation attempts reached. Exiting.")
            sys.exit(1)
        logger.info(f"Credential input attempt {credential_attempts + 1} of {MAX_CREDENTIAL_ATTEMPTS}.")
        entered_client_id = input("Enter your Twitch Client ID: ").strip()
        entered_client_secret = input("Enter your Twitch Client Secret: ").strip()
        if not entered_client_id or not entered_client_secret:
            logger.warning("Client ID or Secret cannot be empty when prompted.")
            credential_attempts += 1
            continue
        access_token = get_access_token(entered_client_id, entered_client_secret)
        if access_token:
            logger.info("Entered credentials validated successfully.")
            client_id, client_secret = entered_client_id, entered_client_secret
            access_token_valid = True
            save_credentials(client_id, client_secret) 
        else:
            logger.warning("Invalid Client ID or Secret from prompt, or token fetch failed.")
            credential_attempts += 1
            
    if not access_token: 
        logger.critical("Failed to authenticate with Twitch after all methods. Exiting.")
        sys.exit(1)
    logger.info("Successfully authenticated with Twitch.")

    # --- Log Startup Info ---
    users_filepath = config.get('TwitchRecorder', 'users_file', fallback=DEFAULT_USERS_FILE)
    try:
        users = read_users_from_file(users_filepath_param=users_filepath, config_for_save=config)
        logger.info(f"Monitoring Twitch users: {', '.join(users)}")
    except SystemExit: 
        logger.critical("Exiting due to issues in user loading (no users provided).")
        sys.exit(1)
    except Exception as e: 
        logger.critical(f"Critical error loading user list from '{users_filepath}': {e}", exc_info=True)
        sys.exit(1)

    check_interval_val = config.getint('TwitchRecorder', 'check_interval', fallback=int(DEFAULT_CHECK_INTERVAL))
    if check_interval_val <=0:
        logger.warning(f"Configured check_interval '{check_interval_val}' is not positive. Using default {DEFAULT_CHECK_INTERVAL}s.")
        check_interval_val = int(DEFAULT_CHECK_INTERVAL)
    logger.info(f"Check interval set to: {check_interval_val} seconds")
    logger.info(f"Recordings will be saved to: {config.get('TwitchRecorder', 'output_directory', fallback=DEFAULT_OUTPUT_DIRECTORY)}")
    logger.info(f"Preferred stream quality: {config.get('TwitchRecorder', 'stream_quality', fallback=DEFAULT_STREAM_QUALITY)}")
    logger.info(f"Filename format: {config.get('TwitchRecorder', 'filename_format', fallback=DEFAULT_FILENAME_FORMAT)}")
    post_cmd = config.get('TwitchRecorder', 'post_processing_command', fallback=DEFAULT_POST_PROCESSING_COMMAND)
    if post_cmd:
        logger.info(f"Post-processing command configured: {post_cmd}")
    else:
        logger.info("No post-processing command configured.")
    
    interval = check_interval_val 
        
    processes = {}
    current_live_user_titles = {} 

    try:
        while True:
            current_live_user_titles.clear() 

            for user in users:
                live_status, title_from_api = is_live(user, client_id, access_token)
                
                if live_status == 'AUTH_FAILURE':
                    logger.error(f"Auth error checking {user}. Token might be expired. Re-authentication logic to be added.")
                    # For now, we'll just log and skip this user for this cycle
                    # A more robust solution would trigger re-authentication for the main token
                    # which is handled in more advanced versions of the script.
                    continue 
                
                if live_status is True:
                    logger.info(f"User {user} is LIVE. Title: {title_from_api}")
                    current_live_user_titles[user] = title_from_api
                elif live_status is False:
                    logger.debug(f"User {user} is offline.") 
                elif live_status is None: 
                    logger.warning(f"Could not get live status for {user} (API error). Skipping for this cycle.")
            
            users_to_start_recording = {
                u: title for u, title in current_live_user_titles.items() if u not in processes
            }
            users_to_stop_recording = [u for u in processes.keys() if u not in current_live_user_titles]
            
            for user_to_start, fetched_title in users_to_start_recording.items():
                if user_to_start not in processes: 
                    recording_info = start_recording(user_to_start, config, stream_title=fetched_title) 
                    if recording_info and 'process' in recording_info:
                        processes[user_to_start] = recording_info
                    else:
                        logger.error(f"Failed to start recording for {user_to_start} (check previous logs for details).")
            
            for user_to_stop in users_to_stop_recording:
                if user_to_stop in processes:
                    logger.info(f"User {user_to_stop} is no longer live or status unknown. Stopping recording.")
                    process_info_to_stop = processes.pop(user_to_stop)
                    stop_recording(process_info_to_stop)
                    
                    post_process_cmd_template = config.get('TwitchRecorder', 'post_processing_command', fallback='').strip()
                    if post_process_cmd_template and process_info_to_stop.get('output_path'):
                        output_filepath = process_info_to_stop['output_path']
                        try:
                            cmd_to_run = post_process_cmd_template.replace("{filepath}", output_filepath).replace("{username}", user_to_stop)
                            logger.info(f"Executing post-processing command for {user_to_stop}: {cmd_to_run}")
                            
                            completed_process = subprocess.run(cmd_to_run, shell=True, capture_output=True, text=True, timeout=300) 
                            
                            if completed_process.returncode == 0:
                                logger.info(f"Post-processing command for {user_to_stop} (file: {output_filepath}) completed successfully.")
                                if completed_process.stdout.strip():
                                     logger.debug(f"Post-process STDOUT for {user_to_stop}: {completed_process.stdout.strip()}")
                            else: 
                                logger.error(f"Post-processing command for {user_to_stop} (file: {output_filepath}) failed. RC: {completed_process.returncode}")
                                if completed_process.stdout.strip(): 
                                     logger.error(f"Post-process STDOUT for {user_to_stop}: {completed_process.stdout.strip()}")
                                if completed_process.stderr.strip():
                                     logger.error(f"Post-process STDERR for {user_to_stop}: {completed_process.stderr.strip()}")

                        except subprocess.TimeoutExpired:
                            logger.error(f"Post-processing command for {user_to_stop} (file: {output_filepath}) timed out after 5 minutes.")
                        except Exception as e_post:
                            logger.error(f"Error during post-processing for {user_to_stop} (file: {output_filepath}): {e_post}", exc_info=True)
                    
            logger.info(f"Check complete. Active recordings: {list(processes.keys())}. Waiting {interval} seconds...")
            time.sleep(interval)
            
    except KeyboardInterrupt:
        logger.info("User interruption (KeyboardInterrupt) detected. Stopping all ongoing recordings...")
    except Exception as e: 
        logger.critical(f"An unexpected critical error occurred in the main loop: {e}", exc_info=True)
    finally:
        logger.info("Initiating script shutdown sequence. Stopping all active recordings...")
        active_recordings = list(processes.items()) 
        for user, info in active_recordings:
            logger.info(f"Stopping recording for {info.get('username', 'unknown user')} due to script exit...")
            stop_recording(info)
        logger.info("All recordings stopped. TwitchRecorder script finished.")

if __name__ == "__main__":
    main()

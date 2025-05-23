# TwitchRecorder

TwitchRecorder is a Python script that periodically scans a list of Twitch usernames and automatically records their live streams using Streamlink and FFmpeg.

## Features

*   **Automatic Recording**: Detects when specified users go live and starts recording.
*   **Configurable**: Most settings are managed via a `config.ini` file.
    *   Customizable check interval, output directory, and user list file.
    *   Selectable stream quality (e.g., best, 1080p60, 720p, etc.).
    *   Flexible output filename formatting using placeholders: `{timestamp}`, `{username}`, `{title}`.
    *   Optional post-processing command execution after recordings finish.
*   **Robust Credential Management**: Handles Twitch API credentials securely with multiple fallback options.
*   **Detailed Logging**: Outputs to both console and a rotating log file (`recorder.log`).
    *   Configurable log level and a "quiet mode" for console output.
*   **Error Handling**: Includes specific messages for common issues and attempts token re-authentication.

## Prerequisites

Before running TwitchRecorder, ensure you have the following installed:

*   **Python 3**: This script is written for Python 3 (version 3.7+ recommended). You can check your Python version by running:
    ```bash
    python --version
    # or
    python3 --version
    ```
    If you don't have Python 3, please download and install it from [python.org](https://www.python.org/downloads/).

*   **FFmpeg**: This is required for processing and saving the video streams. The script will attempt to find FFmpeg in your system's PATH, via an `FFMPEG_PATH` environment variable, or through the `ffmpeg_path` setting in `config.ini`.

### Installing FFmpeg

*   **Windows**:
    *   Download FFmpeg from the official site: [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html).
    *   Extract the downloaded archive (e.g., to `C:\ffmpeg`).
    *   Add the `bin` directory (e.g., `C:\ffmpeg\bin`) to your system's PATH environment variable, or set the `FFMPEG_PATH` environment variable to this directory, or set `ffmpeg_path` in `config.ini`.

*   **Linux (Ubuntu/Debian)**:
    ```bash
    sudo apt update && sudo apt install ffmpeg
    ```

*   **Linux (Fedora)**:
    ```bash
    sudo dnf install ffmpeg
    ```

*   **macOS**:
    *   If you have Homebrew installed:
        ```bash
        brew install ffmpeg
        ```
    *   Otherwise, download from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html) and ensure it's in your PATH or configure `FFMPEG_PATH` / `ffmpeg_path` in `config.ini`.

## Configuration

TwitchRecorder uses a `config.ini` file to manage its settings. When you run the script for the first time, if `config.ini` is not found, a default version will be created in the same directory as the script. You should review and customize this file to your needs.

### `config.ini` Structure

All settings are under the `[TwitchRecorder]` section.

```ini
[TwitchRecorder]
# Path to the ffmpeg executable.
# If empty, the script will try to find it in FFMPEG_PATH environment variable,
# then the system's PATH.
ffmpeg_path =

# Interval in seconds to check if users are live.
check_interval = 60

# Directory where recordings should be saved. Usernames will be subdirectories.
output_directory = recordings

# Path to the file containing the list of Twitch usernames.
users_file = users.txt

# Twitch API credentials.
# It's recommended to use environment variables (TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET)
# or be prompted if these are left blank, rather than storing sensitive data in this file.
# However, for ease of private use, they can be specified here.
# If client_id and client_secret are empty here, the script will try to load them
# from credentials.json (legacy) or prompt the user.
client_id =
client_secret =

# Preferred stream quality. Examples: best, 1080p60, 720p, 480p, worst
# If the desired quality is not available, streamlink will try to find the next best available.
stream_quality = best

# Output file naming convention. You can use placeholders:
# {username} - Twitch username
# {timestamp} - Recording start time (YYYY-MM-DD-HH-MM-SS)
# {title} - Stream title (sanitized for filename safety)
# Example: {timestamp}_{username}_{title}.mp4
filename_format = {timestamp}_{username}_{title}.mp4

# Optional command to run after a recording finishes.
# Use {filepath} for the full path to the video file and {username} for the streamer's name.
# Example for compressing a video (requires ffmpeg in PATH or ffmpeg_path set):
# post_processing_command = ffmpeg -i "{filepath}" -c:v libx264 -preset medium -crf 23 -c:a aac -b:a 128k "{filepath}_compressed.mp4"
# Example for a simple echo command:
# post_processing_command = echo "Finished recording {username} to {filepath}"
post_processing_command =

# Log level for console and file output.
# Available levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
log_level = INFO

# Log file name.
log_file = recorder.log

# Quiet mode for console output. If true, only WARNING, ERROR, CRITICAL messages
# will be shown on the console. File logging is unaffected.
quiet_mode = false
```

### Configuration Options Details

*   **`ffmpeg_path`**: Full path to the `ffmpeg` executable or the directory containing it. If empty, the script checks the `FFMPEG_PATH` environment variable, then the system's PATH.
*   **`check_interval`**: How often (in seconds) the script checks if users are live. Default: `60`.
*   **`output_directory`**: Base directory for recordings. Subdirectories are created per username. Default: `recordings`.
*   **`users_file`**: Path to your user list file. Default: `users.txt`.
*   **`client_id` & `client_secret`**: Your Twitch API credentials. See "Twitch API Credentials" section below for loading order and security.
*   **`stream_quality`**: Preferred recording quality (e.g., `best`, `1080p60`, `720p`). Streamlink falls back if the specified quality isn't available. Default: `best`.
*   **`filename_format`**: Template for output filenames.
    *   `{timestamp}`: Recording start time (YYYY-MM-DD-HH-MM-SS).
    *   `{username}`: Twitch username.
    *   `{title}`: Stream title (sanitized by removing/replacing illegal characters and limiting length).
    *   Default: `{timestamp}_{username}_{title}.mp4`.
*   **`post_processing_command`**: Optional command executed after a recording finishes.
    *   Placeholders: `{filepath}` (full path to video), `{username}`.
    *   Executed in a shell with a 5-minute timeout. Output is logged.
*   **`log_level`**: Controls logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default: `INFO`.
*   **`log_file`**: Name of the log file. Default: `recorder.log`.
*   **`quiet_mode`**: If `true`, suppresses INFO and DEBUG messages from the console (stdout). File logging remains as per `log_level`. Default: `false`.

### User List File

Usernames to monitor are listed in a text file, specified by the `users_file` option in `config.ini` (default is `users.txt`). Usernames should be separated by commas.
Example: `streamer1,anotherstreamer,user_number_3`

If the file is not found or is empty when the script runs, you will be prompted to enter usernames in the console.

### Twitch API Credentials

Valid Twitch API credentials (Client ID and Client Secret) are required to check stream statuses. You can obtain these from the [Twitch Developer Portal](https://dev.twitch.tv/console) by registering an application (type "Chat Bot" is usually sufficient).

The script loads credentials in the following order:
1.  **`config.ini`**: If `client_id` and `client_secret` are provided in the `[TwitchRecorder]` section.
2.  **`credentials.json` (Legacy)**: If not found in `config.ini`, the script checks for a `credentials.json` file in the same directory. This is for backward compatibility.
    ```json
    {
      "client_id": "YOUR_TWITCH_CLIENT_ID",
      "client_secret": "YOUR_TWITCH_CLIENT_SECRET"
    }
    ```
    An example `credentials_example.json` is provided; you can rename and edit it.
3.  **User Prompt**: If credentials are not found or are invalid through the above methods, the script will prompt you to enter them. Credentials entered via prompt are saved to `credentials.json` for future use (unless they were initially loaded and failed from `config.ini`).

**Security Note**: It is generally recommended to **not** store sensitive credentials directly in shared configuration files. Using the prompt or environment variables (not yet directly supported but can be used with external tools to populate `config.ini`) is more secure for shared environments. If you store credentials in `config.ini` or `credentials.json`, ensure these files are protected. **The provided `.gitignore` file is set up to ignore `config.ini` and `credentials.json` by default to help prevent accidental commits of sensitive data.**

## Running the Recorder

1.  **Prerequisites**: Ensure Python 3 and FFmpeg are installed and accessible.
2.  **Configuration**:
    *   Run the script once to generate a default `config.ini` if it doesn't exist.
    *   Edit `config.ini` to set your preferences, especially `client_id`, `client_secret` (or prepare to be prompted), and `users_file`.
    *   Prepare your user list file (e.g., `users.txt`).
3.  **Navigate**: Open your terminal or command prompt and go to the directory where `recorder.py` is located.
4.  **Execute**: Run the script using:
    ```bash
    python recorder.py
    ```
    or, if you need to specify Python 3:
    ```bash
    python3 recorder.py
    ```
5.  **First Run**: If credentials are not configured, you'll be prompted to enter them. If your user list file is empty or not found, you'll be prompted for usernames.

The script will then display startup information (logged configuration) and begin monitoring.

## Logging

TwitchRecorder provides detailed logging to help you understand its activity and troubleshoot issues:

*   **Console Output**: Real-time feedback on operations like user checks, recording starts/stops, and errors.
    *   The verbosity is controlled by `log_level` in `config.ini`.
    *   If `quiet_mode = true` in `config.ini`, INFO and DEBUG messages are suppressed from the console, but still written to the log file.
*   **Log File**: All log messages (regardless of `quiet_mode`) are saved to a file specified by `log_file` in `config.ini` (default: `recorder.log`).
    *   This file automatically rotates when it reaches approximately 5MB, keeping up to 3 backup log files (e.g., `recorder.log.1`, `recorder.log.2`).
    *   The log file is crucial for diagnosing problems if the script doesn't behave as expected.

## Error Handling and Re-authentication

*   **Specific Errors**: The script logs detailed error messages for common issues:
    *   Twitch API errors (e.g., 401 Unauthorized, 403 Forbidden for credentials; 429 Too Many Requests for rate limits).
    *   Streamlink errors (e.g., no plugin found, stream quality unavailable).
    *   FFmpeg errors (e.g., executable not found, issues during recording).
*   **Token Re-authentication**: If the Twitch API access token expires or becomes invalid (usually indicated by a 401 error), the script will attempt to re-acquire a token using the configured credentials. If this fails, it may re-prompt for credentials. This process has a limited number of retries per session.
*   **Post-Processing**: Output from post-processing commands (stdout and stderr) is logged, along with success or failure status.

## Troubleshooting

*   **"FFmpeg not found"**:
    *   Ensure FFmpeg is installed correctly.
    *   Verify that the directory containing `ffmpeg` (or `ffmpeg.exe`) is in your system's PATH.
    *   Alternatively, set the `FFMPEG_PATH` environment variable to the directory containing FFmpeg, or the full path to the executable.
    *   As a last resort, set the `ffmpeg_path` option in `config.ini` to the full path of the FFmpeg executable or its containing directory.

*   **"Invalid Twitch Credentials" / "Authentication Failed" / 401/403 Errors**:
    *   Double-check your `client_id` and `client_secret` in `config.ini` or `credentials.json`.
    *   Ensure they are copied correctly from the Twitch Developer Portal.
    *   Consider regenerating your client secret if problems persist.

*   **"Rate Limited by Twitch API" / 429 Errors**:
    *   The script is making too many requests to the Twitch API. Increase the `check_interval` in `config.ini` (e.g., to `120` seconds or more).

*   **Recording not starting for a user**:
    *   Check `recorder.log` for detailed error messages from Streamlink or FFmpeg.
    *   The user might not actually be live, or the stream quality specified might be unavailable (though Streamlink usually falls back).
    *   Ensure the output directory is writable.

*   **Post-processing command not working**:
    *   Check `recorder.log` for the exact command executed and any stdout/stderr output.
    *   Ensure the command works correctly when run manually in your terminal.
    *   Verify paths (especially `{filepath}`) and quoting if your paths contain spaces.
    *   Make sure any programs used in the command (like `ffmpeg` for compression) are in your system's PATH or specified with their full path.

This comprehensive README should cover all aspects of the script.The `README.md` has been successfully updated with detailed information about all features, configuration options, logging, error handling, and troubleshooting.
This fulfills the subtask requirements.

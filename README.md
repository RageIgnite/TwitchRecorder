# TwitchRecorder

TwitchRecorder is a program written in Python. It scans a list of Twitch usernames periodically and records their streams using Streamlink and FFmpeg when they go live. Usernames are typically read from a `users.txt` file. Recordings are saved as MP4 files.

## Prerequisites

Before running TwitchRecorder, ensure you have the following installed:

*   **Python 3**: This script is written for Python 3. You can check your Python version by running:
    ```bash
    python --version
    # or
    python3 --version
    ```
    If you don't have Python 3, please download and install it from [python.org](https://www.python.org/downloads/).

*   **FFmpeg**: This is required for processing and saving the video streams.

### Installing FFmpeg

*   **Windows**:
    *   Download FFmpeg from the official site: [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html).
    *   Extract the downloaded archive (e.g., to `C:\ffmpeg`).
    *   You need to either add the `bin` directory (e.g., `C:\ffmpeg\bin`) to your system's PATH environment variable or set the `FFMPEG_PATH` environment variable (see "Configuring FFmpeg Path" below).

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
    *   Otherwise, download from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html) and ensure it's in your PATH or configure `FFMPEG_PATH`.

### Configuring FFmpeg Path

The script will first try to find `ffmpeg` if it's in your system's PATH. If `ffmpeg` is installed in a custom location and not added to your PATH, you need to tell the script where to find it using the `FFMPEG_PATH` environment variable.

You can set `FFMPEG_PATH` to point to:
1.  The **full path to the `ffmpeg` executable** itself (e.g., `C:\ffmpeg\bin\ffmpeg.exe` on Windows, or `/opt/ffmpeg/ffmpeg` on Linux/macOS).
2.  The **directory containing the `ffmpeg` executable** (e.g., `C:\ffmpeg\bin` on Windows, or `/opt/ffmpeg/bin` on Linux/macOS). The script will then look for `ffmpeg` or `ffmpeg.exe` within this directory.

## Configuration

### User List
Usernames to be monitored should be listed in a file named `users.txt` in the same directory as the script. The usernames should be separated by commas (e.g., `user1,user2,user3`). If `users.txt` is not found or is empty, the script will prompt you to enter usernames.

### Twitch API Credentials
The script will prompt you for your Twitch Client ID and Client Secret on the first run or if the stored credentials fail validation. These are required to interact with the Twitch API to check if users are live.
Once successfully entered, these credentials will be stored in a `credentials.json` file in the same directory as the script, so you don't have to enter them every time.

**Important**: Do not share your `credentials.json` file or commit it to version control if this is a public repository, as it contains sensitive information.

## Running the Recorder

1.  Ensure you have met all the prerequisites and configured `users.txt` (or prepare to enter them when prompted).
2.  Navigate to the directory where `recorder.py` is located.
3.  Run the script using:
    ```bash
    python recorder.py
    ```
    or, if you have multiple Python versions and need to be specific:
    ```bash
    python3 recorder.py
    ```
4.  On the first run, you will be prompted for your Twitch Client ID and Secret.
5.  You will also be prompted to enter the check interval (how often the script checks if users are live).

The script will then start monitoring the specified Twitch users and automatically record their streams when they go live. Recordings will be saved in subdirectories named after the Twitch username.

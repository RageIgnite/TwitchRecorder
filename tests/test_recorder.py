import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import sys
import configparser

# Add the parent directory to sys.path to allow direct import of recorder
# This is a common way to handle imports in test files when the test directory is a sibling
# to the module directory.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Now import the functions from recorder.py
# Note: recorder.py defines a logger. For tests, we might want to suppress or redirect it.
# For now, we'll let it be, but in more complex scenarios, logger mocking might be needed.
import recorder

class TestSanitizeFilename(unittest.TestCase):
    def test_valid_filenames(self):
        self.assertEqual(recorder.sanitize_filename("valid_name"), "valid_name")
        self.assertEqual(recorder.sanitize_filename("name_with_underscores"), "name_with_underscores")
        self.assertEqual(recorder.sanitize_filename("name-with-hyphens"), "name-with-hyphens")
        self.assertEqual(recorder.sanitize_filename("NameWithNumbers123"), "NameWithNumbers123")

    def test_problematic_characters(self):
        self.assertEqual(recorder.sanitize_filename("invalid/*:name?"), "invalid___name_")
        self.assertEqual(recorder.sanitize_filename("file/with/slashes"), "file_with_slashes")
        self.assertEqual(recorder.sanitize_filename("file\\with\\backslashes"), "file_with_backslashes")
        self.assertEqual(recorder.sanitize_filename("fi:le*co?lo\"ns<ta>rs|pipes"), "fi_le_co_lo_ns_ta_rs_pipes")
        self.assertEqual(recorder.sanitize_filename(" leading_space"), "leading_space")
        self.assertEqual(recorder.sanitize_filename("trailing_space "), "trailing_space")
        self.assertEqual(recorder.sanitize_filename("  multiple__underscores  "), "multiple_underscores")

    def test_empty_and_whitespace_string(self):
        self.assertEqual(recorder.sanitize_filename(""), "")
        self.assertEqual(recorder.sanitize_filename("   "), "") # Should become empty after strip
        self.assertEqual(recorder.sanitize_filename("__"), "") # Should become empty after strip

    def test_unicode_characters(self):
        self.assertEqual(recorder.sanitize_filename("你好世界"), "你好世界") # Assuming these are valid in filenames on the system
        self.assertEqual(recorder.sanitize_filename("résumé_file"), "résumé_file")
        self.assertEqual(recorder.sanitize_filename("文件名*?.txt"), "文件名__.txt")

    def test_truncation(self):
        long_string = "a" * 150
        self.assertEqual(recorder.sanitize_filename(long_string), "a" * 100)
        problematic_long = "/" * 5 + "a" * 120 + ":" * 5
        # Expected: "a" * 100 because leading/trailing '_' from sanitizing '/' and ':' are stripped.
        self.assertEqual(recorder.sanitize_filename(problematic_long), "a" * 100)


class TestFilenameFormatting(unittest.TestCase):
    # We will test the filename generation part of start_recording,
    # as format_filename isn't a separate function in the current recorder.py
    # We need a mock config object.

    def setUp(self):
        self.config = configparser.ConfigParser()
        self.config['TwitchRecorder'] = {
            'output_directory': recorder.DEFAULT_OUTPUT_DIRECTORY, # Use defaults from recorder
            'filename_format': recorder.DEFAULT_FILENAME_FORMAT,
            'stream_quality': recorder.DEFAULT_STREAM_QUALITY,
            'ffmpeg_path': recorder.DEFAULT_FFMPEG_PATH
        }
        # Suppress logger output during these specific tests if it becomes too noisy
        # For now, assume recorder.logger is accessible and can be temporarily disabled or level changed
        # For simplicity, we'll rely on the fact that start_recording uses logger.debug for some title messages
        # and logger.info for the final path, which can be checked with @patch('recorder.logger')

    @patch('recorder.os.makedirs') # Mock makedirs as we don't want to create dirs
    @patch('recorder.get_stream_url', return_value="http://mockstream.url/stream.m3u8")
    @patch('recorder.get_ffmpeg_path', return_value="/usr/bin/ffmpeg")
    @patch('recorder.subprocess.Popen') # Mock Popen to prevent actual recording
    def helper_test_start_recording_filename(self, filename_format, username, timestamp_str, stream_title, expected_filename_part, mock_popen, mock_ffmpeg, mock_streamurl, mock_makedirs):
        self.config['TwitchRecorder']['filename_format'] = filename_format
        
        # Mock datetime.now() within start_recording if it's called directly there
        # The current recorder.py calls datetime.now() inside start_recording
        mock_datetime = MagicMock()
        mock_datetime.now.return_value.strftime.return_value = timestamp_str
        
        with patch('recorder.datetime', mock_datetime):
            # The actual call to start_recording
            result_info = recorder.start_recording(username, self.config, stream_title=stream_title)

        self.assertIsNotNone(result_info, "start_recording should return process info")
        self.assertIn('output_path', result_info)
        
        # Check if the generated filename (part of output_path) is as expected
        # result_info['output_path'] will be like "recordings/username/expected_filename_part"
        generated_filename = os.path.basename(result_info['output_path'])
        self.assertEqual(generated_filename, expected_filename_part)


    def test_format_default_with_title(self):
        self.helper_test_start_recording_filename(
            filename_format="{timestamp}_{username}_{title}.mp4",
            username="testuser",
            timestamp_str="2023-01-01-12-00-00",
            stream_title="Cool Stream Title!*",
            expected_filename_part="2023-01-01-12-00-00_testuser_Cool_Stream_Title_.mp4"
        )

    def test_format_default_no_title_provided(self):
        self.helper_test_start_recording_filename(
            filename_format="{timestamp}_{username}_{title}.mp4",
            username="testuser",
            timestamp_str="2023-01-01-12-00-00",
            stream_title=None,
            expected_filename_part="2023-01-01-12-00-00_testuser.mp4" # {title} and preceding _ should be removed
        )
    
    def test_format_no_title_placeholder(self):
        self.helper_test_start_recording_filename(
            filename_format="{timestamp}_{username}.mp4",
            username="testuser",
            timestamp_str="2023-01-01-12-00-00",
            stream_title="A Title That Wont Be Used",
            expected_filename_part="2023-01-01-12-00-00_testuser.mp4"
        )

    def test_format_only_placeholders(self):
        self.helper_test_start_recording_filename(
            filename_format="{username}.mp4", # Timestamp and title not used in format
            username="testuser",
            timestamp_str="2023-01-01-12-00-00", # Will be generated but not used in filename
            stream_title="A Title",
            expected_filename_part="testuser.mp4"
        )

    def test_format_no_placeholders_at_all(self):
         self.helper_test_start_recording_filename(
            filename_format="my_recording.mp4",
            username="testuser",
            timestamp_str="2023-01-01-12-00-00",
            stream_title="A Title",
            expected_filename_part="my_recording.mp4"
        )
    
    def test_format_title_with_only_invalid_chars(self):
        self.helper_test_start_recording_filename(
            filename_format="{timestamp}_{username}_{title}.mp4",
            username="testuser",
            timestamp_str="2023-01-01-12-00-00",
            stream_title="*:/<>?", # All invalid, should be sanitized to empty or just underscores then stripped
            expected_filename_part="2023-01-01-12-00-00_testuser.mp4" # Title part becomes empty
        )


class TestLoadConfig(unittest.TestCase):
    @patch('recorder.os.path.exists')
    @patch('recorder.configparser.ConfigParser.read')
    def test_config_file_does_not_exist(self, mock_read, mock_exists):
        mock_exists.return_value = False
        config = recorder.load_config()
        mock_read.assert_not_called() # read should not be called if file doesn't exist
        self.assertEqual(config.get('TwitchRecorder', 'check_interval'), recorder.DEFAULT_CHECK_INTERVAL)
        self.assertEqual(config.get('TwitchRecorder', 'stream_quality'), recorder.DEFAULT_STREAM_QUALITY)

    @patch('recorder.os.path.exists', return_value=True)
    @patch('recorder.open', new_callable=mock_open, read_data="[TwitchRecorder]\ncheck_interval = 120\nstream_quality = 720p")
    def test_config_file_exists_with_values(self, mock_file_open, mock_exists):
        # We mock 'open' here because config.read() uses it.
        # The new_callable=mock_open is important for mocking file operations.
        config = recorder.load_config()
        self.assertEqual(config.get('TwitchRecorder', 'check_interval'), "120") # Note: configparser reads strings
        self.assertEqual(config.get('TwitchRecorder', 'stream_quality'), "720p")
        # Check a default value is still there
        self.assertEqual(config.get('TwitchRecorder', 'output_directory'), recorder.DEFAULT_OUTPUT_DIRECTORY)

    @patch('recorder.os.path.exists', return_value=True)
    @patch('recorder.open', new_callable=mock_open, read_data="") # Empty file
    def test_config_file_empty(self, mock_file_open, mock_exists):
        config = recorder.load_config()
        self.assertEqual(config.get('TwitchRecorder', 'check_interval'), recorder.DEFAULT_CHECK_INTERVAL)
        self.assertEqual(config.get('TwitchRecorder', 'stream_quality'), recorder.DEFAULT_STREAM_QUALITY)

    @patch('recorder.os.path.exists', return_value=True)
    @patch('recorder.open', new_callable=mock_open, read_data="[TwitchRecorder]\ncheck_interval = not_an_int")
    def test_config_invalid_value_type(self, mock_file_open, mock_exists):
        config = recorder.load_config()
        # configparser.getint will raise ValueError
        with self.assertRaises(ValueError):
            config.getint('TwitchRecorder', 'check_interval')
        # Check that other defaults are still loaded
        self.assertEqual(config.get('TwitchRecorder', 'output_directory'), recorder.DEFAULT_OUTPUT_DIRECTORY)


class TestGetFFmpegPath(unittest.TestCase):
    def setUp(self):
        self.mock_config = configparser.ConfigParser()
        self.mock_config['TwitchRecorder'] = {} # Ensure section exists

    @patch('recorder.shutil.which')
    @patch('recorder.os.path.isdir')
    @patch('recorder.os.path.isfile')
    @patch('recorder.os.environ.get')
    def test_ffmpeg_path_from_config_file(self, mock_env_get, mock_isfile, mock_isdir, mock_shutil_which):
        self.mock_config['TwitchRecorder']['ffmpeg_path'] = "/custom/path/to/ffmpeg"
        mock_isfile.return_value = True # Config path is a file
        
        path = recorder.get_ffmpeg_path(self.mock_config)
        self.assertEqual(path, "/custom/path/to/ffmpeg")
        mock_env_get.assert_not_called()
        mock_shutil_which.assert_not_called()

    @patch('recorder.shutil.which')
    @patch('recorder.os.path.isdir')
    @patch('recorder.os.path.isfile')
    @patch('recorder.os.environ.get')
    def test_ffmpeg_path_from_config_dir(self, mock_env_get, mock_isfile, mock_isdir, mock_shutil_which):
        self.mock_config['TwitchRecorder']['ffmpeg_path'] = "/custom/ffmpeg_dir"
        # First os.path.isfile for the dir itself is false, then os.path.isdir is true
        # Then os.path.isfile for the exe inside the dir is true
        mock_isfile.side_effect = [False, True] 
        mock_isdir.return_value = True
        
        with patch('recorder.os.name', 'posix'): # Mock os.name for predictable exe name
             path = recorder.get_ffmpeg_path(self.mock_config)
        self.assertEqual(path, "/custom/ffmpeg_dir/ffmpeg")

    @patch('recorder.shutil.which')
    @patch('recorder.os.path.isdir', return_value=False) # Config path is not a dir
    @patch('recorder.os.path.isfile', return_value=False) # Config path is not a file
    @patch('recorder.os.environ.get')
    def test_ffmpeg_path_from_env_var_file(self, mock_env_get, mock_isfile_config, mock_isdir_config, mock_shutil_which):
        self.mock_config['TwitchRecorder']['ffmpeg_path'] = "" # No config path
        mock_env_get.return_value = "/env/path/to/ffmpeg" # FFMPEG_PATH set
        # For the env var check
        mock_isfile.side_effect = [True] # FFMPEG_PATH is a file

        path = recorder.get_ffmpeg_path(self.mock_config)
        self.assertEqual(path, "/env/path/to/ffmpeg")
        mock_shutil_which.assert_not_called()

    @patch('recorder.shutil.which')
    @patch('recorder.os.path.isdir') # For config path and then for env path
    @patch('recorder.os.path.isfile') # For config path and then for env path (file and exe in dir)
    @patch('recorder.os.environ.get')
    def test_ffmpeg_path_from_env_var_dir(self, mock_env_get, mock_isfile, mock_isdir, mock_shutil_which):
        self.mock_config['TwitchRecorder']['ffmpeg_path'] = ""
        mock_env_get.return_value = "/env/ffmpeg_dir"
        # Config path checks:
        mock_isfile.side_effect = [False, # config path is not file
                                   False, # env path is not file (it's a dir)
                                   True]  # exe inside env path is file
        mock_isdir.side_effect = [False, # config path is not dir
                                  True]   # env path is dir
        
        with patch('recorder.os.name', 'nt'): # Test Windows exe name
            path = recorder.get_ffmpeg_path(self.mock_config)
        self.assertEqual(path, "/env/ffmpeg_dir\\ffmpeg.exe")


    @patch('recorder.shutil.which')
    @patch('recorder.os.path.isdir', return_value=False)
    @patch('recorder.os.path.isfile', return_value=False)
    @patch('recorder.os.environ.get', return_value=None) # No env var
    def test_ffmpeg_path_from_shutil_which(self, mock_env_get, mock_isfile, mock_isdir, mock_shutil_which):
        self.mock_config['TwitchRecorder']['ffmpeg_path'] = ""
        mock_shutil_which.return_value = "/usr/bin/ffmpeg_from_path"
        
        path = recorder.get_ffmpeg_path(self.mock_config)
        self.assertEqual(path, "/usr/bin/ffmpeg_from_path")

    @patch('recorder.shutil.which', return_value=None) # Not in PATH
    @patch('recorder.os.path.isdir', return_value=False)
    @patch('recorder.os.path.isfile', return_value=False)
    @patch('recorder.os.environ.get', return_value=None)
    def test_ffmpeg_not_found(self, mock_env_get, mock_isfile, mock_isdir, mock_shutil_which):
        self.mock_config['TwitchRecorder']['ffmpeg_path'] = ""
        path = recorder.get_ffmpeg_path(self.mock_config)
        self.assertIsNone(path)


class TestReadUsersFromFile(unittest.TestCase):
    def setUp(self):
        self.mock_config = configparser.ConfigParser()
        self.mock_config['TwitchRecorder'] = {'users_file': 'test_users.txt'}
        # Suppress logger output for these tests to avoid clutter if input() is called.
        # This can be done by patching 'recorder.logger' or setting its level high.
        # For simplicity, we are focusing on return values & mock interactions here.

    @patch('recorder.open', new_callable=mock_open, read_data="user1,user2, user3 ,user4")
    @patch('builtins.input') # Mock input in case of FileNotFoundError
    def test_read_valid_users_file(self, mock_input, mock_file):
        users = recorder.read_users_from_file('test_users.txt', self.mock_config)
        self.assertEqual(users, ["user1", "user2", "user3", "user4"])
        mock_input.assert_not_called()

    @patch('recorder.open', new_callable=mock_open, read_data="") # Empty file
    @patch('builtins.input', return_value="prompt_user1, prompt_user2")
    @patch('recorder.os.path.exists', return_value=False) # Assume config doesn't exist for save part
    def test_read_empty_users_file_prompts(self, mock_path_exists, mock_input, mock_file):
        with patch('builtins.open', mock_open()) as mock_save_open: # Mock open for saving
             users = recorder.read_users_from_file('test_users.txt', self.mock_config)
        self.assertEqual(users, ["prompt_user1", "prompt_user2"])
        mock_input.assert_any_call("Do you want to save these usernames to test_users.txt for future use? (y/n): ")

    @patch('recorder.open', side_effect=FileNotFoundError) # File does not exist
    @patch('builtins.input')
    @patch('recorder.os.path.exists', return_value=False)
    def test_read_users_file_not_found_prompts(self, mock_path_exists, mock_input_sequence, mock_open_filenotfound):
        # Simulate sequence of inputs: usernames, then 'y' to save
        mock_input_sequence.side_effect = ["userA, userB", "y"]
        with patch('builtins.open', mock_open()) as mock_save_open: # Mock open for saving
            users = recorder.read_users_from_file('test_users.txt', self.mock_config)
        
        self.assertEqual(users, ["userA", "userB"])
        mock_input_sequence.assert_any_call("'test_users.txt' not found or empty. Please enter Twitch usernames, separated by commas: ")
        mock_input_sequence.assert_any_call("Do you want to save these usernames to test_users.txt for future use? (y/n): ")
        # Check if saved
        mock_save_open.assert_called_with('test_users.txt', 'w')
        mock_save_open().write.assert_called_with('userA,userB')


    @patch('recorder.open', side_effect=FileNotFoundError)
    @patch('builtins.input', return_value="") # User provides empty input at prompt
    def test_read_users_empty_prompt_exits(self, mock_input, mock_open_fnf):
        with self.assertRaises(SystemExit):
            recorder.read_users_from_file('test_users.txt', self.mock_config)

    @patch('recorder.open', new_callable=mock_open, read_data=" user1 ,, user2, ")
    def test_read_users_with_spaces_and_empty_entries(self, mock_file):
        users = recorder.read_users_from_file('test_users.txt', self.mock_config)
        self.assertEqual(users, ["user1", "user2"])

if __name__ == '__main__':
    # Setup a basic logger for recorder module if it's not already configured by recorder.py itself
    # This is to prevent "No handlers could be found for logger 'TwitchRecorder'" if tests run standalone
    # and recorder.py's main() (which calls setup_logging) is not executed.
    if not recorder.logger.hasHandlers():
         recorder.setup_logging(quiet_mode=True) # Suppress console output from logger during tests

    unittest.main()

import wx
import requests
import os
import sys
import threading
import subprocess
import time # Optional: for a small delay before closing maybe
from packaging import version # <-- Import the version comparison tool

# --- configuration ---
# !! IMPORTANT: Replace placeholders below !!
REPO_OWNER = "your-github-username"  # Replace with your GitHub username
REPO_NAME = "your-repo-name"      # Replace with your repository name
APP_EXE_NAME = "YourApp.exe"      # Replace with your application's executable name
# Ensure version.txt on GitHub contains a valid version string like "v1.0.0", "v1.1.0-beta", etc.
VERSION_FILE_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest/download/version.txt"
DOWNLOAD_URL_TEMPLATE = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest/download/{APP_EXE_NAME}"
LOCAL_VERSION_FILE = "version.txt" # Local file storing the current version
DOWNLOAD_DESTINATION = APP_EXE_NAME # Download directly as the final exe name
# --- end configuration ---

class UpdateFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Update Any App", size=(400, 200),
                         style=wx.DEFAULT_FRAME_STYLE & ~(wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)) # Non-resizable

        self.panel = wx.Panel(self)
        self.v_sizer = wx.BoxSizer(wx.VERTICAL)

        self.status_label = wx.StaticText(self.panel, label="Initializing...")
        self.v_sizer.Add(self.status_label, 0, wx.ALL | wx.EXPAND, 15)

        # Progress Bar
        self.progress_bar = wx.Gauge(self.panel, range=100, style=wx.GA_HORIZONTAL)
        self.v_sizer.Add(self.progress_bar, 0, wx.ALL | wx.EXPAND, 15)
        self.progress_bar.Hide() # Hide initially

        self.panel.SetSizer(self.v_sizer)
        self.Center()
        self.Show()

        self.update_thread = threading.Thread(target=self.run_update_check)
        self.update_thread.daemon = True # Allows app to exit even if thread is running
        self.update_thread.start()

    def update_status(self, message):
        """Safely update the status label from any thread."""
        # Use CallAfter to ensure UI updates happen on the main thread
        wx.CallAfter(self.status_label.SetLabel, message)
        wx.CallAfter(self.panel.Layout) # Refresh layout

    def update_progress(self, value):
        """Safely update the progress bar from any thread."""
        def do_update():
            if not self.progress_bar.IsShown():
                self.progress_bar.Show()
                self.panel.Layout()
            self.progress_bar.SetValue(value)
        wx.CallAfter(do_update)

    def show_message_dialog(self, message, title, style):
        """Safely show a message dialog from any thread."""
        # Use CallAfter to ensure dialogs are shown from the main thread
        wx.CallAfter(wx.MessageBox, message, title, style | wx.ICON_INFORMATION | wx.CENTER, self)

    def get_remote_version(self):
        """Fetches the remote version string."""
        self.update_status("📡 Contacting update server...")
        try:
            # Add headers to potentially avoid caching issues
            headers = {'Cache-Control': 'no-cache', 'Pragma': 'no-cache'}
            response = requests.get(VERSION_FILE_URL, timeout=15, headers=headers)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            remote_ver_str = response.text.strip()
            print(f"Raw remote version string: '{remote_ver_str}'")
            # Basic validation - ensure it's not empty
            if not remote_ver_str:
                 print("Error: Remote version file is empty.")
                 self.update_status("Error: Invalid version info from server.")
                 return None
            return remote_ver_str
        except requests.exceptions.Timeout:
            print("Error fetching remote version: Timeout")
            self.update_status("Error: Connection timed out.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching remote version: {e}")
            self.update_status(f"Error checking version: {e}")
            return None # Indicate error

    def get_local_version(self):
        """Reads the local version string."""
        # Default to a very low version if file doesn't exist or is invalid
        default_version = "v0.0.0"
        if os.path.exists(LOCAL_VERSION_FILE):
            try:
                with open(LOCAL_VERSION_FILE, "r") as f:
                    local_ver_str = f.read().strip()
                    print(f"Raw local version string: '{local_ver_str}'")
                    # Basic validation - ensure it's not empty before returning
                    if local_ver_str:
                        return local_ver_str
                    else:
                        print("Warning: Local version file is empty, using default.")
                        return default_version
            except IOError as e:
                print(f"Error reading local version file: {e}")
                self.update_status("Error reading local version.")
                return default_version # Treat as no version found if read fails
        return default_version # Default if file doesn't exist

    def save_local_version(self, version_str):
        """Saves the version string locally."""
        try:
            with open(LOCAL_VERSION_FILE, "w") as f:
                f.write(version_str)
            print(f"Saved local version: {version_str}")
        except IOError as e:
            print(f"Error writing local version file: {e}")
            self.update_status("Error saving new version.")
            # Inform user, but maybe don't halt everything?
            self.show_message_dialog(
                f"Update applied, but failed to save the new version ({version_str}) locally.\n"
                "The updater might run again next time.\n"
                f"Error: {e}",
                "Version Save Warning", wx.OK | wx.ICON_WARNING)


    def download_update(self, remote_version_str):
        """Downloads the update file and updates progress."""
        self.update_progress(0) # Reset progress bar
        try:
            # Add headers to potentially avoid caching issues
            headers = {'Cache-Control': 'no-cache', 'Pragma': 'no-cache'}
            download_url = DOWNLOAD_URL_TEMPLATE # Use the template directly
            print(f"Attempting download from: {download_url}")
            response = requests.get(download_url, stream=True, timeout=60, headers=headers) # Increased timeout
            response.raise_for_status()

            total_size = response.headers.get('content-length')
            bytes_downloaded = 0
            temp_download_path = DOWNLOAD_DESTINATION + ".download" # Download to temp file first

            # Ensure old temp file (if exists) is removed
            if os.path.exists(temp_download_path):
                try:
                    os.remove(temp_download_path)
                except OSError as e:
                     print(f"Warning: Could not remove existing temp file {temp_download_path}: {e}")
                     # This might not be fatal, proceed with caution

            print(f"Downloading to temporary file: {temp_download_path}")
            with open(temp_download_path, "wb") as f:
                if total_size is None: # No content length header
                    self.update_progress(50) # Indicate indeterminate progress
                    f.write(response.content)
                    self.update_progress(100)
                    print("Download complete (no size header).")
                else:
                    total_size = int(total_size)
                    if total_size == 0:
                        print("Warning: Content-Length is 0.")
                        # Handle appropriately - maybe it's an error?
                        self.update_status("Error: Empty file received from server.")
                        self.show_message_dialog("The update file downloaded from the server was empty.", "Download Error", wx.OK | wx.ICON_ERROR)
                        wx.CallAfter(self.Close)
                        return False

                    chunk_size = 8192 # Download in 8KB chunks
                    for data in response.iter_content(chunk_size=chunk_size):
                        f.write(data)
                        bytes_downloaded += len(data)
                        progress = int((bytes_downloaded / total_size) * 100)
                        self.update_progress(progress)
                    print(f"Download complete. Bytes downloaded: {bytes_downloaded}")

            # --- Atomic Rename ---
            # Rename temp file to final destination only after successful download
            # This prevents using a partially downloaded file if the updater crashes
            try:
                # Remove the original file first (if it exists)
                 if os.path.exists(DOWNLOAD_DESTINATION):
                     os.remove(DOWNLOAD_DESTINATION)
                     print(f"Removed existing file: {DOWNLOAD_DESTINATION}")
                 # Rename the downloaded temp file
                 os.rename(temp_download_path, DOWNLOAD_DESTINATION)
                 print(f"Renamed {temp_download_path} to {DOWNLOAD_DESTINATION}")
                 self.update_progress(100) # Ensure progress shows 100%
                 return True # Indicate success

            except OSError as e:
                 print(f"Error replacing old file with downloaded update: {e}")
                 self.update_status(f"Error finalizing update: {e}")
                 self.progress_bar.Hide()
                 self.show_message_dialog(f"Downloaded update successfully, but failed to replace the existing application.\nPlease check permissions or close the running application.\nError: {e}", "Update Finalization Error", wx.OK | wx.ICON_ERROR)
                 # Clean up the temp file if rename failed
                 if os.path.exists(temp_download_path):
                     try:
                         os.remove(temp_download_path)
                     except OSError:
                         pass # Ignore error during cleanup
                 wx.CallAfter(self.Close)
                 return False

        except requests.exceptions.RequestException as e:
            print(f"Error downloading update: {e}")
            self.update_status(f"Error download: {e}")
            wx.CallAfter(self.progress_bar.Hide) # Hide progress bar on error
            self.show_message_dialog(f"Failed to download update.\nPlease check your connection or try again later.\nError: {e}", "Download Error", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.Close) # Close updater on download failure
            return False # Indicate failure
        except IOError as e:
            print(f"Error writing downloaded file: {e}")
            self.update_status(f"Error saving file: {e}")
            wx.CallAfter(self.progress_bar.Hide)
            self.show_message_dialog(f"Failed to save the downloaded update.\nPlease check disk space or permissions.\nError: {e}", "File Error", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.Close) # Close updater on file write failure
            return False # Indicate failure


    def launch_app_and_close(self):
        """Launches the downloaded application and closes the updater."""
        exe_path = os.path.abspath(DOWNLOAD_DESTINATION)
        print(f"Attempting to launch: {exe_path}")

        if not os.path.exists(exe_path):
             print("Error: Application file not found after update!")
             self.show_message_dialog(f"Update seemed successful, but the application file '{APP_EXE_NAME}' could not be found to launch.", "Launch Error", wx.OK | wx.ICON_ERROR)
             wx.CallAfter(self.Close) # Use CallAfter for consistency
             return

        try:
            # Use start command on Windows to detach the process
            if sys.platform == "win32":
                 subprocess.Popen(f'start "" "{exe_path}"', shell=True)
            else: # For Linux/macOS (adjust if needed)
                 subprocess.Popen([exe_path]) # Might need permissions `chmod +x`
            print("Application launch command issued.")
            # Add a small delay before closing updater to ensure the new process starts
            time.sleep(1.0)
            wx.CallAfter(self.Close) # Close the updater window
        except OSError as e:
            print(f"Error launching application: {e}")
            self.show_message_dialog(f"Update complete, but failed to launch '{APP_EXE_NAME}'.\nPlease start it manually.\nError: {e}", "Launch Error", wx.OK | wx.ICON_WARNING)
            wx.CallAfter(self.Close) # Still close the updater


    def run_update_check(self):
        """The main logic run in the background thread."""
        self.update_status("🔎 Checking for updates...")
        # No artificial sleep here, let network dictate speed

        remote_version_str = self.get_remote_version()
        if remote_version_str is None:
            # Error message already shown by get_remote_version via update_status
            self.show_message_dialog("Could not check for updates. Please check your internet connection or the update server status.", "Update Check Failed", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.Close)
            return

        local_version_str = self.get_local_version()

        try:
            # Use packaging.version to parse and compare versions
            remote_ver = version.parse(remote_version_str)
            local_ver = version.parse(local_version_str)

            print(f"Local version: {local_ver} ({local_version_str}), Remote version: {remote_ver} ({remote_version_str})")

            # --- Comparison Logic ---
            if remote_ver > local_ver:
                self.update_status(f"🚨 Update available! {local_ver} → {remote_ver}")
                time.sleep(1) # Pause to show message
                self.update_status(f"⬇️ Downloading update {remote_ver}...")

                if self.download_update(remote_version_str):
                    # Download was successful, now save the new version locally
                    self.save_local_version(remote_version_str)
                    self.update_status("✅ Update successful!")
                    # Show dialog, then launch and close
                    self.show_message_dialog(f"Update to version {remote_ver} is complete!\nThe application will now start.", "Update Successful!", wx.OK)
                    # Launching and closing needs to happen on the main thread after the dialog is dismissed
                    self.launch_app_and_close() # Use the dedicated method

                # If download_update returned False, error messages were handled internally, and the app likely closed.

            elif local_ver > remote_ver:
                # Local version is *newer* than remote version
                print("Local version is newer than remote. No update needed.")
                self.update_status(f"✨ Your version ({local_ver}) is newer than the latest release ({remote_ver}).")
                time.sleep(1.5) # Let user see the message
                self.show_message_dialog(
                    f"Your current version ({local_ver}) is newer than the latest available release ({remote_ver}).\n"
                    "No update is necessary.",
                    "Newer Version Detected", wx.OK | wx.ICON_INFORMATION
                )
                wx.CallAfter(self.Close) # Close the updater

            else: # local_ver == remote_ver
                print("Application is up to date.")
                self.update_status("✅ Application is up to date.")
                time.sleep(1.5) # Let user see the message
                self.show_message_dialog("Your application is already the latest version.", "Up To Date", wx.OK)
                # Decide if you want to launch the app even if up-to-date
                # self.launch_app_and_close() # Uncomment this line if you want to launch the app anyway
                wx.CallAfter(self.Close) # Close the updater if not launching


        except version.InvalidVersion as e:
            print(f"Error: Invalid version format encountered - Local: '{local_version_str}', Remote: '{remote_version_str}'. Error: {e}")
            self.update_status("Error: Could not compare versions.")
            self.show_message_dialog(
                "Could not compare application versions due to an invalid format.\n"
                f"Please check the {LOCAL_VERSION_FILE} file and the server's version file.\n"
                f"Error: {e}",
                "Version Error", wx.OK | wx.ICON_ERROR
            )
            wx.CallAfter(self.Close)
        except Exception as e:
            # Catch any other unexpected errors during the check
            print(f"An unexpected error occurred during update check: {e}")
            self.update_status("Error: An unexpected problem occurred.")
            self.show_message_dialog(f"An unexpected error occurred: {e}", "Updater Error", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.Close)


class UpdaterApp(wx.App):
    def OnInit(self):
        # Redirect stdout/stderr for debugging if running as a windowed app
        # sys.stdout = open("updater_stdout.log", "w")
        # sys.stderr = open("updater_stderr.log", "w")
        self.frame = UpdateFrame()
        return True

if __name__ == "__main__":
    print("Starting Updater GUI...")
    # Important: Make sure placeholder values (REPO_OWNER, etc.) are replaced above!
    if REPO_OWNER == "your-github-username" or REPO_NAME == "your-repo-name" or APP_EXE_NAME == "YourApp.exe":
         print("\n" + "="*60)
         print("!! ERROR: Please replace the placeholder values in the")
         print("          'configuration' section of updater.py before running!")
         print("          (REPO_OWNER, REPO_NAME, APP_EXE_NAME)")
         print("="*60 + "\n")
         # Optionally show a wx dialog even before the main frame
         app_precheck = wx.App(False)
         wx.MessageBox("Configuration Error:\nPlease set the REPO_OWNER, REPO_NAME, and APP_EXE_NAME variables inside the updater.py script.", "Configuration Needed", wx.OK | wx.ICON_ERROR | wx.CENTER)
         app_precheck.Destroy()
         sys.exit(1) # Exit if placeholders are still there

    app = UpdaterApp()
    app.MainLoop()
    print("Updater GUI finished.")

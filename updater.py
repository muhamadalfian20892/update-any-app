import wx
import requests
import os
import sys
import threading
import subprocess
import time # Optional: for a small delay before closing maybe

# --- configuration ---
# Change to your own repo
REPO_OWNER = "nama akun github lu"
REPO_NAME = "nama repo lu"
APP_EXE_NAME = "nama aplikasinya.exe"  # nama yang buat di jalanin sekaligus di download
VERSION_FILE_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest/download/version.txt"
DOWNLOAD_URL_TEMPLATE = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest/download/{APP_EXE_NAME}"
LOCAL_VERSION_FILE = "version.txt"
DOWNLOAD_DESTINATION = APP_EXE_NAME # Download directly as the final exe name
# --- end up ---

class UpdateFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Tunevia Updater", size=(400, 200),
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
        self.status_label.SetLabel(message)
        self.panel.Layout() # Refresh layout

    def update_progress(self, value):
        """Safely update the progress bar from any thread."""
        if not self.progress_bar.IsShown():
            self.progress_bar.Show()
            self.panel.Layout()
        self.progress_bar.SetValue(value)

    def show_message_dialog(self, message, title, style):
        """Safely show a message dialog from any thread."""
        wx.MessageBox(message, title, style | wx.ICON_INFORMATION | wx.CENTER, self)


    def get_remote_version(self):
        """Fetches the remote version string."""
        try:
            response = requests.get(VERSION_FILE_URL, timeout=10)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            return response.text.strip()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching remote version: {e}")
            wx.CallAfter(self.update_status, f"Error checking version: {e}")
            return None # Indicate error

    def get_local_version(self):
        """Reads the local version string."""
        if os.path.exists(LOCAL_VERSION_FILE):
            try:
                with open(LOCAL_VERSION_FILE, "r") as f:
                    return f.read().strip()
            except IOError as e:
                print(f"Error reading local version file: {e}")
                wx.CallAfter(self.update_status, "Error reading local version.")
                # Treat as no version found if read fails
                return "v0.0.0"
        return "v0.0.0" # Default if file doesn't exist

    def save_local_version(self, version):
        """Saves the version string locally."""
        try:
            with open(LOCAL_VERSION_FILE, "w") as f:
                f.write(version)
            print(f"Saved local version: {version}")
        except IOError as e:
            print(f"Error writing local version file: {e}")
            wx.CallAfter(self.update_status, "Error saving new version.")
            # ini problematik, update bisa tapi gak kesimpen.

    def download_update(self):
        """Downloads the update file and updates progress."""
        wx.CallAfter(self.update_progress, 0) # Reset progress bar
        try:
            response = requests.get(DOWNLOAD_URL_TEMPLATE, stream=True, timeout=30)
            response.raise_for_status()

            total_size = response.headers.get('content-length')
            bytes_downloaded = 0

            if os.path.exists(DOWNLOAD_DESTINATION):
                 try:
                     os.remove(DOWNLOAD_DESTINATION)
                 except OSError as e:
                     print(f"Could not remove existing file {DOWNLOAD_DESTINATION}: {e}")
                     # Decide if this is fatal or ignorable

            with open(DOWNLOAD_DESTINATION, "wb") as f:
                if total_size is None: # No content length header
                    wx.CallAfter(self.update_progress, 50) # Indeterminate? Or just show downloading
                    f.write(response.content)
                    wx.CallAfter(self.update_progress, 100)
                else:
                    total_size = int(total_size)
                    chunk_size = 8192 # Download in 8KB chunks
                    for data in response.iter_content(chunk_size=chunk_size):
                        f.write(data)
                        bytes_downloaded += len(data)
                        progress = int((bytes_downloaded / total_size) * 100)
                        wx.CallAfter(self.update_progress, progress)

            print("Download complete.")
            wx.CallAfter(self.update_progress, 100)
            return True # Indicate success

        except requests.exceptions.RequestException as e:
            print(f"Error downloading update: {e}")
            wx.CallAfter(self.update_status, f"Error download: {e}")
            wx.CallAfter(self.progress_bar.Hide) # Hide progress bar on error
            wx.CallAfter(self.show_message_dialog, f"Failed to download upddate.\nPlease check your connection or try again later.\nError: {e}", "Download Error", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.Close) # Close updater on download failure
            return False # Indicate failure
        except IOError as e:
            print(f"Error writing downloaded file: {e}")
            wx.CallAfter(self.update_status, f"Error saving file: {e}")
            wx.CallAfter(self.progress_bar.Hide)
            wx.CallAfter(self.show_message_dialog, f"Failed to save the downloaded update.\nPlease check disk space or permissions.\nError: {e}", "File Error", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.Close) # Close updater on file write failure
            return False # Indicate failure


    def launch_app_and_close(self):
        """Launches the downloaded application and closes the updater."""
        exe_path = os.path.abspath(DOWNLOAD_DESTINATION)
        print(f"Attempting to launch: {exe_path}")

        if not os.path.exists(exe_path):
             print("Error: Downloaded file not found!")
             self.show_message_dialog(f"Update downloaded, but the file '{APP_EXE_NAME}' could not be found to launch.", "Launch Error", wx.OK | wx.ICON_ERROR)
             self.Close()
             return

        try:
            subprocess.Popen([exe_path])
            print("Application launched.")
            self.Close() # Close the updater window
        except OSError as e:
            print(f"Error launching application: {e}")
            self.show_message_dialog(f"Update complete, but failed to launch '{APP_EXE_NAME}'.\nPlease start it manually.\nError: {e}", "Launch Error", wx.OK | wx.ICON_WARNING)
            self.Close() # Still close the updater


    def run_update_check(self):
        """The main logic run in the background thread."""
        wx.CallAfter(self.update_status, "🔎 Checking for updates...")
        time.sleep(0.5) # Small delay for visual effect

        remote_version = self.get_remote_version()
        if remote_version is None:
            # Error message already shown by get_remote_version via CallAfter
            wx.CallAfter(self.show_message_dialog, "Could not check for updates. Please check your internet connection.", "Update Check Failed", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(self.Close)
            return

        local_version = self.get_local_version()

        print(f"Local version: {local_version}, Remote version: {remote_version}")

        if remote_version != local_version:
            wx.CallAfter(self.update_status, f"🚨 Update available! {local_version} → {remote_version}")
            time.sleep(1) # Pause to show message
            wx.CallAfter(self.update_status, "⬇️ Downloading update...")

            if self.download_update():
                # Download was successful
                self.save_local_version(remote_version) # Save the new version *after* successful download
                wx.CallAfter(self.update_status, "✅ Update complete!")
                # Show dialog, then launch and close
                wx.CallAfter(self.show_message_dialog, f"Update to version {remote_version} is complete!\nThe application will now start.", "Update Successful!", wx.OK)
                # Launching and closing needs to happen on the main thread after the dialog is dismissed
                wx.CallAfter(self.launch_app_and_close)

            # If download_update returned False, error messages were handled internally, and the app might close.

        else:
            wx.CallAfter(self.update_status, "✅ Application is up to date.")
            time.sleep(1.5) # Let user see the message
            wx.CallAfter(self.show_message_dialog, "Your application is already the latest version.", "Up To Date", wx.OK)
            wx.CallAfter(self.Close)


class UpdaterApp(wx.App):
    def OnInit(self):
        self.frame = UpdateFrame()
        return True

if __name__ == "__main__":
    print("Starting Updater GUI...")
    app = UpdaterApp()
    app.MainLoop()
    print("Updater GUI finished.")
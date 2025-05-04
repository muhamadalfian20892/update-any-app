# Update Any App

A straightforward GUI updater for Windows applications that checks for new versions hosted on GitHub Releases.

---

## Features

*   Automatic update checking against the `latest` GitHub Release.
*   Compares a local `version.txt` file with the one in the release assets.
*   Downloads the new application executable if an update is available.
*   Simple GUI built with wxPython showing status and download progress.
*   Launches the updated application automatically after a successful download.
*   Basic error handling for network and file operations.

---

## Requirements

*   Python 3.x
*   wxPython library (`pip install wxPython`)
*   requests library (`pip install requests`)
*   A GitHub repository configured to host releases.

---

## How It Works

1.  The updater reads the `LOCAL_VERSION_FILE` (default: `version.txt`) in its directory to determine the current version. If the file doesn't exist, it assumes version `"v0.0.0"`.
2.  It fetches the `version.txt` file from the assets of the `latest` release in the specified GitHub repository.
3.  The local and remote versions are compared.
4.  If the remote version is newer:
    *   The updater downloads the application executable (specified by `APP_EXE_NAME`) from the assets of the `latest` release.
    *   The downloaded executable replaces the existing one (specified by `DOWNLOAD_DESTINATION`).
    *   The new version string is saved to the local `version.txt`.
    *   A success message is shown.
    *   The newly downloaded application executable is launched.
5.  If the local version is the same or newer, or if an error occurs, appropriate messages are displayed, and the updater closes.
6.  A simple GUI provides feedback throughout the process.

---

## Setup

### 1. Configure `updater.py`

At the top of `updater.py`, modify the configuration constants:

```python
# --- configuration ---
# Change to your own repo
REPO_OWNER = "your-github-username"  # CHANGE THIS
REPO_NAME = "your-repo-name"         # CHANGE THIS
APP_EXE_NAME = "YourApp.exe"         # CHANGE THIS - Name of your main app executable
# --- URLs are generated automatically based on the above ---
VERSION_FILE_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest/download/version.txt"
DOWNLOAD_URL_TEMPLATE = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest/download/{APP_EXE_NAME}"
# --- Local file configuration ---
LOCAL_VERSION_FILE = "version.txt"
DOWNLOAD_DESTINATION = APP_EXE_NAME # Usually keep this the same as APP_EXE_NAME
# --- end up ---
```

*   `REPO_OWNER`: Your GitHub username or organization name.
*   `REPO_NAME`: The name of the repository containing your application releases.
*   `APP_EXE_NAME`: The exact filename of your main application's executable (e.g., `MyCoolApp.exe`). This file *must* be present in your GitHub Release assets.

### 2. Prepare Your GitHub Repository and Releases

*   You need a public (or private, if you handle authentication, which this script *doesn't*) GitHub repository.
*   Use the GitHub Releases feature to publish new versions of your application.
*   **Crucially:** For *every* release you want the updater to recognize, you **must** upload two specific files as release assets:
    *   `version.txt`: A plain text file containing only the version string for that release (e.g., `v1.0.0`, `v1.1.2`, `v2.0-beta`). This string will be compared against the local `version.txt`.
    *   Your Application Executable: The compiled `.exe` file of your main application, named *exactly* as specified in the `APP_EXE_NAME` configuration variable (e.g., `YourApp.exe`).
*   The updater specifically targets the release tagged as `latest`. Make sure you mark your most recent stable release as the "latest release" on GitHub.

### 3. Compile the Updater (Recommended)

It's highly recommended to compile `updater.py` into an executable (`.exe`) for easier distribution and execution. You can use tools like PyInstaller or Nuitka.

Example using PyInstaller:

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name TuneviaUpdater updater.py
```

*   `--onefile`: Creates a single executable file.
*   `--noconsole`: Prevents a console window from appearing when the GUI runs.
*   `--name TuneviaUpdater`: Sets the output filename (e.g., `TuneviaUpdater.exe`).

### 4. Place the Updater and Initial Files

Place the compiled updater executable (e.g., `TuneviaUpdater.exe`) in the same directory as your main application executable (`YourApp.exe`).

Your application directory should initially look something like this:

```
/YourAppFolder/
    TuneviaUpdater.exe   (The compiled updater)
    YourApp.exe          (Your main application, matching APP_EXE_NAME)
    version.txt          (Optional but recommended: Contains the version of YourApp.exe)
```

*   If `version.txt` is not present on the first run, the updater will assume version `"v0.0.0"` and will likely attempt to download the `latest` release if one exists.
*   It's good practice to ship your application with a `version.txt` matching the version of `YourApp.exe`.

---

## Running the Updater

1.  Users simply run the compiled updater executable (e.g., `TuneviaUpdater.exe`).
2.  It will check for updates based on your configuration.
3.  If an update is found, it will download and replace `YourApp.exe` and update `version.txt`.
4.  It will then attempt to launch the new `YourApp.exe`.
5.  If no update is needed, it will display a message and close.

---

## Example GitHub Release Structure

For a release (e.g., `v1.1.0`) marked as `latest`:

**Release v1.1.0**
*(Description...)*

**Assets:**
*   `YourApp.exe`      (Size: 15.2 MB)
*   `version.txt`      (Size: 6 Bytes) <- *Content: "v1.1.0"*
*   Source code (zip)
*   Source code (tar.gz)

---

## Best Practices

*   Always compile the updater script to `.exe` using the `--noconsole` (PyInstaller) or equivalent `--windowed` option for a better user experience.
*   Use consistent versioning (e.g., Semantic Versioning like `v1.0.0`, `v1.1.0`). Ensure the `version.txt` content exactly matches the version you want to represent.
*   Double-check that the required assets (`version.txt` and the correctly named `APP_EXE_NAME`) are uploaded to **every** GitHub Release intended for updates.
*   Ensure your `latest` release on GitHub always points to the version you want users to update to.
*   Consider code signing your updater and application executables to improve trust and reduce warnings from Windows SmartScreen or antivirus software.

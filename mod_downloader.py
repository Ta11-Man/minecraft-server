import json
import os
import shutil
import requests
from urllib.parse import urlparse

# ================= CONFIGURATION =================
# Folder where mods will be saved
OUTPUT_FOLDER = "./downloads" 
UNMATCHED_SUBFOLDER = "./outdated-mods"

GAME_VERSION = "1.21.10" 

# Path to your json file
JSON_FILE_PATH = "/var/www/halste.ad/browser/assets/data.json"
# =================================================

def clean_output_folders():
    """Deletes the main folder and recreates it + the subfolder."""
    if os.path.exists(OUTPUT_FOLDER):
        print(f"--- Cleaning old files from {OUTPUT_FOLDER} ---")
        shutil.rmtree(OUTPUT_FOLDER)
    os.makedirs(OUTPUT_FOLDER)
    os.makedirs(UNMATCHED_SUBFOLDER)

def get_project_slug(url):
    """Extracts the project slug from a modrinth URL."""
    parsed = urlparse(url)
    path_parts = parsed.path.strip("/").split("/")
    if len(path_parts) >= 2:
        return path_parts[-1]
    return None

def get_mod_version(slug, loader, target_version=None):
    """
    Fetches mod version data.
    If target_version is provided, it asks for a strict match.
    If target_version is None, it grabs the absolute latest file.
    """
    api_url = f"https://api.modrinth.com/v2/project/{slug}/version"
    
    params = {
        "loaders": f'["{loader.lower()}"]'
    }
    
    # only add this filter if we are looking for a strict match
    if target_version:
        params["game_versions"] = f'["{target_version}"]'

    headers = {
        "User-Agent": "PythonScript/ModDownloader/1.2 (email@example.com)"
    }

    try:
        response = requests.get(api_url, params=params, headers=headers)
        response.raise_for_status()
        versions = response.json()
        
        if versions:
            return versions[0]['files'][0]
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"  [!] CRITICAL: The URL/Slug for '{slug}' does not exist on Modrinth.")
        else:
            print(f"  [!] API Error for {slug}: {e}")
    except Exception as e:
        print(f"  [!] Error for {slug}: {e}")
    
    return None

def download_file(url, filename, folder):
    """Downloads the file to the specified folder."""
    filepath = os.path.join(folder, filename)
    
    print(f"  [v] Downloading {filename}...")
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
    except Exception as e:
        print(f"  [!] Failed to download {filename}: {e}")

def main():
    if not GAME_VERSION:
        print("Error: You must specify a GAME_VERSION.")
        return

    # uncomment if wanting a fresh start folder
    # clean_output_folders()

    # load JSON
    try:
        with open(JSON_FILE_PATH, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find {JSON_FILE_PATH}")
        return

    # determine Loader
    loader = "fabric"
    for setting in data.get("serverSettings", []):
        if setting["label"] == "Type":
            loader = setting["value"]
            break
            
    print(f"Targeting: {loader} on Minecraft {GAME_VERSION}")
    print("--- Starting Download Process ---")
    
    wrong_version = []
    missing_completely = []

    for category in data.get("modCategories", []):
        cat_title = category.get("title", "Unknown Category")
        print(f"\nProcessing Category: {cat_title}")
        
        for mod in category.get("mods", []):
            name = mod.get("name")
            url = mod.get("url")
            
            if not url or "modrinth.com" not in url:
                continue

            slug = get_project_slug(url)
            if not slug:
                print(f"  [x] Could not parse URL for {name}")
                continue

            # 1. try Strict Version Match
            file_data = get_mod_version(slug, loader, target_version=GAME_VERSION)
            
            if file_data:
                # success: found exact version
                download_file(file_data['url'], file_data['filename'], OUTPUT_FOLDER)
            else:
                # 2. strict match failed, try fetching ANY version
                print(f"  [?] No strict match for '{name}'. Checking for any version...")
                file_data = get_mod_version(slug, loader, target_version=None)

                if file_data:
                    print(f"      -> Found older/newer version. Saving to '{UNMATCHED_SUBFOLDER}'")
                    target_folder = UNMATCHED_SUBFOLDER
                    download_file(file_data['url'], file_data['filename'], target_folder)
                    wrong_version.append(name)
                else:
                    print(f"  [!] FAIL: No versions found for '{name}' at all.")
                    missing_completely.append(name)

    print("\n" + "="*40)
    print("Download Complete.")
    print(f"Check the '{UNMATCHED_SUBFOLDER}' folder for mods that didn't match version {GAME_VERSION}.")
    if wrong_version:
        print(f"\nThe following mods were not up to date and put in the '{UNMATCHED_SUBFOLDER}' folder:")
        for mod in wrong_version:
            print(f" - {mod}")

    print("\n" + "="*40)
    if missing_completely:
        print(f"\nThe following mods could not be downloaded at all (check URLs):")
        for mod in missing_completely:
            print(f" - {mod}")
    print("="*40)

if __name__ == "__main__":
    main()

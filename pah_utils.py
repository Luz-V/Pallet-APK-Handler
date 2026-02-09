import logging
import subprocess
import shutil
import hashlib
from pathlib import Path

DEBUG_FLAG = False


class PAHError(Exception):
    """Custom exception for PAH errors."""
    pass

def raise_error(msg: str):
    """Raise an error + log with the given message."""
    logging.error(msg)
    raise PAHError(msg)

def clean_tmp_dir(tmpdir: Path):
    """Ensure the tmpdir is empty by deleting and recreating it."""
    if tmpdir.exists():
        shutil.rmtree(tmpdir)
    tmpdir.mkdir(parents=True, exist_ok=True)

def check_adb_connection():
    """Check that at least one device is connected via ADB."""
    result = subprocess.run(
        ["adb", "devices"], capture_output=True, text=True
    )
    devices = [line for line in result.stdout.splitlines() if line.strip().endswith("device")]
    adb_connect = bool(devices)
    if not adb_connect:
        logging.debug("\nNo ADB device detected.")
    return adb_connect

def unzip_apks_to_tmpdir(file_path: Path, tmpdir: Path):
    """Unzip an .apks archive to a temporary directory using 7z."""
    tmpdir.mkdir(parents=True, exist_ok=True)
    process = subprocess.run(
        ["7z", "x", str(file_path), f"-o{tmpdir}", "-y"],
        capture_output=True, text=True)
    if process.stdout:
        logging.debug(f"[7z stdout] {process.stdout.strip()}")
    if process.stderr:
        logging.error(f"[7z stderr] {process.stderr.strip()}")
    return process.returncode == 0

def get_fast_apk_hash(apk_path: Path) -> str:
    """Calcule un hash rapide d'un APK pour identification.
    
    Utilise Blake2b (plus rapide que SHA-256) sur les premiers 64KB.
    
    Args:
        apk_path: Chemin vers le fichier APK
        
    Returns:
        str: Hash hexadécimal
    """
    try:
        hasher = hashlib.blake2b(digest_size=16)  # 128 bits = 32 chars hex
        
        with open(apk_path, 'rb') as f:
            # Lire seulement les premiers 64KB pour la performance
            data = f.read(65536)
            hasher.update(data)
        
        return hasher.hexdigest()
        
    except Exception as e:
        logging.error(f"Failed to hash {apk_path}: {e}")
        return ""

def is_package_installed(pkg: str, installed_list: list[str]) -> bool:
    """Check if pkg is in installed_list."""
    return pkg in installed_list

def create_output_dir(directory: Path):
    """Create the output directory if it doesn't exist."""
    directory.mkdir(parents=True, exist_ok=True)

def check_file(file_path: Path):
    """Ensure the given file exists."""
    file_exist = file_path.is_file()
    if not file_exist:
        if DEBUG_FLAG:
            logging.warning(f'"{file_path}" not found.')
        else:
            raise_error(f'"{file_path}" not found.')
    return file_exist

import logging
import subprocess
import shutil
import time
import hashlib
from pathlib import Path
from typing import Dict, Tuple

DEBUG_FLAG = False

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


# === Base functions ===
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

# === Package lists related functions ===

def extract_user_packages_list() -> list[str]:
    """Return a list of all user-installed packages on the connected device."""
    adb_connect = check_adb_connection()
    if adb_connect:
        result = subprocess.run(
            ["adb", "shell", "pm", "list", "packages", "-3"],
            capture_output=True, text=True
        )
        lines = result.stdout.strip().splitlines()
        return [line.split(":")[1] for line in lines]
    else:
        logging.warning("Skipping android install listing.")
        return []

def extract_packages_labels_version(apk_installer_path: Path) -> list[tuple[str, str, str]]:
    """
    use miniapp on the android device to extract a list of installed packages.
    Return a tuple list : (package_name, version_code, label).
    """
    pkg_name = "com.pah.miniapp"
    remote_path = f"/storage/emulated/0/Android/data/{pkg_name}/files/miniapp_package_list.txt"
    local_file = Path(__file__).parent / "extracted_apks" / "android_extracted_list.txt"
    results = []

    installed = extract_user_packages_list()
    if not installed:
        logging.warning("No user-installed packages detected on device.")
        return results

    # Vérifie si miniapp est installée
    if pkg_name not in installed:
        try:
            subprocess.run(["adb", "install", str(apk_installer_path)], check=True)
            logging.info("miniapp installed successfully.")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to install miniapp: {e}") from e

    # Lancer l’activité principale
    try:
        subprocess.run([
            "adb", "shell", "monkey", "-p", pkg_name,
            "-c", "android.intent.category.LAUNCHER", "1"
        ], capture_output=True, check=True)
        logging.info("miniapp launched.")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to launch miniapp: {e}") from e

    # Wait before reading list file
    max_attempts = 10
    delay = 2.0
    for attempt in range(max_attempts):
        time.sleep(delay)
        res = subprocess.run(["adb", "shell", "ls", remote_path],
                             capture_output=True, text=True)
        logging.debug(f"[shell ls] {res.stdout.strip()}")
        if "No such file" not in res.stdout:
            break
        logging.debug(f"Waiting for file... ({attempt+1}/{max_attempts})")
    else:
        raise RuntimeError("Timeout (10s): miniapp_package_list.txt not found on device.")

    # Pull list file
    try:
        res2 = subprocess.run(["adb", "pull", remote_path, str(local_file)],
                             capture_output=True, check=True)
        logging.debug(f"[adb pull] {res2.stdout.strip()}")
        logging.info(f"Pulled file {local_file.name}")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to pull file: {e}") from e

    # Reading and parsing
    try:
        with local_file.open('r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split(None, 2)
                if len(parts) >= 2:
                    pkg = parts[0]
                    version = parts[1]
                    label = parts[2] if len(parts) > 2 else ""
                    results.append((pkg, version, label))
    except Exception as e:
        raise RuntimeError(f"Failed to parse pulled file: {e}") from e

    return results


def map_apk_files_to_packages(package_map, apk_dir: Path, files_to_hash: list[Path]) -> Dict[str, Tuple[str, str, str]]:
    """Map les fichiers APK vers les packages avec fallback hash.

    Args:
        package_map: Instance de PackageMap
        apk_dir: Répertoire contenant les APK
        files_to_hash: liste des fichiers qui nécessitent un hash

    Returns:
        Dict: {filename: (label, pkg, vcode)}
    """
    mapping = {}
    hash_to_filename = {}

    # Hasher uniquement les fichiers inconnus
    for apk_file in files_to_hash:
        file_hash = get_fast_apk_hash(apk_file)
        if file_hash:
            hash_to_filename[file_hash] = apk_file.name

    # Mapper tous les fichiers connus ou hashés
    for (pkg, vcode_int), info in package_map.get_all_packages().items():
        if not info.local:
            continue

        vcode_str = str(vcode_int)
        expected_filename = f"{pkg}_{vcode_str}.apk"

        # 1) Nom exact sauvegardé
        if info.file_name and (apk_dir / info.file_name).exists():
            mapping[info.file_name] = (info.label, pkg, vcode_str)
            continue

        # 2) Nom attendu
        if (apk_dir / expected_filename).exists():
            mapping[expected_filename] = (info.label, pkg, vcode_str)
            continue

        # 3) Fallback hash
        if info.file_hash and info.file_hash in hash_to_filename:
            filename = hash_to_filename[info.file_hash]
            mapping[filename] = (info.label, pkg, vcode_str)
            logging.info(f"Found renamed APK: {filename} -> {pkg} v{vcode_str}")

    return mapping


# === Name, Label, VersionCode functions ===

def parse_aapt_output(aapt_output: str) -> tuple[str, str, str]:
    """
    Parse the output of 'aapt dump badging' to extract package name, version name, and label.
    Returns empty strings if not found.
    """
    package_name = ""
    version_code = ""
    label = ""
    for line in aapt_output.splitlines():
        if line.startswith("package:"):
            parts = line.split()
            for part in parts:
                if part.startswith("name=") and not package_name:
                    package_name = part.split("=")[1].strip("'")
                elif part.startswith("versionCode=") and not version_code:
                    version_code = part.split("=")[1].strip("'")
        elif "application-label:" in line and not label:
            label = line.split(":", 1)[1].strip().strip("'")
    return package_name, version_code, label

def extract_pkg_version_label(apk_file: Path, tmpdir: Path) -> tuple[str, str, str]:
    """
    Extract package name, version code, and application label from a local .apk or .apks file.
    For .apks, unzip and analyze all .apk inside.
    Args:
    - apk_file: Path to the .apk or .apks file.
    - tmpdir: Path to a temporary directory for extraction.
    Returns:
    - Tuple of (package_name, version_code, label).
    Raises:
    - PAHError if extraction fails.
    """
    clean_tmp_dir(tmpdir)
    
    # Variables locales à cette fonction - réinitialisées à chaque appel
    package_name = ""
    version_code = ""
    label = ""

    if apk_file.suffix == ".apk":
        result = subprocess.run(
            ["aapt", "dump", "badging", str(apk_file)],
            capture_output=True, text=True, check=True
        )
        aapt_output = result.stdout
        package_name, version_code, label = parse_aapt_output(aapt_output)

    elif apk_file.suffix == ".apks":
        unzip_apks_to_tmpdir(apk_file, tmpdir)
        apk_files_inside = list(tmpdir.glob("*.apk"))
        if not apk_files_inside:
            clean_tmp_dir(tmpdir)
            raise_error("No .apk found inside the .apks archive.")

        # Loop on all extracted APKs to find info (stop early if all found)
        for apk_inside in apk_files_inside:
            result = subprocess.run(
                ["aapt", "dump", "badging", str(apk_inside)],
                capture_output=True, text=True
            )
            aapt_output = result.stdout
            p, v, l = parse_aapt_output(aapt_output)
            if not package_name and p:
                package_name = p
            if not version_code and v:
                version_code = v
            if not label and l:
                label = l
            if package_name and version_code and label:
                break
    else:
        raise_error(f"Unsupported file type: {apk_file.suffix}")
    clean_tmp_dir(tmpdir)
    if not package_name:
        raise_error("Failed to extract package name.")
    if not version_code:
        logging.warning(f"VersionCode not found in {apk_file}. Version check disabled.")
    if not version_code:
        logging.warning(f"label not found in {apk_file}.")
    return package_name, version_code, label


# === APK Extraction related functions ===

def unzip_apks_to_tmpdir(file_path: Path, tmpdir: Path):
    """Unzip an .apks archive to a temporary directory using 7z."""
    tmpdir.mkdir(parents=True, exist_ok=True)
    process = subprocess.run(
        ["7z", "x", str(file_path), f"-o{tmpdir}", "-y"],
        capture_output=True,text=True)
    if process.stdout:
        logging.debug(f"[7z stdout] {process.stdout.strip()}")
    if process.stderr:
        logging.error(f"[7z stderr] {process.stderr.strip()}")
    return process.returncode == 0

def extract_single_apk(package: str, apk_path: str, out_dir: Path) -> Path:
    """Pull a single APK via adb and return (apk_file) path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{package}.apk"
    process = subprocess.run(["adb", "pull", apk_path, str(dst)],
               capture_output=True,text=True)
    # Single apk extraction
    if process.stdout:
        logging.debug(f"[adb pull stdout] {process.stdout.strip()}")
    if process.stderr:
        logging.error(f"[adb pull stderr] {process.stderr.strip()}")
    return dst if process.returncode == 0 else False

def extract_split_apks(package: str, apk_paths: list[str], out_dir: Path) -> Path:
    """Pull split APK, concatenate to .apks, and return (apks_file) path."""
    # Multiple APK pull
    out_dir.mkdir(parents=True, exist_ok=True)
    split_files = []
    for idx, path in enumerate(apk_paths, start=1):
        dst = out_dir / f"{package}_split{idx}.apk"
        process = subprocess.run(["adb", "pull", path, str(dst)],
                       capture_output=True,text=True)
        # APKs extraction
        if process.stdout:
            logging.debug(f"[adb pull stdout] {process.stdout.strip()}")
        if process.stderr:
            logging.error(f"[adb pull stderr] {process.stderr.strip()}")
        split_files.append(dst)
    # APKS Concatenation
    apks_dst = out_dir / f"{package}.apks"
    process = subprocess.run(["7z", "a", str(apks_dst)] + [str(f) for f in split_files],
                   capture_output=True,check=True)
    if process.stdout:
        logging.debug(f"[7z stdout] {process.stdout.strip()}")
    if process.stderr:
        logging.error(f"[7z stderr] {process.stderr.strip()}")
        if not DEBUG_FLAG:
            raise_error("APKS concatenation failed for package "+package)
    # cleanup splits
    for f in split_files:
        f.unlink()
    return apks_dst if apks_dst.is_file() else False

def extract_package(package: str, versioncode: str, out_dir: Path) -> str:
    """Extract APK or APKS from android via adb and return the apk_file path."""
    # get paths via adb
    result = subprocess.run([
        "adb", "shell", "pm", "path", package],
        capture_output=True, text=True, check=True)
    if result.stdout:
        logging.debug(f"[adb pm stdout] {result.stdout.strip()}")
    if result.stderr:
        logging.error(f"[adb pm stderr] {result.stderr.strip()}")
    package_file_name = package +"_"+ versioncode
    paths = [line.split(':')[1] for line in result.stdout.splitlines()]
    if len(paths) == 1:
        apk_dst = extract_single_apk(package_file_name, paths[0], out_dir)
    else:
        apk_dst = extract_split_apks(package_file_name, paths, out_dir)
    return str(apk_dst) if apk_dst.is_file() else False


# === APK Install/Uninstall ===

def is_package_installed(pkg: str, installed_list: list[str]) -> bool:
    """Check if pkg is in installed_list."""
    return pkg in installed_list

def install_package(file: Path, tmpdir: Path, down_flag) -> bool:
    """Install an .apk or .apks file via adb. Returns True on success."""
    try:
        if file.suffix == ".apk":
            if not down_flag :
                # Install or update
                process = subprocess.run(["adb", "install",str(file)],
                           capture_output=True,text=True)
            else:
                # Push + try downgrade with su
                push_cmd = subprocess.run(["adb", "push",str(file),"/data/local/tmp"],
                           capture_output=True,text=True)
                process = subprocess.run(["adb", "shell","su","-c","'pm install -r -d /data/local/tmp/"+str(file.name)+"'"],
                           capture_output=True,text=True)
            if process.stdout:
                logging.debug(f"[adb pm stdout]\n {process.stdout.strip()}")
            if process.stderr:
                raise_error(process.stderr.strip())
        elif file.suffix == ".apks":
            clean_tmp_dir(tmpdir)
            unzip_apks_to_tmpdir(file, tmpdir)
            apks_list = [str(p) for p in tmpdir.glob("*.apk")]
            if not down_flag :
                process = subprocess.run(["adb", "install-multiple"] + apks_list,
                           capture_output=True, text=True)
            else :
                # Push + try downgrade with
                push_cmd = subprocess.run(["adb", "push",str(file),"/data/local/tmp"],
                           capture_output=True,text=True)
                process = subprocess.run(
                    ["adb", "shell", "su", "-c", "'pm install-multiple -r -d /data/local/tmp/" + str(file.name) + "'"],
                    capture_output=True, text=True)
            if process.stdout:
                logging.debug(f"[adb pm stdout]\n {process.stdout.strip()}")
            if process.stderr:
                raise_error(process.stderr.strip())
            clean_tmp_dir(tmpdir)
        else:
            raise_error(f"Unsupported file type: {file}")
        return True
    except subprocess.CalledProcessError:
        return False

def uninstall_package(package_name: str) -> bool:
    """Uninstall an app via adb using its package name. Returns True on success."""
    # Warning : adb uninstall failure return exit code 0
    # => details are stored in stdout and not stderr
    try:
        process = subprocess.run(["adb", "uninstall", package_name],
                       capture_output=True, text=True)
        if process.stdout:
            if not "Success" in process.stdout.strip():
                raise_error(process.stdout.strip())
            else:
                logging.debug(f"[adb uninstall stdout] {process.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        raise_error(str(e))
        return False


# === NeoBackup related functions ===

def restore_package(pkg: str, save_dir: Path, installed_list: list[str], tmpdir: Path) -> None:
    """Process a package: install if needed, then restore backups."""
    print(f"{pkg}: Package Processing...")
    if is_package_installed(pkg, installed_list):
        print(f"{pkg}: already installed.")
    else:
        print(f"{pkg}: installing APK(s)…")
        apk_file = next(save_dir.glob("*.apk"), None) or next(save_dir.glob("*.apks"), None)
        if not apk_file or not install_package(apk_file, tmpdir, False):
            print(f"{pkg}: No APK found or installation failed, skipping.")
            return
    # restore data and external files
    print(f"{pkg}: Restoring data.tar.zst …")
    restore_backup_archive(save_dir / "data.tar.zst", f"/data/data/{pkg}", tmpdir)
    print(f"{pkg}: Restoring external_files.tar.zst …")
    restore_backup_archive(
        save_dir / "external_files.tar.zst",
        f"/storage/emulated/0/Android/data/{pkg}",
        tmpdir
    )
    print(f"{pkg}: Completed.\n")
def restore_backup_archive(archive: Path, target_path: str, tmpdir: Path) -> bool:
    """Restore a Neo Backup .tar.zst archive to the device."""
    if not archive.is_file():
        print(f"{archive.name}: not found, skipping")
    else:
        # decompress zst
        process = subprocess.run(["zstd", "-d", str(archive), "-o", str(tmpdir / "data.tar")],
                       capture_output=True,text=True)
        if process.stdout:
            logging.debug(f"[zstd stdout] {process.stdout.strip()}")
        if process.stderr:
            logging.error(f"[zstd stderr] {process.stderr.strip()}")
        # extract tar
        process = subprocess.run(["7z", "x", str(tmpdir / "data.tar"), f"-o{tmpdir}", "-y"],
                       capture_output=True,text=True)
        if process.stdout:
            logging.debug(f"[7z stdout] {process.stdout.strip()}")
        if process.stderr:
            logging.error(f"[7z stderr] {process.stderr.strip()}")

        (tmpdir / "data.tar").unlink()
        # push and copy
        # Simplication needed
        subprocess.run(["adb", "shell", "su", "-c", f"mkdir -p '/storage/emulated/0/neo_tmp/'"])
        subprocess.run(["adb", "push", str(tmpdir / "."), "/storage/emulated/0/neo_tmp/"])
        subprocess.run(["adb", "shell", "su", "-c", f"mkdir -p '{target_path}'"])
        subprocess.run(["adb", "shell", "su", "-c", f"cp -r /storage/emulated/0/neo_tmp/. '{target_path}'"])
        subprocess.run(["adb", "shell", "su", "-c", "rm -rf /storage/emulated/0/neo_tmp"])
        clean_tmp_dir(tmpdir)
    return True

## Deprecated functions
def extract_label_and_name(apk_file: Path, tmpdir: Path) -> tuple[str, str]:
    """Return (package, label) for .apk or .apks, raise on failure."""
    lbl = ""
    pkg = ""
    if apk_file.suffix == ".apk":
        lbl = extract_label_from_apk(apk_file)
        pkg = extract_package_name_from_apk(apk_file)
    elif apk_file.suffix == ".apks":
        lbl = extract_label_from_apks(apk_file, tmpdir)
        pkg = extract_package_name_from_apks(apk_file, tmpdir)
    else:
        raise_error("Unable to open package.")
    clean_tmp_dir(tmpdir)
    if not lbl or not pkg:
        raise_error("Cannot find the label or package name in APKS file.")
    return pkg, lbl
def extract_package_name(apk_file: Path, tmpdir: Path) -> str:
    """Extract package name from .apk or .apks."""
    if apk_file.suffix == ".apk":
        return extract_package_name_from_apk(apk_file)
    elif apk_file.suffix == ".apks":
        return extract_package_name_from_apks(apk_file, tmpdir)
    return ""
def extract_label(apk_file: Path, tmpdir: Path) -> str:
    """Extract label from .apk or .apks."""
    if apk_file.suffix == ".apk":
        return extract_label_from_apk(apk_file)
    elif apk_file.suffix == ".apks":
        return extract_label_from_apks(apk_file, tmpdir)
    return ""
def extract_label_from_apk(apk_file: Path) -> str:
    """Extract the application label from a single .apk archive using aapt."""
    result = subprocess.run(
        ["aapt", "dump", "badging", str(apk_file)],
        capture_output=True, text=True
    )
    for line in result.stdout.splitlines():
        if "application-label:" in line:
            return line.split(":", 1)[1].strip().strip("'")
    return ""
def extract_label_from_apks(apks_file: Path, tmpdir: Path) -> str:
    """Extract the application label from an .apks archive using aapt."""
    unzip_apks_to_tmpdir(apks_file, tmpdir)
    label = ""
    for apk in tmpdir.glob("*.apk"):
        lbl = extract_label_from_apk(apk)
        if lbl:
            label = lbl
            break
    clean_tmp_dir(tmpdir)
    return label
def extract_package_name_from_apk(apk_file: Path) -> str:
    """Extract the package name from a single .apk archive using aapt."""
    result = subprocess.run(
        ["aapt", "dump", "badging", str(apk_file)],
        capture_output=True, text=True
    )
    for line in result.stdout.splitlines():
        if line.startswith("package:"):
            # e.g. package: name='com.example.app' versionCode='1' versionName='1.0'
            parts = line.split()
            for part in parts:
                if part.startswith("name="):
                    return part.split("=")[1].strip("'")
    return ""
def extract_package_name_from_apks(apks_file: Path, tmpdir: Path) -> str:
    """Extract the package name from an .apks archive."""
    unzip_apks_to_tmpdir(apks_file, tmpdir)
    pkg = ""
    for apk in tmpdir.glob("*.apk"):
        name = extract_package_name_from_apk(apk)
        if name:
            pkg = name
            break
    clean_tmp_dir(tmpdir)
    return pkg
def uninstall_package_from_list(del_list: list[str], installed_list: list[str]) -> None:
    """Uninstall packages in both del_list (marked to uninstall) and installed_list (present on the device)."""
    for pkg in del_list:
        if pkg in installed_list:
            subprocess.run(["adb", "uninstall", pkg])
def uninstall_package_not_in_list(keep_list: list[str], installed_list: list[str]) -> None:
    """Uninstall packages not in keep_list from installed_list."""
    for pkg in installed_list:
        if pkg not in keep_list:
            subprocess.run(["adb", "uninstall", pkg])
def read_meta_info(meta_file: Path) -> tuple[str, bool]:
    """Read package_name and is_split_apk from a meta_v2.am.json file."""
    import json
    data = json.loads(meta_file.read_text())
    pkg = data.get("package_name", "")
    is_split = bool(data.get("is_split_apk", False))
    return pkg, is_split
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
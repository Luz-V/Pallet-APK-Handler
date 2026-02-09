import logging
import subprocess
import pah_utils as pahu

from pathlib import Path

# === NeoBackup related functions ===

def restore_package(pkg: str, save_dir: Path, installed_list: list[str], tmpdir: Path) -> None:
    """Process a package: install if needed, then restore backups."""
    print(f"{pkg}: Package Processing...")
    if pahu.is_package_installed(pkg, installed_list):
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
        pahu.clean_tmp_dir(tmpdir)
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
        pahu.raise_error("Unable to open package.")
    pahu.clean_tmp_dir(tmpdir)
    if not lbl or not pkg:
        pahu.raise_error("Cannot find the label or package name in APKS file.")
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
    pahu.unzip_apks_to_tmpdir(apks_file, tmpdir)
    label = ""
    for apk in tmpdir.glob("*.apk"):
        lbl = extract_label_from_apk(apk)
        if lbl:
            label = lbl
            break
    pahu.clean_tmp_dir(tmpdir)
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
    pahu.unzip_apks_to_tmpdir(apks_file, tmpdir)
    pkg = ""
    for apk in tmpdir.glob("*.apk"):
        name = extract_package_name_from_apk(apk)
        if name:
            pkg = name
            break
    pahu.clean_tmp_dir(tmpdir)
    return pkg
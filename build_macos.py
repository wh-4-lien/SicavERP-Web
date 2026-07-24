#!/usr/bin/env python3
"""
Build script for SicavERP macOS .app bundle.
Replicates flet pack's macOS pre-processing (sign + tar.gz Flet.app)
then calls PyInstaller with --collect-all flet_web.
"""
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid
from pathlib import Path

import flet_cli.__pyinstaller.config as hook_config
import PyInstaller.__main__

PROJECT_DIR = Path(__file__).parent

# Limpieza previa para evitar que PyInstaller use paths cacheados de builds anteriores
for _stale in ["SicavERP.spec", "build"]:
    _p = PROJECT_DIR / _stale
    if _p.is_dir(): shutil.rmtree(_p)
    elif _p.exists(): _p.unlink()

# Step 1: Copy flet-desktop to temp dir and pre-process Flet.app
from flet_cli.__pyinstaller.utils import get_flet_bin_path
src_dir = get_flet_bin_path()
assert src_dir and Path(src_dir).exists(), "flet-desktop not found"

temp_dir = str(Path(tempfile.gettempdir()) / str(uuid.uuid4()))
shutil.copytree(src_dir, temp_dir, symlinks=True)

app_path = os.path.join(temp_dir, "Flet.app")
tar_path = os.path.join(temp_dir, "flet-macos.tar.gz")

# Sign the full .app bundle recursively (--deep)
print("Signing Flet.app...")
result = subprocess.run(
    ["codesign", "-s", "-", "--force", "--all-architectures", "--timestamp", "--deep", app_path],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
)
print("codesign:", result.stdout)
if result.returncode:
    sys.exit(1)
print("Signed OK")

# Pack to tar.gz
print("Packing to flet-macos.tar.gz...")
with tarfile.open(tar_path, "w:gz") as tar:
    tar.add(app_path, arcname="Flet.app")

# Remove everything except the tar.gz so PyInstaller won't reclassify loose binaries
for entry in os.listdir(temp_dir):
    entry_path = os.path.join(temp_dir, entry)
    if entry_path == tar_path:
        continue
    if os.path.isdir(entry_path):
        shutil.rmtree(entry_path)
    else:
        os.remove(entry_path)

print(f"Temp dir contents: {os.listdir(temp_dir)}")

# Step 2: Tell flet's hook to use the pre-processed temp dir
hook_config.temp_bin_dir = temp_dir

# Step 3: Run PyInstaller
os.chdir(PROJECT_DIR)
pyi_args = [
    "main.py",
    "--noconfirm",
    "--noconsole",
    "--name", "SicavERP",
    "--icon", "assets/sicav.png",
    "--add-data", "assets:assets",
    "--add-data", "vistas:vistas",
    "--add-data", "core:core",
    "--add-data", "utils:utils",
    "--collect-all", "flet_web",
]

print("Running PyInstaller:", " ".join(pyi_args))
PyInstaller.__main__.run(pyi_args)

# Step 4: Cleanup temp dir
shutil.rmtree(temp_dir, ignore_errors=True)
print("Build complete. Check dist/SicavERP.app")

# Step 5: Create DMG
from version import VERSION
dmg_path = PROJECT_DIR / "dist" / f"SicavERP-v{VERSION}.dmg"
dmg_path.unlink(missing_ok=True)
result = subprocess.run([
    "hdiutil", "create",
    "-volname", "SicavERP",
    "-srcfolder", str(PROJECT_DIR / "dist" / "SicavERP.app"),
    "-ov", "-format", "UDZO",
    str(dmg_path),
], capture_output=True, text=True)
print(result.stdout, result.stderr)
print(f"DMG listo: {dmg_path}")

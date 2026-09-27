"""Build a Blender extension ZIP containing the complete add-on and workers."""
from pathlib import Path
import re
import zipfile

root = Path(__file__).resolve().parents[1]
version = re.search(r'^version = "([^"]+)"', (root / 'blender_manifest.toml').read_text(), re.M)[1]
target = root / 'dist' / f"vox-cleaner-{version}.zip"
target.parent.mkdir(exist_ok=True)
files = ('blender_manifest.toml', '__init__.py', 'vox_format.py',
         'batch.py', 'batch_worker.py', 'README.md')
with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
    for name in files:
        archive.write(root / name, name)
print(target)

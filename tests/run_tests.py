"""Run deterministic tests without opening cameras, microphones or windows."""
from pathlib import Path
import runpy
import sys

folder=Path(__file__).resolve().parent
sys.path.insert(0,str(folder.parent))
sys.path.insert(0,str(folder))
files=sorted(folder.glob('test_*.py'))
for path in files:
    print(f'\n--- {path.name} ---',flush=True)
    runpy.run_path(str(path),run_name='__main__')
print(f'\nAll {len(files)} test scripts passed.')

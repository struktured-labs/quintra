"""Load the PyBoy vignette mute hook when tests are run from scripts/.\n\n`python scripts/test_foo.py` puts this directory on sys.path first, so\nthe hook works even if CI or a caller forgot PYTHONPATH.\n"""
from pathlib import Path
import runpy

_hook = Path(__file__).resolve().parent / "quintra_sitecustomize" / "sitecustomize.py"
runpy.run_path(str(_hook), run_name="sitecustomize")

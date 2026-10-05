"""Run a reviewed source checkout against reports in the caller's directory."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from junit_collision_check.cli import main

raise SystemExit(main())

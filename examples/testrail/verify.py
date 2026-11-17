"""Run synthetic positive/negative controls; no TestRail server connection."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from junit_collision_check.core import inspect_reports
for name, expected in [('collision.xml', 'issues'), ('overrides.xml', 'clean')]:
    path = Path(__file__).with_name(name)
    with path.open('rb') as stream:
        report = inspect_reports([(name, stream)], identity='testrail')
    assert report['status'] == expected, report
    print(name, expected)

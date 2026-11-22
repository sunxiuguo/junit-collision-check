"""Run the synthetic matrix in a fresh child directory, with local Vitest installed."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from xml.etree import ElementTree as ET

root = Path(__file__).resolve().parent
checker = Path(sys.argv[1]).resolve()
vitest = root / "node_modules/vitest/vitest.mjs"
with tempfile.TemporaryDirectory(prefix="matrix-", dir=root) as tmp:
    work = Path(tmp)
    for path in ("matrix.test.mjs", "vitest.config.mjs"):
        shutil.copyfile(root / path, work / path)
    env = {k: v for k, v in os.environ.items()
           if k in ("PATH", "SYSTEMROOT", "WINDIR")}
    home = work / "home"
    home.mkdir()
    env.update(HOME=str(home), PYTHONDONTWRITEBYTECODE="1")
    def run(expected, cmd, cwd=work, **extra):
        result = subprocess.run(cmd, cwd=cwd, env={**env, **extra},
                                capture_output=True, text=True, check=False, timeout=30)
        if result.returncode != expected:
            raise RuntimeError(f"{cmd!r}: expected {expected}, got "
                               f"{result.returncode}\n{result.stdout}\n{result.stderr}")
        return result.stdout

    def producer(more, expected, report, **extra):
        return run(expected, ["node", str(vitest), *more, "--outputFile",
                              str(report)], **extra)

    def scan(expected, *files):
        message = run(expected, [sys.executable, "-m", "junit_collision_check",
                                 *map(str, files)], cwd=checker)
        assert ("CONFLICTING_OUTCOMES" in message) == (expected == 1), message

    def xml(files, classes, failed_class):
        cases = [case for path in files for case in ET.parse(work / path).iter("testcase")]
        assert sorted(case.attrib["classname"] for case in cases) == sorted(classes)
        assert {case.attrib["name"] for case in cases} == {"same matrix case"}
        assert [case.attrib["classname"] for case in cases
                if case.find("failure") is not None] == [failed_class]

    template = "{displayName}:{filename}"
    paths = ["a.xml", "b.xml"]
    for mode in ("default", "qualified"):
        files = [f"{mode}-{p}" for p in paths]
        for i, path in enumerate(files):
            producer(["run"], i, path, DEMO_FAIL=str(i), DEMO_PROJECT=f"env-{i}",
                     DEMO_CLASSNAME=(template if mode == "qualified" else ""))
        classes = (["matrix.test.mjs"] * 2 if mode == "default" else
                   ["env-0:matrix.test.mjs", "env-1:matrix.test.mjs"])
        xml(files, classes, classes[-1])
        scan(1 if mode == "default" else 0, *(work / path for path in files))
    for mode in ("labels", "projects"):
        (work / mode).mkdir()
        for i in range(2):
            producer(["run", "--reporter", "blob"], i, f"{mode}/{i}.json",
                     DEMO_FAIL=str(i), VITEST_BLOB_LABEL=f"env-{i}",
                     DEMO_PROJECT=(f"env-{i}" if mode == "projects" else "matrix"))
    for mode, suffix, fmt, expected, classes in (
        ("labels", "default", "", 1, ["matrix.test.mjs"] * 2),
        ("labels", "template", template, 1, ["matrix:matrix.test.mjs"] * 2),
        ("projects", "template", template, 0,
         ["env-0:matrix.test.mjs", "env-1:matrix.test.mjs"]),
    ):
        path = f"{mode}-{suffix}.xml"
        producer([f"--merge-reports={mode}"], 1, path, DEMO_CLASSNAME=fmt)
        xml([path], classes, classes[-1])
        scan(expected, work / path)
print("PASS: five Vitest JUnit populations; every intentional failure kept and merge exit preserved.")

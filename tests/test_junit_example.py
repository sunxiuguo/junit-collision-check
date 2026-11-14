"""The optional Java example must reject unknown artifacts before running them."""
import importlib.util
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class JUnitExampleSafetyTests(unittest.TestCase):
    def test_digest_mismatch_executes_nothing(self):
        path = Path(__file__).resolve().parents[1] / "examples/junit-parameterized-class/verify.py"
        spec = importlib.util.spec_from_file_location("junit_example_verifier", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            artifact = Path(temp) / "synthetic.jar"
            artifact.write_bytes(b"not a real jar")
            with patch.object(module, "run") as run:
                with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                    module.verify({"6.0.3": artifact, "6.1.3": artifact}, "java")
                run.assert_not_called()
            # Even a verified first artifact must wait for the second digest.
            with patch.object(module, "VERSIONS", {
                    "6.0.3": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                    "6.1.3": "incorrect-second-digest"}), patch.object(module, "run") as run:
                with self.assertRaisesRegex(ValueError, "JUnit 6.1.3: JAR SHA-256 mismatch"):
                    module.verify({"6.0.3": artifact, "6.1.3": artifact}, "java")
                run.assert_not_called()

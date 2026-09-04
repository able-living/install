import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "odoo-stack-launcher.sh"


class LauncherTest(unittest.TestCase):
    def render_launcher(self, root: Path, payload: bytes, *, root_user: bool) -> Path:
        payload_path = root / "payload.sh"
        payload_path.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        launcher = TEMPLATE.read_text(encoding="utf-8")
        launcher = launcher.replace(
            "__INSTALLER_URL__", "https://example.invalid/odoo-stack-install.sh"
        )
        launcher = launcher.replace("__INSTALLER_SHA256__", digest)
        launcher = launcher.replace("__INSTALLER_RELEASE__", "test-release")
        launcher_path = root / "odoo-stack"
        launcher_path.write_text(launcher, encoding="utf-8")
        launcher_path.chmod(0o755)

        bin_root = root / "bin"
        bin_root.mkdir()
        curl = bin_root / "curl"
        curl.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "output=''\n"
            "while [ \"$#\" -gt 0 ]; do\n"
            "  if [ \"$1\" = '--output' ]; then output=$2; shift 2; else shift; fi\n"
            "done\n"
            "cp \"$TEST_PAYLOAD\" \"$output\"\n",
            encoding="utf-8",
        )
        curl.chmod(0o755)
        fake_id = bin_root / "id"
        fake_id.write_text(
            f"#!/usr/bin/env bash\nprintf '%s\\n' '{0 if root_user else 1000}'\n",
            encoding="utf-8",
        )
        fake_id.chmod(0o755)
        sudo = bin_root / "sudo"
        sudo.write_text("#!/usr/bin/env bash\nexec \"$@\"\n", encoding="utf-8")
        sudo.chmod(0o755)
        return launcher_path

    def run_launcher(self, payload: bytes, *, root_user: bool = True):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            launcher = self.render_launcher(root, payload, root_user=root_user)
            environment = os.environ.copy()
            environment["PATH"] = f"{root / 'bin'}:{environment['PATH']}"
            environment["TEST_PAYLOAD"] = str(root / "payload.sh")
            return subprocess.run(
                [str(launcher), "--plan"],
                check=False,
                capture_output=True,
                env=environment,
                text=True,
            )

    def test_verified_payload_receives_arguments(self):
        result = self.run_launcher(b"#!/usr/bin/env bash\nprintf 'args=%s\\n' \"$*\"\n")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("args=--plan", result.stdout)
        self.assertIn("odoo-stack-install.sh: OK", result.stdout)

    def test_non_root_execution_uses_sudo_path(self):
        result = self.run_launcher(
            b"#!/usr/bin/env bash\nprintf 'elevated-args=%s\\n' \"$*\"\n",
            root_user=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("elevated-args=--plan", result.stdout)

    def test_tampered_payload_is_not_executed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            launcher = self.render_launcher(
                root, b"#!/usr/bin/env bash\necho should-not-run\n", root_user=True
            )
            (root / "payload.sh").write_bytes(b"#!/usr/bin/env bash\necho tampered\n")
            environment = os.environ.copy()
            environment["PATH"] = f"{root / 'bin'}:{environment['PATH']}"
            environment["TEST_PAYLOAD"] = str(root / "payload.sh")
            result = subprocess.run(
                [str(launcher)],
                check=False,
                capture_output=True,
                env=environment,
                text=True,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("tampered", result.stdout)


if __name__ == "__main__":
    unittest.main()

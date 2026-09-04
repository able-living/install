import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "odoo-stack"


class LauncherTest(unittest.TestCase):
    def test_help_does_not_require_network_or_privileges(self):
        result = subprocess.run(
            ("bash", str(LAUNCHER), "--help"),
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--installer-ref", result.stdout)

    def test_invalid_installer_ref_is_rejected_before_authentication(self):
        result = subprocess.run(
            ("bash", str(LAUNCHER), "--installer-ref", "feature/not-allowed"),
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("installer ref must be", result.stderr)

    def test_token_auth_downloads_exact_sha_and_forwards_arguments(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bin_root = root / "bin"
            bin_root.mkdir()
            fake_gh = bin_root / "gh"
            fake_gh.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    set -euo pipefail
                    printf '%s\n' "$*" >> "$GH_CALLS"
                    case "$*" in
                      "api user --jq .login") printf '%s\n' test-user ;;
                      "repo view able-living/odoo-stack --json viewerPermission --jq .viewerPermission")
                        printf '%s\n' READ
                        ;;
                      "api repos/able-living/odoo-stack/commits/main --jq .sha")
                        printf '%040d\n' 0
                        ;;
                      *"repos/able-living/odoo-stack/contents/deploy/bootstrap/install.sh?ref="*)
                        cat "$FAKE_INSTALLER"
                        ;;
                      *) exit 1 ;;
                    esac
                    """
                ),
                encoding="utf-8",
            )
            fake_gh.chmod(0o755)
            fake_id = bin_root / "id"
            fake_id.write_text(
                "#!/usr/bin/env bash\nprintf '1000\\n'\n", encoding="utf-8"
            )
            fake_id.chmod(0o755)
            fake_sudo = bin_root / "sudo"
            fake_sudo.write_text(
                "#!/usr/bin/env bash\nexit 99\n", encoding="utf-8"
            )
            fake_sudo.chmod(0o755)
            installer = root / "installer.sh"
            installer.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "test \"$1\" = '--github-token-file'\n"
                "test \"$(cat \"$2\")\" = 'test-token'\n"
                "shift 2\n"
                "printf 'installer-args=%s\\n' \"$*\"\n",
                encoding="utf-8",
            )
            calls = root / "gh-calls"
            environment = os.environ.copy()
            environment["PATH"] = f"{bin_root}:{environment['PATH']}"
            environment["FAKE_INSTALLER"] = str(installer)
            environment["GH_CALLS"] = str(calls)
            result = subprocess.run(
                ("bash", str(LAUNCHER), "--plan"),
                input="2\ntest-token\n",
                check=False,
                capture_output=True,
                env=environment,
                text=True,
            )
            call_log = calls.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("installer-args=--plan", result.stdout)
        self.assertIn("commits/main", call_log)
        self.assertIn(
            "?ref=0000000000000000000000000000000000000000", call_log
        )


if __name__ == "__main__":
    unittest.main()

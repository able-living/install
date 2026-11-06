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
                      "api repos/able-living/odoo-stack/contents/platform/deploy/bootstrap/install.sh?ref=0000000000000000000000000000000000000000 --jq .type")
                        printf 'gh: Not Found (HTTP 404)\n' >&2
                        exit 1
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


class InstallerPathTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.calls = self.root / "calls"
        self.new_installer = self.root / "new-installer.sh"
        self.legacy_installer = self.root / "legacy-installer.sh"
        self.new_installer.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "printf 'installer-source=new\\n'\n",
            encoding="utf-8",
        )
        self.legacy_installer.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "printf 'installer-source=legacy\\n'\n",
            encoding="utf-8",
        )
        fake_gh = self.bin / "gh"
        fake_gh.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -euo pipefail
                printf '%s\n' "$*" >> "$GH_CALLS"
                case "$*" in
                  "auth status --hostname github.com") exit 0 ;;
                  "auth token --hostname github.com") printf 'cached-token\n' ;;
                  "api user --jq .login") printf 'test-user\n' ;;
                  "repo view able-living/odoo-stack --json viewerPermission --jq .viewerPermission")
                    printf 'READ\n'
                    ;;
                  "api repos/able-living/odoo-stack/commits/main --jq .sha")
                    printf '%040d\n' 0
                    ;;
                  "api repos/able-living/odoo-stack/contents/platform/deploy/bootstrap/install.sh?ref=0000000000000000000000000000000000000000 --jq .type")
                    status="${NEW_PATH_STATUS:-200}"
                    case "$status" in
                      200) printf '%s\n' "${NEW_PATH_TYPE:-file}" ;;
                      404)
                        printf 'gh: Not Found (HTTP 404)\n' >&2
                        exit 1
                        ;;
                      *)
                        printf 'gh: request failed (HTTP %s)\n' "$status" >&2
                        exit 1
                        ;;
                    esac
                    ;;
                  *"repos/able-living/odoo-stack/contents/platform/deploy/bootstrap/install.sh?ref="*)
                    test "${NEW_DOWNLOAD_FAILURE:-0}" = 0 || {
                      printf 'gh: server error (HTTP 502)\n' >&2
                      exit 1
                    }
                    cat "$NEW_INSTALLER"
                    ;;
                  *"repos/able-living/odoo-stack/contents/deploy/bootstrap/install.sh?ref="*)
                    cat "$LEGACY_INSTALLER"
                    ;;
                  *) exit 90 ;;
                esac
                """
            ),
            encoding="utf-8",
        )
        fake_gh.chmod(0o755)
        self.environment = os.environ.copy()
        for name in ("GH_CONFIG_DIR", "GH_TOKEN", "GITHUB_TOKEN", "ABLE_LIVING_INSTALLER_REF"):
            self.environment.pop(name, None)
        self.environment.update({
            "PATH": f"{self.bin}:{self.environment['PATH']}",
            "GH_CALLS": str(self.calls),
            "NEW_INSTALLER": str(self.new_installer),
            "LEGACY_INSTALLER": str(self.legacy_installer),
        })

    def run_launcher(self):
        return subprocess.run(
            ("bash", str(LAUNCHER), "--plan"),
            env=self.environment,
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )

    def assert_single_sha_resolution(self):
        calls = self.calls.read_text(encoding="utf-8")
        self.assertEqual(calls.count("commits/main --jq .sha"), 1)
        self.assertNotIn("?ref=main", calls)
        return calls

    def test_new_path_is_preferred_when_present(self):
        result = self.run_launcher()
        calls = self.assert_single_sha_resolution()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("installer-source=new", result.stdout)
        self.assertIn("/contents/platform/deploy/bootstrap/install.sh?ref=", calls)
        self.assertNotIn("/contents/deploy/bootstrap/install.sh?ref=", calls)
        self.assertNotIn("trying the legacy path", result.stdout)

    def test_missing_new_path_falls_back_to_legacy_path_with_same_sha(self):
        self.environment["NEW_PATH_STATUS"] = "404"
        result = self.run_launcher()
        calls = self.assert_single_sha_resolution()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("trying the legacy path", result.stdout)
        self.assertIn("installer-source=legacy", result.stdout)
        self.assertIn("/contents/platform/deploy/bootstrap/install.sh?ref=", calls)
        self.assertIn("/contents/deploy/bootstrap/install.sh?ref=", calls)
        self.assertIn("?ref=" + "0" * 40, calls)

    def test_non_404_path_check_errors_do_not_fall_back(self):
        for status in ("401", "403", "429", "500", "502"):
            with self.subTest(status=status):
                self.calls.unlink(missing_ok=True)
                self.environment["NEW_PATH_STATUS"] = status
                result = self.run_launcher()
                calls = self.calls.read_text(encoding="utf-8")

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("could not inspect installer path", result.stderr)
                self.assertNotIn("/contents/deploy/bootstrap/install.sh?ref=", calls)
                self.assertNotIn("trying the legacy path", result.stdout)

    def test_new_path_download_failure_does_not_fall_back(self):
        self.environment["NEW_DOWNLOAD_FAILURE"] = "1"
        result = self.run_launcher()
        calls = self.calls.read_text(encoding="utf-8")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("could not download the private installer", result.stderr)
        self.assertNotIn("/contents/deploy/bootstrap/install.sh?ref=", calls)

    def test_empty_or_invalid_download_does_not_fall_back(self):
        for content in ("", "if then\n"):
            with self.subTest(content=content):
                self.calls.unlink(missing_ok=True)
                self.new_installer.write_text(content, encoding="utf-8")
                result = self.run_launcher()
                calls = self.calls.read_text(encoding="utf-8")

                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("/contents/deploy/bootstrap/install.sh?ref=", calls)
                if not content:
                    self.assertIn("downloaded installer is empty", result.stderr)
                else:
                    self.assertIn("not valid Bash", result.stderr)

    def test_non_file_path_type_does_not_fall_back(self):
        self.environment["NEW_PATH_TYPE"] = "dir"
        result = self.run_launcher()
        calls = self.calls.read_text(encoding="utf-8")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("installer path is not a file", result.stderr)
        self.assertNotIn("/contents/deploy/bootstrap/install.sh?ref=", calls)


class PersistentLoginTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.calls = self.root / "calls"
        self.config = self.root / "config" / "gh"
        self.installer = self.root / "installer.sh"
        self.installer.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'test "$1" = --github-token-file\n'
            'test -s "$2"\n'
            'printf "%s\\n" "$2" >> "$CREDENTIAL_PATHS"\n'
            'exit "${INSTALLER_EXIT:-0}"\n'
        )
        fake = self.bin / "gh"
        fake.write_text(textwrap.dedent("""\
            #!/usr/bin/env bash
            set -euo pipefail
            printf '%s\\n' "$*" >> "$GH_CALLS"
            config="${GH_CONFIG_DIR:-$XDG_CONFIG_HOME/gh}"
            case "$*" in
              "auth status --hostname github.com")
                test -f "$config/login" && test "$(cat "$config/login")" = valid
                ;;
              "auth login "*)
                test "${LOGIN_FAILURE:-0}" = 0
                install -d -m 0700 "$config"
                printf 'valid\\n' > "$config/login"
                chmod 600 "$config/login"
                ;;
              "auth token --hostname github.com") printf 'cached-token\\n' ;;
              "api user --jq .login") printf 'test-user\\n' ;;
              "repo view "*)
                test "${REPOSITORY_DENIED:-0}" = 0
                printf 'READ\\n'
                ;;
              "api repos/able-living/odoo-stack/commits/main --jq .sha")
                printf '%040d\\n' 0
                ;;
              "api repos/able-living/odoo-stack/contents/platform/deploy/bootstrap/install.sh?ref=0000000000000000000000000000000000000000 --jq .type")
                printf 'gh: Not Found (HTTP 404)\\n' >&2
                exit 1
                ;;
              *"/contents/deploy/bootstrap/install.sh?ref="*) cat "$FAKE_INSTALLER" ;;
              *) exit 90 ;;
            esac
        """))
        fake.chmod(0o755)
        self.environment = os.environ.copy()
        for name in ("GH_CONFIG_DIR", "GH_TOKEN", "GITHUB_TOKEN", "ABLE_LIVING_INSTALLER_REF"):
            self.environment.pop(name, None)
        self.environment.update({
            "PATH": f"{self.bin}:{self.environment['PATH']}",
            "XDG_CONFIG_HOME": str(self.root / "config"),
            "GH_CALLS": str(self.calls),
            "FAKE_INSTALLER": str(self.installer),
            "CREDENTIAL_PATHS": str(self.root / "credential-paths"),
        })

    def run_launcher(self, answers=""):
        return subprocess.run(
            ("bash", str(LAUNCHER), "--plan"), env=self.environment,
            input=answers, text=True, capture_output=True, check=False, timeout=10,
        )

    def assert_temporary_credentials_removed(self):
        for line in (self.root / "credential-paths").read_text().splitlines():
            self.assertFalse(Path(line).exists())
            self.assertFalse(Path(line).parent.exists())

    def test_login_survives_exit_and_second_run_skips_authentication(self):
        first = self.run_launcher("1\n")
        second = self.run_launcher()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertTrue((self.config / "login").exists())
        self.assertEqual(self.calls.read_text().count("auth login "), 1)
        self.assertIn("https://github.com/login/device", first.stdout)
        self.assertIn("直接复用", second.stdout)
        self.assertNotIn("请选择 GitHub 认证方式", second.stderr)
        self.assertNotIn("cached-token", first.stdout + first.stderr + second.stdout + second.stderr)
        self.assert_temporary_credentials_removed()

    def test_cancelled_installer_keeps_login_for_retry(self):
        self.environment["INSTALLER_EXIT"] = "130"
        first = self.run_launcher("1\n")
        self.assertEqual(first.returncode, 130)
        self.environment["INSTALLER_EXIT"] = "0"
        second = self.run_launcher()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.calls.read_text().count("auth login "), 1)
        self.assert_temporary_credentials_removed()

    def test_explicit_config_directory_is_respected(self):
        self.config = self.root / "custom-gh"
        self.environment["GH_CONFIG_DIR"] = str(self.config)
        first = self.run_launcher("1\n")
        second = self.run_launcher()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertTrue((self.config / "login").exists())
        self.assertFalse((self.root / "config").exists())

    def test_expired_login_requires_new_authentication(self):
        self.config.mkdir(parents=True)
        (self.config / "login").write_text("expired\n")
        result = self.run_launcher("1\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("auth login ", self.calls.read_text())

    def test_temporary_token_does_not_create_persistent_gh_login(self):
        result = self.run_launcher("2\ntemporary-token\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.config.exists())
        self.assertNotIn("auth login ", self.calls.read_text())
        self.assertNotIn("temporary-token", result.stdout + result.stderr + self.calls.read_text())
        self.assert_temporary_credentials_removed()

    def test_cached_login_still_requires_repository_access(self):
        self.assertEqual(self.run_launcher("1\n").returncode, 0)
        self.environment["REPOSITORY_DENIED"] = "1"
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot read", result.stderr)
        self.assertEqual(self.calls.read_text().count("auth login "), 1)

    def test_failed_login_does_not_download_installer(self):
        self.environment["LOGIN_FAILURE"] = "1"
        result = self.run_launcher("1\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("/contents/", self.calls.read_text())
        self.assertFalse(self.config.exists())

    def test_login_dependencies_include_git_and_do_not_force_plaintext(self):
        source = LAUNCHER.read_text()
        self.assertIn("command -v git", source)
        self.assertIn("ca-certificates gh git", source)
        self.assertNotIn("--insecure-storage", source)
        self.assertNotIn('GH_CONFIG_DIR="$TEMP_ROOT/gh"', source)


if __name__ == "__main__":
    unittest.main()

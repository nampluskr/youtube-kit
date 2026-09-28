import json
import os
import subprocess
import sys
import unittest

PYTHON_EXE = r"C:\winpython\WPy64-31180_cpu\python-3.11.8.amd64\python.exe"
YOUTUBE_KIT_CMD = "youtube-kit"
OUT_DIR = "outputs"


def run_cli(args, env_override=None):
    """Run youtube-kit CLI command and return (returncode, stdout, stderr)."""
    env = os.environ.copy()
    if env_override:
        env.update(env_override)
    cmd = [YOUTUBE_KIT_CMD] + args
    p = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        shell=True,
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()


class TestCLI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.makedirs(OUT_DIR, exist_ok=True)

    def test_00_path_executable(self):
        """Verify youtube-kit runs directly from PATH."""
        code, stdout, stderr = run_cli(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("usage: youtube-kit", stdout)

    # -------------------------------------------------------------
    # 1. info command exit codes (0, 1, 2, 3)
    # -------------------------------------------------------------
    def test_10_info_exit_code_0(self):
        code, stdout, stderr = run_cli(["info", "bWPXADZylm0", "-o", OUT_DIR, "--json"])
        self.assertEqual(code, 0)
        data = json.loads(stdout)
        self.assertEqual(data["id"], "bWPXADZylm0")

        # Verify stdout matches <id>.meta.json content
        meta_file = os.path.join(OUT_DIR, "bWPXADZylm0.meta.json")
        self.assertTrue(os.path.exists(meta_file))
        with open(meta_file, "r", encoding="utf-8") as f:
            file_data = json.load(f)
        self.assertEqual(data, file_data)
        # Verify no extraneous output on stdout (exactly 1 valid JSON line)
        self.assertEqual(len(stdout.splitlines()), 1)

    def test_11_info_non_json_table(self):
        code, stdout, stderr = run_cli(["info", "bWPXADZylm0", "-o", OUT_DIR])
        self.assertEqual(code, 0)
        self.assertIn("[Video Formats]", stdout)
        self.assertIn("[Audio Formats]", stdout)
        self.assertIn("[Subtitles]", stdout)

    def test_12_info_exit_code_1_network_error(self):
        # Break network by directing to unused proxy port
        env_break = {"HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9"}
        code, stdout, stderr = run_cli(["info", "bWPXADZylm0", "--json"], env_override=env_break)
        self.assertEqual(code, 1)
        err = json.loads(stdout)
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["error"], "YoutubeKitError")
        self.assertEqual(err["video_id"], "bWPXADZylm0")
        self.assertIn("https://www.youtube.com/watch?v=bWPXADZylm0", err["url"])
        self.assertIn("message", err)

    def test_13_info_exit_code_2_invalid_input(self):
        code, stdout, stderr = run_cli(["info", "abc", "--json"])
        self.assertEqual(code, 2)
        err = json.loads(stdout)
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["error"], "InvalidInput")
        self.assertIsNone(err["video_id"])
        self.assertIsNone(err["url"])
        self.assertIn("message", err)

    def test_14_info_exit_code_3_video_unavailable(self):
        # T-16 private video
        code, stdout, stderr = run_cli(["info", "Et9xVTOjgko", "--json"])
        self.assertEqual(code, 3)
        err = json.loads(stdout)
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["error"], "VideoUnavailable")
        self.assertEqual(err["video_id"], "Et9xVTOjgko")
        self.assertIn("message", err)

    # -------------------------------------------------------------
    # 2. video command exit codes (0, 1, 2, 3, 4, 5)
    # -------------------------------------------------------------
    def test_20_video_exit_code_0(self):
        code, stdout, stderr = run_cli([
            "video", "JyEsEcsCqzM", "--video", "299", "--audio", "140", "-o", OUT_DIR, "--json"
        ])
        self.assertEqual(code, 0)
        data = json.loads(stdout)
        self.assertIn(data["status"], ("ok", "reused"))
        self.assertEqual(data["video_id"], "JyEsEcsCqzM")
        self.assertTrue(os.path.exists(data["path"]))
        self.assertEqual(len(stdout.splitlines()), 1)

    def test_21_video_non_json(self):
        code, stdout, stderr = run_cli([
            "video", "JyEsEcsCqzM", "--video", "299", "--audio", "140", "-o", OUT_DIR
        ])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(stdout.strip()))
        self.assertEqual(len(stdout.splitlines()), 1)

    def test_22_video_exit_code_1_network_error(self):
        env_break = {"HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9"}
        code, stdout, stderr = run_cli([
            "video", "JyEsEcsCqzM", "--video", "299", "--audio", "140", "--json"
        ], env_override=env_break)
        self.assertEqual(code, 1)
        err = json.loads(stdout)
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["error"], "YoutubeKitError")

    def test_23_video_exit_code_2_invalid_input(self):
        # Invalid container name
        code, stdout, stderr = run_cli([
            "video", "JyEsEcsCqzM", "--video", "299", "--audio", "140", "--container", "avi", "--json"
        ])
        self.assertEqual(code, 2)
        err = json.loads(stdout)
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["error"], "InvalidInput")

    def test_24_video_exit_code_3_video_unavailable(self):
        code, stdout, stderr = run_cli([
            "video", "Et9xVTOjgko", "--video", "137", "--audio", "140", "--json"
        ])
        self.assertEqual(code, 3)
        err = json.loads(stdout)
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["error"], "VideoUnavailable")

    def test_25_video_exit_code_4_not_available(self):
        # Format ID not available
        code, stdout, stderr = run_cli([
            "video", "JyEsEcsCqzM", "--video", "99999", "--audio", "140", "--json"
        ])
        self.assertEqual(code, 4)
        err = json.loads(stdout)
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["error"], "NotAvailable")

        # Live video
        code_live, stdout_live, _ = run_cli([
            "video", "rFZHOHl-L8A", "--video", "137", "--audio", "140", "--json"
        ])
        self.assertEqual(code_live, 4)

    def test_26_video_exit_code_5_missing_dependency(self):
        # Run with PATH that does NOT include ffmpeg directory
        # Include python directory so python can run, but exclude ffmpeg
        python_dir = os.path.dirname(PYTHON_EXE)
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        clean_path = f"{python_dir};{python_dir}\\Scripts;{system_root};{system_root}\\System32;D:\\projects\\_bin"
        env_no_ffmpeg = {"PATH": clean_path}
        # Note: if ffmpeg is in chocolatey/winget/strawberry, clean_path excludes them
        code, stdout, stderr = run_cli([
            "video", "JyEsEcsCqzM", "--video", "299", "--audio", "140", "--json"
        ], env_override=env_no_ffmpeg)
        self.assertEqual(code, 5)
        err = json.loads(stdout)
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["error"], "MissingDependency")
        self.assertIn("ffmpeg", err["message"].lower())

    # -------------------------------------------------------------
    # 3. audio command exit codes (0, 1, 2, 3, 4)
    # -------------------------------------------------------------
    def test_30_audio_exit_code_0(self):
        code, stdout, stderr = run_cli([
            "audio", "JyEsEcsCqzM", "--audio", "140", "-o", OUT_DIR, "--json"
        ])
        self.assertEqual(code, 0)
        data = json.loads(stdout)
        self.assertIn(data["status"], ("ok", "reused"))
        self.assertEqual(data["video_id"], "JyEsEcsCqzM")
        self.assertTrue(os.path.exists(data["path"]))
        self.assertEqual(len(stdout.splitlines()), 1)

    def test_31_audio_non_json(self):
        code, stdout, stderr = run_cli([
            "audio", "JyEsEcsCqzM", "--audio", "140", "-o", OUT_DIR
        ])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(stdout.strip()))
        self.assertEqual(len(stdout.splitlines()), 1)

    def test_32_audio_exit_code_1_network_error(self):
        env_break = {"HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9"}
        code, stdout, stderr = run_cli([
            "audio", "JyEsEcsCqzM", "--audio", "140", "--json"
        ], env_override=env_break)
        self.assertEqual(code, 1)
        err = json.loads(stdout)
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["error"], "YoutubeKitError")

    def test_33_audio_exit_code_2_invalid_input(self):
        code, stdout, stderr = run_cli([
            "audio", "abc", "--audio", "140", "--json"
        ])
        self.assertEqual(code, 2)
        err = json.loads(stdout)
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["error"], "InvalidInput")

    def test_34_audio_exit_code_3_video_unavailable(self):
        code, stdout, stderr = run_cli([
            "audio", "Et9xVTOjgko", "--audio", "140", "--json"
        ])
        self.assertEqual(code, 3)
        err = json.loads(stdout)
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["error"], "VideoUnavailable")

    def test_35_audio_exit_code_4_not_available(self):
        code, stdout, stderr = run_cli([
            "audio", "JyEsEcsCqzM", "--audio", "99999", "--json"
        ])
        self.assertEqual(code, 4)
        err = json.loads(stdout)
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["error"], "NotAvailable")

    # -------------------------------------------------------------
    # 4. subtitle command exit codes (0, 1, 2, 3, 4)
    # -------------------------------------------------------------
    def test_40_subtitle_exit_code_0(self):
        code, stdout, stderr = run_cli([
            "subtitle", "bWPXADZylm0", "--track", "manual:ko", "-o", OUT_DIR, "--json"
        ])
        self.assertEqual(code, 0)
        data = json.loads(stdout)
        self.assertIn(data["status"], ("ok", "reused"))
        self.assertEqual(data["video_id"], "bWPXADZylm0")
        self.assertTrue(os.path.exists(data["path"]))
        self.assertEqual(len(stdout.splitlines()), 1)

    def test_41_subtitle_non_json(self):
        code, stdout, stderr = run_cli([
            "subtitle", "bWPXADZylm0", "--track", "manual:ko", "-o", OUT_DIR
        ])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(stdout.strip()))
        self.assertEqual(len(stdout.splitlines()), 1)

    def test_42_subtitle_exit_code_1_network_error(self):
        env_break = {"HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9"}
        code, stdout, stderr = run_cli([
            "subtitle", "bWPXADZylm0", "--track", "manual:ko", "--json"
        ], env_override=env_break)
        self.assertEqual(code, 1)
        err = json.loads(stdout)
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["error"], "YoutubeKitError")

    def test_43_subtitle_exit_code_2_invalid_input(self):
        code, stdout, stderr = run_cli([
            "subtitle", "bWPXADZylm0", "--track", "ko", "--json"
        ])
        self.assertEqual(code, 2)
        err = json.loads(stdout)
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["error"], "InvalidInput")

    def test_44_subtitle_exit_code_3_video_unavailable(self):
        code, stdout, stderr = run_cli([
            "subtitle", "Et9xVTOjgko", "--track", "manual:ko", "--json"
        ])
        self.assertEqual(code, 3)
        err = json.loads(stdout)
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["error"], "VideoUnavailable")

    def test_45_subtitle_exit_code_4_not_available(self):
        # T-3 has no manual subtitles
        code, stdout, stderr = run_cli([
            "subtitle", "VbD8ITrJ6lg", "--track", "manual:ko", "--json"
        ])
        self.assertEqual(code, 4)
        err = json.loads(stdout)
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["error"], "NotAvailable")


if __name__ == "__main__":
    unittest.main()

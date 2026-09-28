import json
import os
import subprocess
import unittest

YOUTUBE_KIT_CMD = "youtube-kit"
OUT_DIR = "outputs"


def run_cli(args):
    cmd = [YOUTUBE_KIT_CMD] + args
    p = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()


class TestBatchCLI(unittest.TestCase):

    def test_01_file_not_found(self):
        code, stdout, stderr = run_cli(["batch", "nonexistent.jsonl"])
        self.assertEqual(code, 2)

    def test_02_info_job_rejected(self):
        tmp_file = "test_info_job.jsonl"
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(json.dumps({"url": "bWPXADZylm0", "do": "info"}) + "\n")
        try:
            code, stdout, stderr = run_cli(["batch", tmp_file])
            self.assertEqual(code, 2)
        finally:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)

    def test_03_invalid_json_rejected(self):
        tmp_file = "test_invalid.jsonl"
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write("{not a valid json}\n")
        try:
            code, stdout, stderr = run_cli(["batch", tmp_file])
            self.assertEqual(code, 2)
        finally:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)

    def test_04_mixed_success_and_failure(self):
        tmp_file = "test_mixed.jsonl"
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(json.dumps({"url": "bWPXADZylm0", "do": "subtitle", "track": "manual:ko"}) + "\n")
            f.write(json.dumps({"url": "Et9xVTOjgko", "do": "subtitle", "track": "manual:ko"}) + "\n")
        try:
            code, stdout, stderr = run_cli(["batch", tmp_file, "-o", OUT_DIR, "--json"])
            self.assertEqual(code, 6)
            data = json.loads(stdout)
            self.assertEqual(len(data["items"]), 2)
            self.assertEqual(data["failed"], 1)
            self.assertEqual(data["ok"] + data["reused"], 1)
            self.assertEqual(data["items"][0]["video_id"], "bWPXADZylm0")
            self.assertIn(data["items"][0]["status"], ("ok", "reused"))
            self.assertEqual(data["items"][1]["video_id"], "Et9xVTOjgko")
            self.assertEqual(data["items"][1]["status"], "failed")
            self.assertEqual(data["items"][1]["error"], "VideoUnavailable")
        finally:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)

    def test_05_all_success(self):
        tmp_file = "test_ok.jsonl"
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(json.dumps({"url": "bWPXADZylm0", "do": "subtitle", "track": "manual:ko"}) + "\n")
        try:
            code, stdout, stderr = run_cli(["batch", tmp_file, "-o", OUT_DIR, "--json"])
            self.assertEqual(code, 0)
            data = json.loads(stdout)
            self.assertEqual(data["failed"], 0)
            self.assertEqual(data["ok"] + data["reused"], 1)
        finally:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)

    def test_06_non_json_output(self):
        tmp_file = "test_summary.jsonl"
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(json.dumps({"url": "bWPXADZylm0", "do": "subtitle", "track": "manual:ko"}) + "\n")
            f.write(json.dumps({"url": "Et9xVTOjgko", "do": "subtitle", "track": "manual:ko"}) + "\n")
        try:
            code, stdout, stderr = run_cli(["batch", tmp_file, "-o", OUT_DIR])
            self.assertEqual(code, 6)
            self.assertIn("Summary:", stdout)
            self.assertIn("[1/2]", stdout)
            self.assertIn("[2/2]", stdout)
        finally:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)


if __name__ == "__main__":
    unittest.main()

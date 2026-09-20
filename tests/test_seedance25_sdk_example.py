import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "higgsfield_seedance_25" / "main.py"


def load_example_module():
    spec = importlib.util.spec_from_file_location("seedance25_example", EXAMPLE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load Seedance 2.5 example")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Seedance25SdkExampleTests(unittest.TestCase):
    def test_exact_model_and_requested_parameters_are_present(self) -> None:
        text = EXAMPLE.read_text(encoding="utf-8")
        self.assertIn(
            'MODEL = "bytedance/seedance-2.5/text-to-video"',
            text,
        )
        self.assertIn('PROMPT = "A cinematic scene at sunset"', text)
        self.assertIn('"duration": 5', text)
        self.assertIn('"resolution": "720p"', text)
        self.assertIn('"aspect_ratio": "16:9"', text)
        self.assertIn("higgsfield_client.subscribe(", text)

    def test_example_extracts_video_url_without_credentials(self) -> None:
        module = load_example_module()
        self.assertEqual(
            module._extract_video_url({"video": {"url": "https://example.test/video.mp4"}}),
            "https://example.test/video.mp4",
        )

    def test_example_rejects_missing_video_url(self) -> None:
        module = load_example_module()
        with self.assertRaisesRegex(RuntimeError, "video URL"):
            module._extract_video_url({"status": "completed"})

    def test_env_local_is_explicitly_ignored(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".env.local", gitignore)

    def test_sdk_and_dotenv_are_locked_project_dependencies(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
        self.assertIn('"higgsfield-client>=0.1.0,<0.2.0"', pyproject)
        self.assertIn('"python-dotenv>=1.0.0,<2.0.0"', pyproject)
        self.assertIn('name = "higgsfield-client"', lock)
        self.assertIn('name = "python-dotenv"', lock)


if __name__ == "__main__":
    unittest.main()

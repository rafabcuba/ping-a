import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ping_a.audio import (
    AudioError,
    create_backend,
    default_sound,
    generate_beep_wav,
    load_sound,
    source_path,
    wav_duration,
)


class TestAudio(unittest.TestCase):
    def test_generate_beep_wav(self):
        data = generate_beep_wav()
        self.assertTrue(data.startswith(b"RIFF"))
        self.assertEqual(data[8:12], b"WAVE")
        self.assertGreater(wav_duration(data), 0.15)

    def test_load_nonexistent(self):
        with self.assertRaises(AudioError):
            load_sound("/ruta/que/no/existe.wav")

    def test_load_wav(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "beep.wav"
            path.write_bytes(generate_beep_wav())
            source = load_sound(str(path))
            self.assertEqual(source.name, "beep.wav")
            self.assertGreater(source.duration, 0.1)

    def test_source_cache_path(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(
                os.environ, {"XDG_CACHE_HOME": directory}
            ):
                source = default_sound()
                first = source_path(source)
                second = source_path(source)
                self.assertTrue(os.path.exists(first))
                self.assertEqual(first, second)
                self.assertTrue(first.startswith(directory))

    def test_null_and_bell_backends(self):
        self.assertEqual(create_backend("null").name, "null")
        self.assertEqual(create_backend("bell").name, "bell")

    def test_unknown_backend(self):
        with self.assertRaises(AudioError):
            create_backend("inventado")

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg no disponible")
    def test_decode_mp3(self):
        with tempfile.TemporaryDirectory() as directory:
            wav_path = Path(directory) / "tone.wav"
            mp3_path = Path(directory) / "tone.mp3"
            wav_path.write_bytes(generate_beep_wav())
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    str(wav_path),
                    str(mp3_path),
                ],
                check=True,
            )
            source = load_sound(str(mp3_path))
            self.assertGreater(source.duration, 0.1)


if __name__ == "__main__":
    unittest.main()

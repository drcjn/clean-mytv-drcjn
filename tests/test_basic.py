import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import install  # noqa: E402
import playlists  # noqa: E402


class Helpers(unittest.TestCase):
    def test_names(self):
        self.assertEqual(install.sanitize_names("  Asha,  Ravi & Mia  "), "Asha, Ravi & Mia")
        self.assertEqual(install.sanitize_names('A"; rm -rf / #'), "A rm -rf")
        self.assertEqual(len(install.sanitize_names("x" * 200)), 60)
        self.assertEqual(install.sanitize_names(None), "")

    def test_host(self):
        self.assertTrue(install.valid_host("192.168.1.50"))
        self.assertTrue(install.valid_host("10.0.0.2:5555"))
        self.assertFalse(install.valid_host("tv.local; reboot"))
        self.assertFalse(install.valid_host(""))

    def test_filter_list_keeps_default_apps(self):
        out = install.filter_list("com.sonyliv\ncom.netflix.ninja  # preinstalled\n# note\ncom.google.android.apps.mediashell\n")
        lines = out.splitlines()
        self.assertEqual(lines[0], "com.sonyliv")
        self.assertTrue(lines[1].startswith("# kept"))
        self.assertTrue(lines[3].startswith("# kept"))

    def test_find_example(self):
        with tempfile.TemporaryDirectory() as t:
            for n in ["xiaomi-mitv-axfr1", "xiaomi-mitv-axfr2", "tcl-55p71b"]:
                (Path(t) / n).mkdir()
                (Path(t) / n / "debloat.txt").write_text("x\n")
            hits = install.find_example("MiTV-AXFR1", t)
            self.assertEqual([h.name for h in hits], ["xiaomi-mitv-axfr1"])
            self.assertEqual(install.find_example("Unknown-9000", t), [])

    def test_theme(self):
        cfg = install.make_theme("A & B", ["com.netflix.ninja"], True)
        self.assertEqual(cfg["greeting_name"], "A & B")
        self.assertTrue(cfg["wallpaper"])
        self.assertNotIn("greeting_name", install.make_theme("", [], False))


class Playlists(unittest.TestCase):
    def test_parse(self):
        codes, genres, problems = playlists.parse_choices("India, USA & Korea, uk, bd", "Movies, kids")
        self.assertEqual(codes, ["in", "us", "kr", "uk", "bd"])
        self.assertEqual(genres, ["movies", "kids"])
        self.assertEqual(problems, [])

    def test_problems(self):
        _, _, problems = playlists.parse_choices("Atlantis", "cartoonz")
        self.assertEqual(len(problems), 2)

    def test_urls(self):
        urls = dict(playlists.playlist_urls(["kr"], ["kids"]))
        self.assertEqual(urls["KR"], "https://iptv-org.github.io/iptv/countries/kr.m3u")
        self.assertEqual(urls["Kids"], "https://iptv-org.github.io/iptv/categories/kids.m3u")


class Photos(unittest.TestCase):
    def test_prep(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")
        sys.path.insert(0, str(ROOT / "tools"))
        import prep_photos
        with tempfile.TemporaryDirectory() as t:
            src, out = Path(t) / "src", Path(t) / "out"
            src.mkdir()
            for i, (w, h, c) in enumerate([(600, 900, "red"), (600, 900, "blue"), (900, 600, "green")]):
                Image.new("RGB", (w, h), c).save(src / ("p%d.jpg" % i))
            n = prep_photos.build(prep_photos.find_photos(src), out)
            self.assertEqual(n, 2)                      # one portrait pair + one landscape
            for f in out.glob("*.jpg"):
                self.assertEqual(Image.open(f).size, (1280, 720))


if __name__ == "__main__":
    unittest.main()

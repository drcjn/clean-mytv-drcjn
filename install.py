#!/usr/bin/env python3
"""clean-mytv-drcjn: one-wizard clean-up for an Android TV / Google TV over Wi-Fi.

    python3 install.py                 # asks 4 questions, then does everything
    python3 install.py --dry-run       # shows the plan, changes nothing on the TV
    python3 install.py --only theme    # re-run one part later (apps, debloat, launcher, theme, closeapps, playlists)

Built on the open-source CleanYourTV project (downloaded at install time, pinned to a tested commit).
Everything it disables is only *disabled* (never uninstalled) and can be restored.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
import playlists  # noqa: E402

UPSTREAM_URL = "https://github.com/Gathin23/cleanyourtv"
UPSTREAM_REF = "be6087056a1c7d4f08f3f1cc778d92374d86ef27"   # tested commit; change deliberately, not automatically
UP = ROOT / "upstream"
PY = UP / "tools" / "venv" / "bin" / "python"
BACKUP = ROOT / "backup"
WORK = ROOT / "out"

# The few apps every install gets. Anyone can change the dock later (see README, "Customise").
DEFAULT_APPS = [
    ("Netflix", "com.netflix.ninja"),
    ("Prime Video", "com.amazon.amazonvideo.livingroom"),
    ("YouTube", "com.google.android.youtube.tv"),
    ("Apple TV", "com.apple.atve.androidtv.appletv"),
    ("MX Player", "com.mxtech.videoplayer.television"),
]
TELEVIZO = playlists.TELEVIZO
PROTECTED = {p for _, p in DEFAULT_APPS} | {TELEVIZO, "com.google.android.apps.mediashell"}  # never disabled; mediashell = Chromecast
STEPS = ["apps", "debloat", "launcher", "theme", "closeapps", "playlists"]


class Ctx:
    def __init__(self, a):
        self.a = a
        self.dry = a.dry_run
        self.host = a.tv_ip

    def tv(self, cmd, mutate=True):
        """Run one shell command on the TV via CleanYourTV's ADB client. Mutating commands are skipped in --dry-run."""
        if self.dry and mutate:
            print("    [dry-run] tv: %s" % (cmd if len(cmd) < 110 else cmd[:107] + "..."))
            return ""
        r = subprocess.run([str(PY), str(UP / "tools" / "tv.py"), cmd], env=dict(os.environ, TV_HOST=self.host),
                           capture_output=True, text=True, timeout=300)
        return (r.stdout or "") + (r.stderr or "")

    def script(self, args, mutate=True, **env):
        if self.dry and mutate:
            print("    [dry-run] run: %s" % " ".join(map(str, args)))
            return 0
        e = dict(os.environ, TV_HOST=self.host, **env)
        return subprocess.run([str(x) for x in args], env=e, cwd=str(UP) if str(args[0]).startswith(str(UP)) else None).returncode


# ---------- small pure helpers (unit-tested) ----------
def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def sanitize_names(text):
    text = re.sub(r"[^\w &,.'\-]", "", text or "", flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()[:60]


def valid_host(h):
    return bool(re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}(:\d{2,5})?", h or ""))


def find_example(model, examples_dir):
    """Folders of CleanYourTV's tested lists whose name contains the TV's model (e.g. MiTV-AXFR1)."""
    m = norm(model)
    if not m or not Path(examples_dir).is_dir():
        return []
    hits = [d for d in sorted(Path(examples_dir).iterdir()) if (d / "debloat.txt").is_file() and m in norm(d.name)]
    return sorted(hits, key=lambda d: len(d.name))


def filter_list(text):
    """Drop the lines that would disable our default apps or Chromecast; keep everything else (and comments)."""
    out = []
    for line in text.splitlines():
        pkg = line.split("#")[0].strip()
        if pkg and pkg in PROTECTED:
            out.append("# kept by clean-mytv: " + line.strip())
        else:
            out.append(line)
    return "\n".join(out) + "\n"


def make_theme(names, dock, has_wallpaper):
    cfg = {
        "background_color": "#000000", "columns": 5, "dock_apps": dock,
        "hidden_apps": ["com.android.tv"], "live_tv_package": "",
        "dock_glass": False, "dock_band": True, "dock_title": False, "ambient_glow": False, "app_glow": False,
        "icon_only_buttons": True, "icon_only_inputs": True, "show_greeting": True,
        "clock_wallpaper": True, "clock_wallpaper_dim": 10, "clock_glow": False,
        "tile_menu": True, "reorder_button": True, "wallpaper": bool(has_wallpaper),
        "wallpaper_rotation_minutes": 20, "wallpaper_order": "shuffle", "wallpaper_dim": 0,
    }
    if names:
        cfg["greeting_name"] = names
    return cfg


# ---------- environment ----------
def java_home():
    cands = [os.environ.get("JAVA_HOME", ""), "/opt/homebrew/opt/openjdk@17", "/opt/homebrew/opt/openjdk@21",
             "/usr/local/opt/openjdk@17", "/usr/local/opt/openjdk@21"]
    try:
        cands.append(subprocess.run(["/usr/libexec/java_home", "-v", "17"], capture_output=True, text=True).stdout.strip())
    except OSError:
        pass
    for c in cands:
        j = Path(c) / "bin" / "java" if c else None
        if j and j.exists():
            v = subprocess.run([str(j), "-version"], capture_output=True, text=True).stderr
            m = re.search(r'version "(\d+)', v)
            if m and 17 <= int(m.group(1)) <= 22:
                return c
    return None


def android_home():
    for c in [os.environ.get("ANDROID_HOME", ""), str(Path.home() / "Library/Android/sdk"), str(Path.home() / "Android/Sdk"),
              "/opt/homebrew/share/android-commandlinetools"]:
        if c and (Path(c) / "platforms" / "android-34").is_dir() and (Path(c) / "build-tools").is_dir():
            return c
    return None


def preflight():
    problems = []
    if sys.version_info < (3, 8):
        problems.append("Python 3.8+ is needed")
    if not shutil.which("git"):
        problems.append("git is missing (macOS: xcode-select --install)")
    if not java_home():
        problems.append("JDK 17-22 is missing (macOS: brew install openjdk@17)")
    if not android_home():
        problems.append("Android SDK platform 34 + build-tools 34.0.0 not found "
                        "(macOS: brew install --cask android-commandlinetools, then: "
                        "sdkmanager \"platforms;android-34\" \"build-tools;34.0.0\")")
    return problems


def setup_upstream(dry):
    if not UP.exists():
        print("  downloading CleanYourTV (pinned %s)" % UPSTREAM_REF[:8])
        subprocess.run(["git", "clone", "-q", UPSTREAM_URL, str(UP)], check=True)
    subprocess.run(["git", "-C", str(UP), "checkout", "-q", UPSTREAM_REF], check=True)
    if not PY.exists():
        print("  creating Python environment")
        subprocess.run([sys.executable, "-m", "venv", str(UP / "tools" / "venv")], check=True)
        pip = [str(PY), "-m", "pip", "install", "-q", "--disable-pip-version-check"]
        subprocess.run(pip + ["-r", str(UP / "tools" / "requirements.txt")], check=True)
        subprocess.run(pip + ["pillow"], check=True)
        subprocess.run(pip + ["pillow-heif"], check=False)   # optional (HEIC photos)


# ---------- questions ----------
def ask(q, default=""):
    if not sys.stdin.isatty():
        return default
    r = input("%s%s " % (q, " [%s]" % default if default else "")).strip()
    return r or default


def gather(a):
    print("\nclean-mytv: four questions (press Enter to skip any of them)\n")
    while not valid_host(a.tv_ip):
        a.tv_ip = ask("TV IP address (TV: Settings > Network; TV and computer on the same Wi-Fi):")
        if not valid_host(a.tv_ip):
            print("  that is not an IP address like 192.168.1.50")
            if not sys.stdin.isatty():
                sys.exit("--tv-ip is required")
    if a.photos is None:
        a.photos = ask("1. Photo or folder of photos for the background and screensaver:")
    if a.names is None:
        a.names = ask("2. Names for the greeting, e.g. 'Asha, Ravi & Mia':")
    a.names = sanitize_names(a.names)
    if a.countries is None:
        a.countries = ask("3a. Countries for free TV channels (e.g. India, USA, Korea):")
    if a.genres is None:
        a.genres = ask("3b. Genres (%s):" % ", ".join(playlists.GENRES[:12]) + ", ...", "")
    return a


# ---------- the work ----------
def step_apps(c, probe):
    print("\n[apps] default apps: %s" % ", ".join(l for l, _ in DEFAULT_APPS))
    installed = set(re.findall(r"package:(\S+)", c.tv("pm list packages", mutate=False)))
    wanted = DEFAULT_APPS + [("Televizo (free IPTV player)", TELEVIZO)]
    for label, pkg in wanted:
        if pkg in installed:
            print("  %s: already installed" % label)
            continue
        print("  %s: opening its Play Store page and pressing Install (TV must be signed in to Google Play)" % label)
        c.tv("am start -a android.intent.action.VIEW -d 'market://details?id=%s' >/dev/null 2>&1; sleep 6; "
             "input keyevent KEYCODE_DPAD_CENTER" % pkg)
        if c.dry:
            continue
        for _ in range(40):
            if pkg in c.tv("pm list packages %s" % pkg, mutate=False):
                print("    installed")
                break
            time.sleep(6)
        else:
            print("    ! %s did not install; install it from the Play Store yourself, then run: python3 install.py --only theme" % label)
    c.tv("input keyevent KEYCODE_HOME")


def step_debloat(c, probe):
    model = probe.get("ro.product.model", "")
    hits = find_example(model, UP / "examples")
    if not hits:
        sys.exit("\nNo tested debloat list for model %r. Nothing was changed.\n"
                 "Use PROMPT.md with a coding assistant (it discovers the bloat on your TV), or pass your own list:\n"
                 "  python3 install.py --list my-list.txt   (one package per line)\n" % model)
    src = Path(c.a.list) if c.a.list else hits[0] / "debloat.txt"
    print("\n[debloat] using %s" % (src.relative_to(UP) if str(src).startswith(str(UP)) else src))
    BACKUP.mkdir(exist_ok=True)
    for name, cmd in [("packages-all.txt", "pm list packages"), ("packages-disabled.txt", "pm list packages -d"),
                      ("getprop.txt", "getprop")]:
        (BACKUP / name).write_text(c.tv(cmd, mutate=False))
    filtered = BACKUP / "debloat-applied.txt"
    filtered.write_text(filter_list(src.read_text()))
    n = sum(1 for l in filtered.read_text().splitlines() if l.split("#")[0].strip())
    print("  %d packages will be DISABLED (not uninstalled); backup + restore list in %s" % (n, BACKUP))
    c.script([UP / "tools" / "disable.sh", filtered])


def step_launcher(c, probe):
    print("\n[launcher] building and installing the clean home screen (a few minutes)")
    c.script([UP / "launcher" / "build-and-install.sh"], JAVA_HOME=java_home() or "", ANDROID_HOME=android_home() or "")


def installed_dock(c):
    have = set(re.findall(r"package:(\S+)", c.tv("pm list packages", mutate=False)))
    dock = [p for _, p in DEFAULT_APPS if p in have]
    return dock if (dock or c.dry) else [p for _, p in DEFAULT_APPS]


def step_theme(c, probe):
    print("\n[theme] wallpaper, greeting, dock")
    theme = WORK / "theme"
    shutil.rmtree(theme, ignore_errors=True)
    theme.mkdir(parents=True)
    has_wp = False
    if c.a.photos:
        tmp = WORK / "stitched"
        shutil.rmtree(tmp, ignore_errors=True)
        subprocess.run([str(PY), str(ROOT / "tools" / "prep_photos.py"), c.a.photos, str(tmp)]
                       + (["--trim-bottom", str(c.a.trim_bottom)] if c.a.trim_bottom else []), check=True)
        subprocess.run([str(PY), "-I", str(UP / "tools" / "wallpaper_prep.py"), str(tmp), str(theme / "wallpapers"),
                        "--brightness", "0.7", "--gradient", "0.45"], check=True)
        has_wp = True
    cfg = make_theme(c.a.names, installed_dock(c), has_wp)
    extra = ROOT / "theme-overrides.json"          # your own tweaks, kept across re-runs (never committed)
    if extra.is_file():
        cfg.update(json.loads(extra.read_text()))
    (theme / "config.json").write_text(json.dumps(cfg, indent=2))
    c.script([UP / "tools" / "theme.sh", theme])
    c.tv("settings put secure screensaver_components com.gathin.tvhome/.ClockDream; settings put secure screensaver_enabled 1")


def step_closeapps(c, probe):
    print("\n[closeapps] 'Close Apps' tile + automatic closing of other streaming apps")
    app = ROOT / "closeapps"
    apps = c.a.close_apps.split() if c.a.close_apps else installed_dock(c) + [TELEVIZO]
    if c.dry:
        print("    [dry-run] would build the helper for: %s, install it, then you press Allow on the TV" % " ".join(apps))
        return
    (app / "app/src/main/assets/apps.txt").write_text(" ".join(apps) + "\n")
    (app / "local.properties").write_text("sdk.dir=%s\n" % (android_home() or ""))
    r = subprocess.run(["./gradlew", "--no-daemon", "-q", "assembleRelease"], cwd=str(app),
                       env=dict(os.environ, JAVA_HOME=java_home() or "", ANDROID_HOME=android_home() or ""))
    apk = app / "app/build/outputs/apk/release/app-release.apk"
    if r.returncode or not apk.exists():
        print("  ! build failed; skipping the Close Apps helper (everything else still works)")
        return
    subprocess.run([str(PY), "-I", str(UP / "tools" / "b64push.py"), str(apk), "/data/local/tmp/closeapps.apk"],
                   env=dict(os.environ, TV_HOST=c.host), check=True, stdout=subprocess.DEVNULL)
    c.tv("pm install -r /data/local/tmp/closeapps.apk; rm -f /data/local/tmp/closeapps.apk; am start -n tv.closeapps/.MainActivity")
    print("  >>> LOOK AT THE TV: tick 'Always allow from this computer' and choose Allow (this is the helper's own key).")
    print("      The helper needs the TV's network debugging to stay ON.")
    for _ in range(36):
        time.sleep(5)
        if c.tv('ps -A -o ARGS | grep -c "[a]utoclose.sh"', mutate=False).strip().startswith(("1", "2", "3")):
            print("  Close Apps is running.")
            return
    print("  ! the watcher did not start; press the 'Close Apps' tile on Home after allowing the key.")


def step_playlists(c, probe):
    codes, genres, problems = playlists.parse_choices(c.a.countries, c.a.genres)
    if problems:
        print("\n[playlists] skipped:\n  " + "\n  ".join(problems))
        return
    entries = playlists.playlist_urls(codes or [], genres)
    if not entries:
        print("\n[playlists] nothing chosen, skipped")
        return
    print("\n[playlists] %d free playlists for Televizo" % len(entries))
    good = [(n, u) for n, u in entries if c.dry or playlists.url_exists(u)]
    for n, u in entries:
        if (n, u) not in good:
            print("  ! no such playlist, skipped: %s" % u)
    WORK.mkdir(exist_ok=True)
    (WORK / "playlists.txt").write_text("\n".join("%s %s" % x for x in good) + "\n")
    if not c.dry:
        playlists.add_to_televizo(lambda cmd: c.tv(cmd), good)
    print("  (the URLs are also in %s, in case you want to add them by hand)" % (WORK / "playlists.txt"))


STEP_FN = {"apps": step_apps, "debloat": step_debloat, "launcher": step_launcher, "theme": step_theme,
           "closeapps": step_closeapps, "playlists": step_playlists}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tv-ip")
    ap.add_argument("--photos", help="photo, or folder of photos, for background + screensaver")
    ap.add_argument("--trim-bottom", type=float, default=0.0, help="cut this fraction off the bottom of every photo (watermark strips)")
    ap.add_argument("--names", help="names for the greeting")
    ap.add_argument("--countries", help="e.g. 'India, USA, Korea'")
    ap.add_argument("--genres", help="e.g. 'movies, music, kids'")
    ap.add_argument("--close-apps", help="package names the Close Apps helper manages (default: the dock apps + Televizo)")
    ap.add_argument("--list", help="your own debloat list (one package per line) instead of the tested one")
    ap.add_argument("--only", help="comma-separated parts to run: " + ",".join(STEPS))
    ap.add_argument("--dry-run", action="store_true", help="show the plan; change nothing on the TV")
    ap.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    a = ap.parse_args(argv)

    steps = [s.strip() for s in a.only.split(",")] if a.only else STEPS
    bad = [s for s in steps if s not in STEPS]
    if bad:
        sys.exit("unknown part(s): %s" % ", ".join(bad))
    a = gather(a)
    problems = preflight()
    if problems and not a.dry_run:
        sys.exit("\nMissing on this computer:\n  - " + "\n  - ".join(problems))
    for p in problems:
        print("  note (needed for a real run): " + p)

    print("\nPlan: %s" % ", ".join(steps))
    print("  TV: %s | photos: %s | greeting: %s | countries: %s | genres: %s" % (
        a.tv_ip, a.photos or "none", a.names or "none", a.countries or "none", a.genres or "none"))
    print("  Nothing is uninstalled. ADB (network debugging) must stay ON for the Close Apps helper.")
    if not a.dry_run and not a.yes and sys.stdin.isatty() and input("\nType YES to change this TV: ").strip() != "YES":
        sys.exit("cancelled, nothing was changed")

    setup_upstream(a.dry_run)
    c = Ctx(a)
    out = subprocess.run([str(PY), str(UP / "tools" / "tv.py"), "--probe"], env=dict(os.environ, TV_HOST=a.tv_ip),
                         capture_output=True, text=True, timeout=120)
    text = out.stdout + out.stderr
    probe = dict(re.findall(r"^(\S+) = (.*)$", text, re.M))
    if "ro.product.model" not in probe:
        sys.exit("\nCould not reach the TV at %s.\n%s\nCheck: same Wi-Fi, USB debugging on, then accept 'Allow USB debugging?' on the TV." % (a.tv_ip, text.strip()[-300:]))
    print("\nConnected: %s (Android %s, SDK %s)" % (probe.get("ro.product.model"), probe.get("ro.build.version.release"),
                                                  probe.get("ro.build.version.sdk")))
    if int(probe.get("ro.build.version.sdk", "0")) < 26:
        sys.exit("This TV runs Android below 8.0; the launcher cannot be installed. Nothing was changed.")
    for s in steps:
        STEP_FN[s](c, probe)
    print("\nDone." + (" (dry run: nothing was changed)" if a.dry_run else
                       "\nRestore everything: upstream/tools/restore.sh backup/debloat-applied.txt   |   theme: upstream/tools/theme.sh --reset"))


if __name__ == "__main__":
    main()

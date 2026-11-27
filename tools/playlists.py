#!/usr/bin/env python3
"""Free IPTV playlists (iptv-org) for the Televizo player: pick countries and genres, then add them on the TV.

    python playlists.py --countries "india, usa, korea" --genres "movies, music, kids" --print-only

Adding them on the TV drives Televizo's own screens with remote-key presses over ADB (see add_to_televizo).
Televizo, iptv-org and the streams belong to their owners: these are free, community-maintained public streams,
some of which stop working over time.
"""
import argparse
import re
import subprocess
import sys
import time
import urllib.request

BASE = "https://iptv-org.github.io/iptv"
TELEVIZO = "com.ottplay.ottplay"

# Names people type -> iptv-org country code. Any two-letter ISO code also works (the URL is checked).
COUNTRIES = {
    "india": "in", "usa": "us", "us": "us", "united states": "us", "america": "us", "uk": "uk", "britain": "uk",
    "united kingdom": "uk", "england": "uk", "gb": "uk", "korea": "kr", "south korea": "kr", "bangladesh": "bd",
    "pakistan": "pk", "nepal": "np", "sri lanka": "lk", "france": "fr", "germany": "de", "italy": "it",
    "spain": "es", "portugal": "pt", "netherlands": "nl", "japan": "jp", "china": "cn", "brazil": "br",
    "canada": "ca", "australia": "au", "uae": "ae", "turkey": "tr", "russia": "ru", "indonesia": "id",
    "malaysia": "my", "singapore": "sg", "thailand": "th", "philippines": "ph", "mexico": "mx", "poland": "pl",
    "greece": "gr", "sweden": "se", "norway": "no", "ireland": "ie", "south africa": "za", "egypt": "eg",
}
GENRES = ["animation", "auto", "business", "classic", "comedy", "cooking", "culture", "documentary", "education",
          "entertainment", "family", "general", "kids", "legislative", "lifestyle", "movies", "music", "news",
          "outdoor", "public", "relax", "religious", "science", "series", "shop", "sports", "travel", "weather"]
DEFAULT_COUNTRIES = ["in"]
DEFAULT_GENRES = ["news"]


def split(text):
    return [t.strip().lower() for t in re.split(r"[,;/&\n]+|\band\b", text or "") if t.strip()]


def parse_choices(countries_text, genres_text):
    """-> (country_codes, genres, problems). Nothing is fetched here."""
    codes, genres, problems = [], [], []
    for c in split(countries_text):
        code = COUNTRIES.get(c) or (c if re.fullmatch(r"[a-z]{2}", c) else None)
        if code is None:
            problems.append("unknown country: %r (use a name from the README or a two-letter code)" % c)
        elif code not in codes:
            codes.append(code)
    for g in split(genres_text):
        if g not in GENRES:
            problems.append("unknown genre: %r (choose from: %s)" % (g, ", ".join(GENRES)))
        elif g not in genres:
            genres.append(g)
    return codes, genres, problems


def playlist_urls(codes, genres):
    out = [("%s" % c.upper(), "%s/countries/%s.m3u" % (BASE, c)) for c in codes]
    out += [(g.capitalize(), "%s/categories/%s.m3u" % (BASE, g)) for g in genres]
    return out


def url_exists(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "clean-mytv"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            head = r.read(4096).decode("utf-8", "ignore")
            return r.status == 200 and head.lstrip().startswith("#EXTM3U")
    except Exception:
        return False


def _keys(*names):
    return "for x in %s; do input keyevent KEYCODE_$x; sleep 0.7; done" % " ".join(names)


def add_to_televizo(tv, entries, say=print):
    """Add each (name, url) as an M3U playlist in Televizo. tv(cmd) runs one shell command on the TV.

    Verified on Televizo 'com.ottplay.ottplay' on Android TV 11 with its default English UI. If a screen looks
    different on your TV this can misfire: add the printed URLs by hand (Settings > Playlists > + > New M3U)."""
    tv("am force-stop %s; monkey -p %s -c android.intent.category.LEANBACK_LAUNCHER 1 >/dev/null 2>&1; sleep 7" % (TELEVIZO, TELEVIZO))
    # main screen -> gear (top right) -> Settings -> Playlists -> the + button
    tv(_keys("DPAD_UP", "DPAD_UP", *["DPAD_RIGHT"] * 6, "DPAD_CENTER", "DPAD_DOWN", "DPAD_DOWN", "DPAD_CENTER",
             "DPAD_RIGHT", "DPAD_RIGHT"))
    for name, url in entries:
        say("  adding %s" % name)
        safe = re.sub(r"[^A-Za-z0-9_]", "_", name)
        tv("input keyevent KEYCODE_DPAD_CENTER; sleep 1.5; input keyevent KEYCODE_DPAD_CENTER; sleep 3; "
           "input text %s; input keyevent KEYCODE_TAB; sleep 1; input text %s; sleep 1; input keyevent KEYCODE_ENTER; sleep 1; "
           "for x in UP UP UP RIGHT RIGHT; do input keyevent KEYCODE_DPAD_$x; sleep 0.4; done; "
           "input keyevent KEYCODE_DPAD_CENTER; sleep 2.5; input keyevent KEYCODE_DPAD_DOWN; sleep 0.4; "
           "input keyevent KEYCODE_DPAD_DOWN; sleep 0.4; input keyevent KEYCODE_DPAD_CENTER; sleep 4" % (safe, url))
    tv("input keyevent KEYCODE_HOME")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--countries", default="")
    ap.add_argument("--genres", default="")
    ap.add_argument("--print-only", action="store_true")
    a = ap.parse_args(argv)
    codes, genres, problems = parse_choices(a.countries, a.genres)
    if problems:
        sys.exit("\n".join(problems))
    for name, url in playlist_urls(codes, genres):
        print("%-12s %s %s" % (name, url, "" if a.print_only else ("ok" if url_exists(url) else "NOT FOUND")))


if __name__ == "__main__":
    main()

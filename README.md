# clean-mytv-drcjn

Make a slow Android TV / Google TV fast and clean, **over Wi-Fi, in one wizard**:

* removes the manufacturer's ads, telemetry and background junk (they are **disabled, never uninstalled**)
* replaces the cluttered home screen with a simple one: a dock of a few streaming apps, an app grid, HDMI/USB inputs
* puts **your own photos** behind it as a rotating wallpaper and screensaver
* greets your family by name ("Good morning, Asha, Ravi & Mia")
* adds **free live-TV playlists** by country and genre in a free player (Televizo), no account needed
* adds a **Close Apps** helper: opening one streaming app automatically closes the others, which is what keeps a
  1 GB TV smooth

Built and tested on a Xiaomi Mi TV 4A (MiTV-AXFR1, Android TV 11, 1 GB RAM). It stands on the open-source
[CleanYourTV](https://github.com/Gathin23/cleanyourtv) project, which the wizard downloads at install time.

> **Your photos stay yours.** They are processed on your computer and copied only to your TV. Nothing is uploaded, and
> this repository contains no personal photos, names or addresses.

## The key feature: Close Apps (auto-close)

A 1 GB TV runs out of memory when Netflix, YouTube and Prime sit in the background together, and that is what makes
it crawl. **Close Apps** fixes that automatically:

* **Automatic:** open any one of your streaming apps and the others are closed in the background about 2 seconds later.
  It never touches the app on screen or Chromecast.
* **One-press tile:** a red **Close Apps** tile on Home closes them all on demand.
* **Independent of your computer:** a small helper app on the TV starts the watcher at every boot, so you never run a
  command again. (Source in [`closeapps/`](closeapps/), the watcher is [`autoclose.sh`](closeapps/app/src/main/assets/autoclose.sh).)

In testing on a Xiaomi Mi TV 4A (1 GB RAM), opening Netflix after YouTube closed YouTube's process every time, and
free memory stayed noticeably higher. It needs the TV's network debugging to stay on (see below).

## What the wizard asks

| # | Question | Used for |
|---|---|---|
| 1 | A photo, or a folder of photos | Rotating wallpaper + screensaver. Portrait photos are put two side by side to fill the widescreen. |
| 2 | Names (e.g. `Asha, Ravi & Mia`) | The greeting on the home screen |
| 3 | Countries and genres (e.g. `India, USA, Korea` / `movies, music, kids`) | Free IPTV playlists added to Televizo |
| 4 | (nothing to answer) | A small default set of apps is installed: Netflix, Prime Video, YouTube, Apple TV, MX Player. Change it any time. |

Every question can be skipped with Enter.

## Quick start

On the **TV**: Settings > Device Preferences > About, press OK on **Build** seven times, go back, open
**Developer options** and turn on **USB debugging** (and *Network / ADB debugging*, e.g. "MiTV Adb debugging", if it is
listed). Note the TV's IP address (Settings > Network). Keep the TV on, on the same Wi-Fi as your computer.

On your **computer** (macOS or Linux):

```bash
# one-time tools (macOS example)
brew install openjdk@17
brew install --cask android-commandlinetools
sdkmanager "platforms;android-34" "build-tools;34.0.0"

git clone --branch v1.0 https://github.com/drcjn/clean-mytv-drcjn   # a reviewed release, not whatever is newest
cd clean-mytv-drcjn
python3 install.py --dry-run     # look first: shows the plan, changes nothing on the TV
python3 install.py               # the real thing
```

When asked, accept **"Allow USB debugging?"** on the TV (tick *Always allow*). Near the end, accept the prompt once more
for the Close Apps helper's own key.

Prefer typing everything up front?

```bash
python3 install.py --tv-ip 192.168.1.50 --photos ~/Pictures/family --names "Asha, Ravi & Mia" \
                   --countries "India, USA, Korea" --genres "movies, music, kids" --yes
```

Photos with a camera watermark strip at the bottom? Add `--trim-bottom 0.1` to cut 10% off every photo.

## What it does, step by step

| Part (`--only`) | What happens |
|---|---|
| `apps` | Installs the default apps and Televizo from Google Play if they are missing (the TV must be signed in to Google Play). |
| `debloat` | Backs up the package list, then **disables** the junk using the tested list for your TV model from CleanYourTV. No tested list for your model? The wizard stops *before changing anything* (see "Other TV models"). |
| `launcher` | Builds and installs the clean launcher, sets it as Home. |
| `theme` | Makes the wallpapers from your photos, sets the greeting, dock and screensaver. |
| `closeapps` | Builds and installs the Close Apps helper (a "Close Apps" tile, and automatic closing at every boot). |
| `playlists` | Adds iptv-org playlists for your countries and genres in Televizo. |

Re-run any part later, e.g. new photos: `python3 install.py --only theme --photos ~/Pictures/new`.

## Customise later

* **Dock apps / hidden tiles / look:** create `theme-overrides.json` next to `install.py`, e.g.
  `{"dock_apps": ["com.netflix.ninja", "com.google.android.youtube.tv"], "hidden_apps": ["com.android.tv"]}`, then run
  `python3 install.py --only theme`. Your file is merged over the defaults and survives re-runs. Holding OK on a tile also
  lets you move it. All keys are documented in
  [CleanYourTV's themes/README.md](https://github.com/Gathin23/cleanyourtv/blob/main/themes/README.md).
* **Different default apps:** edit `DEFAULT_APPS` at the top of `install.py`.
* **More playlists:** `python3 tools/playlists.py --countries "Japan" --genres "sports" --print-only` prints URLs to add in
  Televizo (Settings > Playlists > + > New M3U), or re-run `--only playlists`.
* **Apps the Close Apps helper manages:** `python3 install.py --only closeapps --close-apps "com.netflix.ninja com.google.android.youtube.tv"`
  (default: the dock apps plus Televizo). On the TV the list lives in `/data/local/tmp/autoclose.apps` and is read live.
* **Live TV / antenna users:** the wizard hides the TV's own "Live TV" tile. Remove `"com.android.tv"` from `hidden_apps`
  to bring it back.

## Close Apps helper: how it works, and the trade-off

Android does not let a normal app close other apps. The helper therefore talks to the TV's own debugging service from
inside the TV (`127.0.0.1:5555`) with a key you approve once, and runs a tiny watcher that closes other streaming apps
when you open one. **Network debugging must stay ON** for this. Only the approved key can connect; if you would rather
keep network debugging off, skip it: `python3 install.py --only apps,debloat,launcher,theme,playlists`.

## Restore / undo

```bash
upstream/tools/restore.sh backup/debloat-applied.txt     # re-enable everything that was disabled
upstream/tools/theme.sh --reset                          # remove the theme
```

To remove the helper: uninstall "tv.closeapps" in the TV's app settings, then switch network debugging off.
When you are finished with the TV, also turn off USB / network debugging and revoke the debugging authorisations.

## Other TV models

The debloat step uses [CleanYourTV's tested lists](https://github.com/Gathin23/cleanyourtv/tree/main/examples) (hundreds of
models). If yours is not there the wizard stops without changing anything. Options: give it your own list
(`--list my-list.txt`, one package name per line), or hand [`PROMPT.md`](PROMPT.md) to a coding assistant such as
Claude Code, which finds the bloat on your TV and asks before touching anything. Fire TV, Samsung (Tizen), LG (webOS) and
Roku are not Android TV and are not supported.

## Free TV channels: what to expect

The playlists come from [iptv-org](https://github.com/iptv-org/iptv): free, community-maintained public streams, mostly
news, public and themed channels. Some streams stop working, some are in other languages, and premium channels are not
included. Nothing here is affiliated with any broadcaster. Check what is legal where you live.

## Tests

```bash
python3 -m venv .venv && .venv/bin/pip install pillow
.venv/bin/python -m unittest discover -s tests -v
```

## Credits and licences

* [CleanYourTV](https://github.com/Gathin23/cleanyourtv) by Gathin23: the debloat lists, ADB tools and launcher (downloaded at
  install time, pinned to a tested commit, not copied here). See its repository for its licence.
* [iptv-org](https://github.com/iptv-org/iptv) playlists and [Televizo](https://play.google.com/store/apps/details?id=com.ottplay.ottplay): their owners' terms apply.
* [dadb](https://github.com/mobile-dev-inc/dadb) (Apache-2.0) in the Close Apps helper.
* This repository: MIT, see [LICENSE](LICENSE). Use at your own risk; you are changing your own TV.

# Security

* Install from a **release tag** (`git clone --branch v1.1 ...`), not from the latest `main`.
* `install.py` runs on your computer and talks to your TV: read it before running it. It downloads CleanYourTV at a
  pinned commit (see `UPSTREAM_REF`) and never uninstalls anything.
* The Close Apps helper needs the TV's network debugging to stay on; only the key you approve can connect.
* Found a problem? Please report it privately via GitHub's "Report a vulnerability" on this repository's Security tab.

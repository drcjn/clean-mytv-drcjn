# Prompt for a coding assistant (Claude Code, Codex, Gemini CLI ...)

Open this repository in your assistant and paste:

---

Set up my Android TV with this repository. Work on the real TV and keep me informed.

1. Check `README.md`, then run `python3 install.py --dry-run` first and show me the plan.
2. Ask me, one at a time: (a) the TV's IP address, (b) a photo or folder of photos for the background, (c) the names for
   the greeting, (d) countries and genres for free TV channels. I may skip any.
3. Run `python3 install.py` with those answers (add `--yes` only after I have approved the plan). Tell me when the TV will
   show "Allow USB debugging?" so I can accept it.
4. If the wizard says there is no tested debloat list for my model, do not improvise: follow the safety rules in
   `upstream/PROMPT.md` and `upstream/AGENTS.md` (disable, never uninstall; back up first; never touch core packages;
   small batches with screenshots), and ask me before disabling anything I might use.
5. Never print my IP address, photos or names anywhere public. Never commit `backup/`, `out/` or `upstream/`.
6. At the end remind me: network debugging must stay on for the Close Apps helper, and how to restore.

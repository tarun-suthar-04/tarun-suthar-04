# Setup

1. Create a repo named exactly `tarun-suthar-04` (public), upload everything in this folder.
2. Edit `profile.config.json`, then run `python scripts/build.py` (or let the workflow do it).
3. Open `preview.html` in a browser to check light and dark mode locally.

## TODOs (buttons show a yellow TODO tag until filled)
- `links.email`, `links.resume`, `links.leetcode`
- `projects[].repo` for each project (cards fall back to your repositories tab)
- `assets/hero.png`: cropped from your screenshot; replace with a higher-resolution image (max ~600px wide, <150 KB)
- `data/sample-contributions.json` is placeholder data; the workflow replaces it with real numbers
- "Currently learning" text/chips: edit in config if you want JavaScript / backend fundamentals instead of Django / API

## Test the workflow
Repo -> Actions -> "Update profile cards" -> Run workflow. Check that assets/ and README.md get a bot commit.

## Notes
- GitHub does not allow links inside README SVGs, so every clickable card is its own SVG wrapped in a link.
- Fonts: Inter / JetBrains Mono are used if installed, otherwise safe fallbacks. Headlines use textLength so they never overflow.

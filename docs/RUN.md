# Run it

Both blocks are moved unchanged from the README. The build stamps the page and the docx with the
current git HEAD, so after a run three tracked files show as modified; that is expected.

### From the committed CSVs (no dataset needed)

```bash
uv sync --extra dev
uv run pytest -q
uv run --extra figures python scripts/help_figures.py
uv run python scripts/wind_html.py
npm install -g docx
NODE_PATH="$(npm root -g)" node docs/memoria/build_memoria.js
uv run python scripts/check_readme.py
```

### Full pipeline (needs the dataset)

```bash
uv run python scripts/fetch_data.py          # ~730 MB, needs git-lfs
uv run python scripts/build_frame_cache.py
uv run python scripts/help_wind.py
uv run python scripts/second_help.py
uv run python scripts/help_kinds.py
uv run python scripts/near_robustness.py
uv run python scripts/matchup_check.py
uv run python scripts/wind_scenes.py
```

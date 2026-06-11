# Dev workflow

Edit in WSL, test on Windows, only use GitHub Actions for the final release build.

## The loop

All commands run from the WSL repo root. Each one rsyncs the working tree to
`C:\Users\jirod\ShimaTTS` first (no commit/push needed), then runs it with the
Windows venv (`.venv`, Python 3.11, CUDA torch).

```bash
scripts/win.sh test            # pytest on Windows
scripts/win.sh smoke           # import every runtime dep (catches packaging issues)
scripts/win.sh run             # run the real app on Windows, GPU and all
scripts/win.sh run --test-tts "hello chat"
scripts/win.sh run --test-overlay
scripts/win.sh build           # local PyInstaller build -> C:\Users\jirod\ShimaTTS\dist
scripts/win.sh deps            # (re)install deps into the Windows venv
scripts/win.sh sync            # just copy files, run nothing
```

The sync excludes `.git`, `.venv`, `dist`, `config.json`, `ShimaTTS.log`, and
`data/`, so the Windows-side config and uploads survive every sync. The Windows
checkout is a mirror - don't edit code there, it gets overwritten.

Override the Windows path with `SHIMA_WIN_DIR=/mnt/c/somewhere scripts/win.sh ...`.

## When to use what

| Change | Check with |
|---|---|
| Logic, server, filters | `scripts/win.sh test` (or pytest in WSL) |
| New/changed dependency | `scripts/win.sh smoke` |
| Audio, tray, dialogs, end-to-end | `scripts/win.sh run` |
| PyInstaller flags, build.py, hooks | `scripts/win.sh build`, then run the exe |
| Release | push a `v*` tag - CI builds, smoke-tests the exe, releases |

`ShimaTTS.exe --smoke` runs inside CI after the build, so a release with a
missing import fails the workflow instead of shipping. The workflow also has a
manual trigger (Actions tab -> Build Windows EXE -> Run workflow) to test the
CI build without tagging a release.

## Notes

- The distribution is a frozen `launcher.py` + `uv.exe` + app source. On the
  user's machine the launcher provisions `runtime/` (managed Python 3.11,
  CUDA torch if `nvidia-smi` exists, else CPU) and then runs
  `runtime\Scripts\pythonw.exe -m src.main` with `SHIMA_HOME` set. Torch and
  f5-tts are never frozen - that's how GPU support fits under GitHub's 2 GB
  release asset limit.
- `scripts/win.sh build` keeps `dist/ShimaTTS/runtime` between rebuilds.
  Delete it (or change requirements) to test provisioning from scratch;
  set `SHIMA_TORCH_INDEX=https://download.pytorch.org/whl/cpu` to avoid the
  4 GB CUDA download while testing.
- Windows venv setup from scratch (PowerShell):
  `py -3.11 -m venv C:\Users\jirod\ShimaTTS\.venv`, then `scripts/win.sh deps`.

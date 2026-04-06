# babkacli

Utilities for parsing agent JSON responses and executing workspace commands.

## Agent CLI

Run the GitHub Models agent from the repository root:

```bash
babkacli
```

It starts in `test_project` by default and accepts natural language tasks.
The agent can inspect files, create folders, create files, write code, run Python scripts, and finish with a `done` command.

For a one-off task:

```bash
babkacli --once "Inspect the project and summarize the main entrypoint."
```

If you want the older command-testing CLI, run:

```bash
python -m src.cli
```

For the PySide6 UI:

```bash
babkacli-ui
```

or directly:

```bash
python -m src.ui
```

### UI terminal

The embedded terminal is a PySide6 interactive ANSI/VT100 terminal. On Windows it uses `winpty` for live streaming output and full-screen control sequences; `QProcess` remains the fallback transport backend. It starts PowerShell with `-NoProfile`, `POWERSHELL_DISABLE_TELEMETRY=1`, `TERM=xterm-256color`, and `COLORTERM=truecolor`.

### Chat web view

The chat history panel now uses `Qt WebView` hosted through QML instead of `QtWebEngineWidgets`.

On Windows, `Microsoft Edge WebView2 Runtime` is required. The UI fails fast at startup with a blocking error if the runtime is missing, instead of silently falling back to another web backend.

# snakktilmeg

Small macOS dictation helper. Press the global hotkey once to start recording, press it again to stop, transcribe the captured WAV with `whisper.cpp`, then paste the transcript into the active app through the macOS clipboard.

## Requirements

- Python 3.13+
- `uv`
- macOS, for clipboard paste automation through `pbcopy` and `osascript`
- Microphone access for the terminal/app running the process
- A local `whisper.cpp` checkout with:
  - CLI: `~/code/div/whisper.cpp/build/bin/whisper-cli`
  - Model: `~/code/div/whisper.cpp/models/ggml-base.en.bin`

Those `whisper.cpp` paths are currently hardcoded in `main.py`.

## Setup

```sh
uv sync
```

If `whisper.cpp` is not already built, build it and download the expected model in that repository before running this app.

## Run

```sh
uv run python main.py
```

Default hotkey: `Ctrl` + `Alt` + `Space`.

Use the hotkey once to start recording and again to stop. While transcription is running, additional hotkey presses are ignored. Logs are emitted as JSON on stderr/stdout depending on the logging handler stream.

Press `Ctrl-C` in the terminal to shut the app down cleanly. If the app is only listening for the hotkey, it exits immediately. If a recording is active, the partial audio is discarded without transcription or paste. If transcription or paste is already in progress, shutdown waits for that work to finish before exiting.

## Tests

Run the unit test suite:

```sh
uv run pytest
```

Optional type check:

```sh
uv run pyright
```

Current tests cover the app orchestration, hotkey state transitions, graceful `Ctrl-C` shutdown behavior, structured error handling, empty transcript handling, WAV writing, `whisper.cpp` command construction/output parsing, macOS paste command construction, JSON log formatting, and timing logs.

Coverage is mostly unit-level with fakes. The suite does not fully exercise real microphone input, real global hotkeys, real `whisper.cpp` execution, or macOS accessibility/clipboard integration end to end.

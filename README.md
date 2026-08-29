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

## Setup

```sh
uv sync
cp .env.example .env
```

Edit `.env` if your `whisper.cpp` checkout or model live somewhere else:

```sh
WHISPER_REPO_PATH=~/code/div/whisper.cpp
WHISPER_MODEL_PATH=~/code/div/whisper.cpp/models/ggml-base.en.bin
HOTKEY=<ctrl>+<alt>+<space>
```

If `whisper.cpp` is not already built, build it and download the configured model before running this app. The app derives the CLI path as `WHISPER_REPO_PATH/build/bin/whisper-cli`.

## Run

```sh
uv run python main.py
```

Default hotkey: `Ctrl` + `Alt` + `Space`. Configure it with `HOTKEY` in `.env` using `pynput.keyboard.HotKey.parse` syntax, for example `<ctrl>+<alt>+<space>`.

Use the hotkey once to start recording and again to stop. A click-through status pill appears near the bottom center of the focused application's display: it shows `Listening…` while the microphone is recording and `Transcribing…` while whisper is processing the audio. If the focused display cannot be determined, the pill appears on the primary display. While transcription is running, additional hotkey presses are ignored. Logs are emitted as JSON on stderr/stdout depending on the logging handler stream.

The overlay uses native macOS AppKit APIs and does not take keyboard focus. If it cannot be initialized, the failure is logged and dictation continues without the visual indicator.

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

Current tests cover the app orchestration, hotkey and indicator state transitions, overlay positioning, graceful `Ctrl-C` shutdown behavior, structured error handling, empty transcript handling, WAV writing, `whisper.cpp` command construction/output parsing, macOS paste command construction, JSON log formatting, and timing logs.

Coverage is mostly unit-level with fakes. The suite does not fully exercise real microphone input, the AppKit overlay, real global hotkeys, real `whisper.cpp` execution, or macOS accessibility/clipboard integration end to end.

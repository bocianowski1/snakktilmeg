# snakktilmeg

Small dictation helper for macOS and Windows. Press the global hotkey once to start recording, press it again to stop, transcribe the captured WAV with `whisper.cpp`, then paste the transcript into the active app through the system clipboard.

## Requirements

- Python 3.13+
- `uv`
- macOS or Windows (run natively on Windows, not inside WSL)
  - macOS: clipboard paste through `pbcopy` and `osascript`; Accessibility and Microphone access for the terminal/app running the process
  - Windows: clipboard paste through the Win32 clipboard and a simulated `Ctrl` + `V`; microphone access enabled for desktop apps; a Python build that includes `tkinter` (the python.org and `uv`-managed builds do)
- A local `whisper.cpp` checkout with:
  - CLI: `~/code/div/whisper.cpp/build/bin/whisper-cli` on macOS, `~/code/div/whisper.cpp/build/bin/Release/whisper-cli.exe` on Windows
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

If `whisper.cpp` is not already built, build it and download the configured model before running this app. The app derives the CLI path from `WHISPER_REPO_PATH`:

- macOS: `WHISPER_REPO_PATH/build/bin/whisper-cli`
- Windows: `WHISPER_REPO_PATH/build/bin/Release/whisper-cli.exe`, which is where `cmake -B build` followed by `cmake --build build --config Release` puts it with the Visual Studio generator

On Windows, `~` in `.env` paths expands to your user profile folder; plain Windows paths such as `C:\code\whisper.cpp` also work.

## Run

```sh
uv run python main.py
```

Default hotkey: `Ctrl` + `Alt` + `Space`. Configure it with `HOTKEY` in `.env` using `pynput.keyboard.HotKey.parse` syntax, for example `<ctrl>+<alt>+<space>`.

Use the hotkey once to start recording and again to stop. A click-through status pill appears near the bottom center of the focused application's display: it shows `Listening…` while the microphone is recording and `Transcribing…` while whisper is processing the audio. If the focused display cannot be determined, the pill appears on the primary display. While transcription is running, additional hotkey presses are ignored. Logs are emitted as JSON on stderr/stdout depending on the logging handler stream.

On macOS the overlay uses native AppKit APIs; on Windows it is a click-through `tkinter` window on the focused window's monitor. On both platforms it does not take keyboard focus, so the paste lands in the app you were using. If it cannot be initialized, the failure is logged and dictation continues without the visual indicator.

On Windows with a Norwegian or other layout that uses `AltGr`, `Ctrl` + `Alt` is the same as `AltGr`. The default hotkey still works, but pick another one in `HOTKEY` if it clashes with a character you type.

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

Current tests cover the app orchestration, hotkey and indicator state transitions, overlay positioning, graceful `Ctrl-C` shutdown behavior, structured error handling, empty transcript handling, WAV writing, `whisper.cpp` command construction/output parsing, macOS and Windows paste flows, Windows indicator queueing, platform adapter selection, JSON log formatting, and timing logs.

Coverage is mostly unit-level with fakes. The suite does not fully exercise real microphone input, the AppKit or `tkinter` overlays, real global hotkeys, real `whisper.cpp` execution, or the macOS/Windows clipboard integration end to end.

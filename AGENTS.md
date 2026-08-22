# Agent Guide

This project is a small macOS dictation helper. It records audio on a global
hotkey, transcribes the WAV through a local `whisper.cpp` CLI, and pastes the
result into the active app.

Keep the project intentionally small, but preserve the boundaries that make it
easy to extend.

## Architecture

- `main.py` is the composition root. It should wire config, logging, concrete
  adapters, and the application object. Avoid putting workflow logic here.
- `lib/app.py` owns orchestration: recording state, hotkey behavior,
  transcription flow, text insertion, shutdown, and user-facing logging.
- Adapter modules wrap external systems:
  - `lib/audio.py`: microphone capture and WAV writing through `sounddevice`.
  - `lib/transcription.py`: `whisper.cpp` subprocess invocation and transcript
    parsing.
  - `lib/text_insertion.py`: macOS clipboard and paste automation.
  - `lib/hotkeys.py`: global hotkey listener through `pynput`.
  - `lib/config.py`: environment and `.env` configuration.
  - `lib/logging.py`: JSON logging setup.
- `tests/` mirrors the production modules and should stay fast and mostly
  unit-level.

## Design Rules

- Keep external integrations behind small protocols or injectable callables.
  `App` should depend on capabilities, not concrete libraries or subprocesses.
- Add new behavior at the narrowest boundary:
  - Workflow/state changes usually belong in `App`.
  - New OS, subprocess, hardware, or service interactions belong in adapter
    modules.
  - New environment values belong in `config.py` and `WhisperConfig` unless
    they are clearly unrelated to whisper setup.
- Prefer explicit domain errors from `lib/errors.py` over leaking raw
  `OSError`, `subprocess.CalledProcessError`, library exceptions, or permission
  failures across module boundaries.
- Include structured log fields with stable `event` names for meaningful
  workflow steps and failures. Do not rely on free-form log messages for machine
  interpretation.
- Keep imports of optional/platform-specific libraries inside the adapter
  methods that need them when possible. This keeps tests portable and avoids
  import-time failures on machines missing macOS-specific dependencies.
- Do not introduce broad frameworks, background job systems, or global mutable
  state unless the existing protocol-and-adapter structure is no longer enough.

## Testing Expectations

- Run `uv run pytest` before handing off changes.
- Run `uv run pyright` for typed changes or public interface changes.
- Add focused tests with fakes for new orchestration behavior in `App`.
- For subprocess or OS command adapters, test command construction, successful
  parsing, and wrapped failure cases by injecting fake runners.
- For config changes, test required values, empty values, and derived paths.
- Mark any test that needs real hardware, `whisper.cpp`, macOS permissions, or
  global hotkeys with the existing `integration` marker.

## Scalability Guidelines

- Keep the core workflow deterministic and easy to test. If a feature needs
  concurrency, isolate it and expose a simple synchronization point for tests.
- If `App` grows beyond straightforward state orchestration, split by behavior
  rather than by technical layer. For example, extract a recording/transcription
  session object before adding conditionals throughout `App`.
- Preserve dependency direction: adapters may know about external libraries;
  orchestration should only know about protocols and domain errors.
- Keep user-visible behavior documented in `README.md` when it changes,
  especially hotkeys, environment variables, shutdown behavior, and platform
  requirements.
- Avoid editing generated, cache, or local runtime files such as `__pycache__/`,
  `.venv/`, and `recording.wav`.

## Common Commands

```sh
uv sync
uv run pytest
uv run pyright
uv run python main.py
```

## Environment

Expected local environment values:

```sh
WHISPER_REPO_PATH=~/code/div/whisper.cpp
WHISPER_MODEL_PATH=~/code/div/whisper.cpp/models/ggml-base.en.bin
HOTKEY=<ctrl>+<alt>+<space>
```

The app derives the CLI path as:

```text
${WHISPER_REPO_PATH}/build/bin/whisper-cli
```

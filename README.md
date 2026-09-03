# narrate

Turn owned EPUB and PDF books into chaptered `.m4b` audiobooks, then drop them in a [Jellyfin](https://jellyfin.org) Books library.

This is not Speechify. There is no live highlighting. Generation happens here. Listening happens in a real audiobook client.

```
owned EPUB/PDF  →  OpenRouter TTS  →  chaptered M4B  →  Jellyfin  →  phone
```

[![tests](https://github.com/3stacks/narrate/actions/workflows/test.yml/badge.svg)](https://github.com/3stacks/narrate/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Why

Spotify's audiobook hours cap and Speechify's subscription are the wrong product if you already bought the book. narrate reads a DRM-free EPUB or PDF you own, estimates the TTS cost before you commit, synthesises chaptered audio, and lands a single `.m4b` where Jellyfin can serve it.

Default voice is OpenRouter `openai/gpt-4o-mini-tts-2025-12-15` at **$0.60 per million characters**. A typical novel is about 100k words / 500k characters, so about **$0.30 per book**. No monthly hour cap.

Kokoro is almost the same price and a bit more robotic. Sesame and Grok Voice are quality upgrades at $7 and $15 per million characters.

## Requirements

- Python 3.12+
- [ffmpeg](https://ffmpeg.org) and `ffprobe` on `PATH`
- An [OpenRouter](https://openrouter.ai) API key
- Optional: a Jellyfin server with a Books library

## Install

```bash
git clone https://github.com/3stacks/narrate.git
cd narrate
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Put `OPENROUTER_API_KEY` in `.env`. Preview shows the dollar estimate before generation.

```bash
narrate serve                 # http://127.0.0.1:3841
narrate preview book.epub
narrate import book.epub --who me --yes
narrate voices
```

The import UI is a drop zone, a name, a voice, and a cost confirm. Several people can import; tag who did it with `NARRATE_USERS`.

## Output

Jellyfin Books layout:

```
data/library/
  Author Name/
    Book Title/
      Book Title.m4b
      cover.jpg
```

Jobs resume if the process dies mid-book. Already-synthesised chunks are skipped.

## Jellyfin

Create a Books library pointed at the folder that will hold those `Author/Title` directories. Paste an API key from Dashboard → API Keys so narrate can call `/Library/Media/Updated` after a book lands. If the drop-in fails, the local `.m4b` is still kept and the job warns.

Two ways to land the file. Same app.

**SSH.** Generate on a workstation, `rsync` over system `ssh`:

```
JELLYFIN_RSYNC_TARGET=media-server:/data/media/audiobooks
JELLYFIN_CONTAINER_PATH=/media/audiobooks
JELLYFIN_URL=http://media-server:8096
JELLYFIN_API_KEY=
```

`host:path` uses your existing SSH config. No extra keys in narrate.

**Same host.** Run narrate next to Jellyfin and write straight into the media folder. No SSH:

```
NARRATE_LIBRARY_DIR=/data/media/audiobooks
JELLYFIN_RSYNC_TARGET=
JELLYFIN_CONTAINER_PATH=/media/audiobooks
JELLYFIN_URL=http://127.0.0.1:8096
JELLYFIN_API_KEY=
NARRATE_HOST=0.0.0.0
```

Or `docker compose up --build`. The compose file bind-mounts a library directory and talks to Jellyfin at `host.docker.internal:8096`.

If Jellyfin sits behind an SSO wall (Cloudflare Access and similar), native apps and API keys usually cannot log in. Point players and `JELLYFIN_URL` at a LAN or tailnet address on port 8096 instead.

## Listen

This web app is not a player.

| Client | Notes |
|---|---|
| [Symfonium](https://symfonium.app/) (Android) | Best Jellyfin audiobook client: chapters, speed, sleep timer, Android Auto, offline |
| Official Jellyfin Android app | Free fallback. Background audio works |
| [Plappa](https://plappa.me/) (iOS) | Jellyfin + Audiobookshelf, built for books |
| BookPlayer (iOS) | Can pull from Jellyfin; also works with AirDropped `.m4b` files |

Give each listener their own Jellyfin user so progress stays separate.

## Config

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | Required for generation |
| `NARRATE_USERS` | Names in the import UI |
| `NARRATE_DATA_DIR` | Uploads, SQLite jobs, working files |
| `NARRATE_LIBRARY_DIR` | Where `.m4b` files are written |
| `JELLYFIN_RSYNC_TARGET` | `host:path` (SSH) or a local directory. Empty means in-place |
| `JELLYFIN_URL` | Jellyfin base URL for the library scan |
| `JELLYFIN_API_KEY` | Dashboard → API Keys |
| `JELLYFIN_CONTAINER_PATH` | Path *inside* the Jellyfin container, usually `/media/audiobooks` |
| `NARRATE_HOST` / `NARRATE_PORT` | Bind address for `narrate serve` |
| `NARRATE_BASIC_AUTH` | Optional `user:password` for the UI |
| `NARRATE_DEFAULT_MODEL` / `NARRATE_DEFAULT_VOICE` | TTS defaults |

## Not in scope

- OCR for scanned PDFs
- Stripping DRM
- Live sentence highlighting
- A custom phone player
- Voice cloning

Only books you purchased, DRM-free. Do not distribute the audio.

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

## License

MIT. See [LICENSE](LICENSE).

## Contact

Luke Boyle — [lukeboyle.com](https://lukeboyle.com) — [GitHub](https://github.com/3stacks)

# Raspberry Pi Service

The drop-in entrypoint is `run_service.py`.

It does three jobs:

- checks that `python3` is new enough
- checks that `ffmpeg` exists
- creates `.venv/`, installs Python packages, and starts the API when needed

The service keeps its model cache inside this project folder by default:

- `.cache/stable-ts`

## What The Pi Needs

Install these system packages once:

```bash
sudo apt update
sudo apt install -y python3 python3-venv ffmpeg
```

That is the only system-level requirement. Python packages are installed into a local `.venv`.

## Quick Start

Copy this folder to the Pi, for example:

```bash
/home/pi/alignment
```

Then either do a one-time install:

```bash
cd /home/pi/alignment
python3 run_service.py install
python3 run_service.py serve --host 0.0.0.0 --port 8000
```

Or let first start install its own Python packages:

```bash
cd /home/pi/alignment
python3 run_service.py serve --host 0.0.0.0 --port 8000 --auto-install
```

Useful checks:

```bash
python3 run_service.py doctor
python3 run_service.py doctor --strict
```

Notes:

- first install will create `.venv`
- first alignment request will download the Whisper model into `.cache/stable-ts`
- on a Raspberry Pi, start with `STABLE_TS_MODEL=base`

## systemd

1. Copy this project to the Pi, for example `/home/pi/alignment`.
2. Copy `lyric-align.service` to `/etc/systemd/system/lyric-align.service`.
3. Edit `User`, `WorkingDirectory`, and the `/home/pi/alignment` paths if needed.
4. Enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable lyric-align
sudo systemctl start lyric-align
sudo systemctl status lyric-align
```

The included unit uses:

```bash
/usr/bin/python3 /home/pi/alignment/run_service.py serve --host 0.0.0.0 --port 8000 --auto-install
```

So the service can bootstrap its own `.venv` on first start.

## API

### Health check

```bash
curl http://<pi-ip>:8000/health
```

### Get SRT back directly

```bash
curl -X POST "http://<pi-ip>:8000/align" \
  -F "audio=@songs/ハートムービング.wav" \
  -F "lyrics=<songs/ハートムービング.txt" \
  -F "language=ja" \
  -o aligned.srt
```

### Get JSON back

```bash
curl -X POST "http://<pi-ip>:8000/align-json" \
  -F "audio=@songs/ハートムービング.wav" \
  -F "lyrics=<songs/ハートムービング.txt" \
  -F "language=ja"
```

The JSON response includes:

- `srt`
- `textgrid`
- `segment_count`
- `model`
- `language`

For an iPhone app, the simplest contract is `multipart/form-data` with:

- `audio`: uploaded media file
- `lyrics`: plain text lyrics
- `language`: usually `ja`

## Troubleshooting

If startup fails:

- run `python3 run_service.py doctor`
- if `ffmpeg=missing`, install it with `sudo apt install -y ffmpeg`
- if Python is too old, install a newer `python3` before continuing
- if package install failed, rerun `python3 run_service.py install`

If the service is slow:

- use `STABLE_TS_MODEL=base`
- keep `workers=1`
- expect the first request after model download to be the slowest

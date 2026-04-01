# Lyric Alignment Service

`stable-ts`-based lyric alignment service for turning uploaded audio + lyrics into `.srt` subtitles.

## Run Locally

```bash
python3 run_service.py serve --host 0.0.0.0 --port 8000 --auto-install
```

## Raspberry Pi

See [README_PI_SERVICE.md](README_PI_SERVICE.md) for the Pi deployment steps and `systemd` unit.

from __future__ import annotations

import tempfile
from pathlib import Path
import shutil

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse

from align_core import (
    DEFAULT_DEVICE,
    DEFAULT_LANGUAGE,
    DEFAULT_MODEL,
    DOWNLOAD_ROOT,
    align_audio_to_outputs,
)


app = FastAPI(title="Lyric Alignment API", version="1.0.0")


async def save_upload(upload: UploadFile, destination: Path) -> None:
    with destination.open("wb") as handle:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)


@app.get("/health")
def health() -> dict[str, str | None]:
    return {
        "status": "ok",
        "model": DEFAULT_MODEL,
        "language": DEFAULT_LANGUAGE,
        "device": DEFAULT_DEVICE,
        "download_root": DOWNLOAD_ROOT,
        "ffmpeg": shutil.which("ffmpeg"),
    }


@app.post("/align", response_class=PlainTextResponse)
async def align_srt(
    audio: UploadFile = File(...),
    lyrics: str = Form(...),
    language: str = Form(DEFAULT_LANGUAGE),
    model: str = Form(DEFAULT_MODEL),
) -> PlainTextResponse:
    suffix = Path(audio.filename or "upload.wav").suffix or ".wav"

    try:
        with tempfile.TemporaryDirectory(prefix="lyric_align_") as tmpdir:
            tmpdir_path = Path(tmpdir)
            audio_path = tmpdir_path / f"input{suffix}"
            output_stem = tmpdir_path / "aligned"

            await save_upload(audio, audio_path)
            artifacts = align_audio_to_outputs(
                audio_path,
                lyrics,
                output_stem,
                language=language,
                model_name=model,
                device=DEFAULT_DEVICE,
                download_root=DOWNLOAD_ROOT,
            )
            srt_text = artifacts.srt_path.read_text(encoding="utf-8")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PlainTextResponse(
        srt_text,
        media_type="application/x-subrip",
        headers={"Content-Disposition": 'attachment; filename="aligned.srt"'},
    )


@app.post("/align-json")
async def align_json(
    audio: UploadFile = File(...),
    lyrics: str = Form(...),
    language: str = Form(DEFAULT_LANGUAGE),
    model: str = Form(DEFAULT_MODEL),
) -> JSONResponse:
    suffix = Path(audio.filename or "upload.wav").suffix or ".wav"

    try:
        with tempfile.TemporaryDirectory(prefix="lyric_align_") as tmpdir:
            tmpdir_path = Path(tmpdir)
            audio_path = tmpdir_path / f"input{suffix}"
            output_stem = tmpdir_path / "aligned"

            await save_upload(audio, audio_path)
            artifacts = align_audio_to_outputs(
                audio_path,
                lyrics,
                output_stem,
                language=language,
                model_name=model,
                device=DEFAULT_DEVICE,
                download_root=DOWNLOAD_ROOT,
            )
            payload = {
                "srt": artifacts.srt_path.read_text(encoding="utf-8"),
                "textgrid": artifacts.textgrid_path.read_text(encoding="utf-8"),
                "segment_count": artifacts.segment_count,
                "model": model,
                "language": language,
            }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JSONResponse(payload)

from __future__ import annotations

import os
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from praatio import textgrid
import stable_whisper


SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    "node_modules",
    ".align_runtime",
    "vendor",
}

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = os.environ.get("STABLE_TS_MODEL", "small")
DEFAULT_DEVICE = os.environ.get("STABLE_TS_DEVICE")
DEFAULT_LANGUAGE = os.environ.get("STABLE_TS_LANGUAGE", "ja")
DOWNLOAD_ROOT = os.environ.get(
    "STABLE_TS_DOWNLOAD_ROOT",
    str(PROJECT_ROOT / ".cache" / "stable-ts"),
)


@dataclass
class Pair:
    wav_path: Path
    txt_path: Path


@dataclass
class AlignmentArtifacts:
    srt_path: Path
    textgrid_path: Path
    segment_count: int


_MODEL_LOCK = threading.Lock()
_CACHED_MODEL = None
_CACHED_MODEL_KEY: tuple[str, str | None, str | None] | None = None


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def pretty_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def should_skip_dir(name: str) -> bool:
    return name.startswith(".") or name in SKIP_DIR_NAMES


def discover_pairs(root: Path) -> tuple[list[Pair], list[Path]]:
    pairs: list[Pair] = []
    skipped_wavs: list[Path] = []

    for dirpath, dirnames, _filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if not should_skip_dir(name)]
        current_dir = Path(dirpath)

        txt_by_stem = {
            normalize_text(path.stem): path for path in current_dir.glob("*.txt")
        }

        for wav_path in sorted(current_dir.glob("*.wav")):
            txt_path = txt_by_stem.get(normalize_text(wav_path.stem))
            if txt_path is None:
                skipped_wavs.append(wav_path)
                continue
            pairs.append(Pair(wav_path=wav_path, txt_path=txt_path))

    pairs.sort(key=lambda pair: pretty_path(pair.wav_path))
    skipped_wavs.sort(key=pretty_path)
    return pairs, skipped_wavs


def normalize_lyrics_text(text: str) -> str:
    lines = [
        normalize_text(line.strip())
        for line in text.splitlines()
        if line.strip()
    ]
    return "\n".join(lines)


def read_lyrics(path: Path) -> str:
    return normalize_lyrics_text(path.read_text(encoding="utf-8"))


def get_model(
    model_name: str = DEFAULT_MODEL,
    device: str | None = DEFAULT_DEVICE,
    download_root: str | None = DOWNLOAD_ROOT,
):
    global _CACHED_MODEL, _CACHED_MODEL_KEY

    key = (model_name, device, download_root)
    with _MODEL_LOCK:
        if _CACHED_MODEL is None or _CACHED_MODEL_KEY != key:
            if download_root:
                Path(download_root).mkdir(parents=True, exist_ok=True)
            _CACHED_MODEL = stable_whisper.load_model(
                model_name,
                device=device,
                download_root=download_root,
            )
            _CACHED_MODEL_KEY = key
        return _CACHED_MODEL


def run_alignment(
    audio_path: Path,
    lyrics_text: str,
    *,
    language: str = DEFAULT_LANGUAGE,
    model_name: str = DEFAULT_MODEL,
    device: str | None = DEFAULT_DEVICE,
    download_root: str | None = DOWNLOAD_ROOT,
):
    normalized_lyrics = normalize_lyrics_text(lyrics_text)
    if not normalized_lyrics:
        raise RuntimeError("Transcript is empty after removing blank lines.")

    model = get_model(model_name=model_name, device=device, download_root=download_root)
    result = model.align(
        str(audio_path),
        normalized_lyrics,
        language=language,
        original_split=True,
        regroup=False,
        verbose=False,
    )
    if result is None:
        raise RuntimeError("stable-ts returned no alignment result.")

    result.remove_no_word_segments()
    return result


def build_textgrid(result, output_path: Path) -> None:
    segment_entries: list[tuple[float, float, str]] = []
    word_entries: list[tuple[float, float, str]] = []

    for segment in result.segments:
        start = float(segment.start)
        end = float(segment.end)
        text_value = str(segment.text).strip()
        if end > start and text_value:
            segment_entries.append((start, end, text_value))

        for word in segment.words or []:
            word_start = float(word.start)
            word_end = float(word.end)
            word_text = str(word.word).strip()
            if word_end > word_start and word_text:
                word_entries.append((word_start, word_end, word_text))

    if segment_entries:
        max_time = max(end for _, end, _ in segment_entries)
    elif word_entries:
        max_time = max(end for _, end, _ in word_entries)
    else:
        max_time = 0.0

    tg = textgrid.Textgrid()
    tg.addTier(textgrid.IntervalTier("segments", segment_entries, minT=0.0, maxT=max_time))
    tg.addTier(textgrid.IntervalTier("words", word_entries, minT=0.0, maxT=max_time))
    tg.save(
        str(output_path),
        format="short_textgrid",
        includeBlankSpaces=True,
    )


def save_alignment_artifacts(result, output_stem: Path) -> AlignmentArtifacts:
    srt_path = output_stem.with_suffix(".srt")
    textgrid_path = output_stem.with_suffix(".TextGrid")

    result.to_srt_vtt(
        str(srt_path),
        segment_level=True,
        word_level=False,
    )
    build_textgrid(result, textgrid_path)

    return AlignmentArtifacts(
        srt_path=srt_path,
        textgrid_path=textgrid_path,
        segment_count=len(result.segments),
    )


def align_audio_to_outputs(
    audio_path: Path,
    lyrics_text: str,
    output_stem: Path,
    *,
    language: str = DEFAULT_LANGUAGE,
    model_name: str = DEFAULT_MODEL,
    device: str | None = DEFAULT_DEVICE,
    download_root: str | None = DOWNLOAD_ROOT,
) -> AlignmentArtifacts:
    result = run_alignment(
        audio_path,
        lyrics_text,
        language=language,
        model_name=model_name,
        device=device,
        download_root=download_root,
    )
    return save_alignment_artifacts(result, output_stem)

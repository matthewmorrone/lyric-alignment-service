from __future__ import annotations

from pathlib import Path

from align_core import (
    DEFAULT_DEVICE,
    DEFAULT_LANGUAGE,
    DEFAULT_MODEL,
    DOWNLOAD_ROOT,
    align_audio_to_outputs,
    discover_pairs,
    pretty_path,
    read_lyrics,
)


def run() -> int:
    root = Path.cwd()
    pairs, skipped_wavs = discover_pairs(root)

    print(f"Working directory: {root}")
    print(f"Found {len(pairs)} wav/txt pair(s).")
    for skipped_wav in skipped_wavs:
        print(f"  [skip] missing sibling .txt: {pretty_path(skipped_wav)}")

    if not pairs:
        return 0

    print(
        f"Loading stable-ts model '{DEFAULT_MODEL}'"
        + (f" on '{DEFAULT_DEVICE}'" if DEFAULT_DEVICE else "")
        + f" for language '{DEFAULT_LANGUAGE}'."
    )

    failures = 0
    for index, pair in enumerate(pairs, 1):
        print(f"[{index}/{len(pairs)}] {pretty_path(pair.wav_path)}")
        try:
            artifacts = align_audio_to_outputs(
                pair.wav_path,
                read_lyrics(pair.txt_path),
                pair.wav_path.with_suffix(""),
                language=DEFAULT_LANGUAGE,
                model_name=DEFAULT_MODEL,
                device=DEFAULT_DEVICE,
                download_root=DOWNLOAD_ROOT,
            )
            print(
                "  saved: "
                f"{pretty_path(artifacts.srt_path)} and "
                f"{pretty_path(artifacts.textgrid_path)} | "
                f"segments={artifacts.segment_count}"
            )
        except Exception as exc:
            failures += 1
            print(f"  [error] {pair.wav_path.stem}: {exc}")

    print(
        f"Complete. processed={len(pairs) - failures} failed={failures} output_dir={root}"
    )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run())

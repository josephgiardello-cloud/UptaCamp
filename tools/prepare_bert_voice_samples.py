from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _normalize_text(raw: str) -> str:
    text = " ".join(raw.strip().split())
    return text


def build_manifest(samples_dir: Path, out_csv: Path, speaker: str) -> dict[str, int]:
    wav_files = sorted(samples_dir.glob("*.wav"))
    kept = 0
    skipped = 0

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="|")
        for wav_path in wav_files:
            txt_path = wav_path.with_suffix(".txt")
            if not txt_path.exists():
                skipped += 1
                continue
            text = _normalize_text(txt_path.read_text(encoding="utf-8", errors="ignore"))
            if not text:
                skipped += 1
                continue
            writer.writerow([str(wav_path.resolve()), text, speaker])
            kept += 1

    return {"total_wavs": len(wav_files), "kept": kept, "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare a Piper/Coqui-style training manifest from curated Bert samples."
    )
    parser.add_argument(
        "--samples-dir",
        default="voice_samples/bert_downeast",
        help="Folder containing .wav + matching .txt transcripts",
    )
    parser.add_argument(
        "--out-csv",
        default="voice_samples/bert_downeast/metadata.csv",
        help="Output manifest file path",
    )
    parser.add_argument(
        "--speaker",
        default="bert",
        help="Speaker label to place in manifest",
    )
    args = parser.parse_args()

    samples_dir = Path(args.samples_dir)
    out_csv = Path(args.out_csv)

    if not samples_dir.exists():
        raise SystemExit(f"Samples folder does not exist: {samples_dir}")

    stats = build_manifest(samples_dir=samples_dir, out_csv=out_csv, speaker=args.speaker)

    report = {
        "samples_dir": str(samples_dir.resolve()),
        "out_csv": str(out_csv.resolve()),
        "speaker": args.speaker,
        **stats,
    }
    report_path = out_csv.with_suffix(".report.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=== Bert Voice Sample Prep ===")
    print(f"Samples dir: {report['samples_dir']}")
    print(f"Manifest: {report['out_csv']}")
    print(f"Kept: {report['kept']} | Skipped: {report['skipped']} | Total wavs: {report['total_wavs']}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()

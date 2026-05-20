from __future__ import annotations

import json
from pathlib import Path

from voice_manager import VoiceManager


def main() -> None:
    vm = VoiceManager(enabled=True)
    report = vm.get_local_prerequisites_report()

    print("=== Bert Offline Voice Prerequisites ===")
    print(f"Platform: {report.get('platform')}")
    print(f"Offline ready: {report.get('offline_ready')}")
    print(f"Configured backend: {report.get('backend')}")
    print(f"PowerShell available: {report.get('powershell_available')}")
    print(f"System.Speech available: {report.get('system_speech_available')}")

    local_ai = report.get("local_ai", {})
    print("Local AI backend:")
    print(f"- executable: {local_ai.get('executable')}")
    print(f"- executable_found: {local_ai.get('executable_found')}")
    print(f"- model_path: {local_ai.get('model_path')}")
    print(f"- model_found: {local_ai.get('model_found')}")
    print(f"- ready: {local_ai.get('ready')}")

    rvc = report.get("rvc", {})
    print("RVC conversion pass:")
    print(f"- enabled: {rvc.get('enabled')}")
    print(f"- executable: {rvc.get('executable')}")
    print(f"- executable_found: {rvc.get('executable_found')}")
    print(f"- model_path: {rvc.get('model_path')}")
    print(f"- model_found: {rvc.get('model_found')}")
    print(f"- index_path: {rvc.get('index_path')}")
    print(f"- index_found: {rvc.get('index_found')}")
    print(f"- ready: {rvc.get('ready')}")
    print(f"- pitch_shift: {rvc.get('pitch_shift')}")

    voices = report.get("voices", [])
    if voices:
        print("Installed voices:")
        for voice in voices:
            print(f"- {voice}")
    else:
        print("Installed voices: none detected")

    print("Recommended (local) voices:")
    for key, names in report.get("recommended", {}).items():
        print(f"- {key}: {', '.join(names)}")

    notes = report.get("notes", [])
    if notes:
        print("Notes:")
        for note in notes:
            print(f"- {note}")

    out_path = Path("bert_voice_prereq_report.json")
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved JSON report: {out_path}")


if __name__ == "__main__":
    main()

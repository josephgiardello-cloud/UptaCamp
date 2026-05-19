from __future__ import annotations

import argparse
import csv
import sqlite3


def export_rows(db_path: str, out_csv: str) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT event_id, match_id, phase, ai_level, state_hash,
                   candidate_json, selected_action, expected_value, created_at
            FROM bot_telemetry
            ORDER BY created_at DESC
            """
        ).fetchall()
    finally:
        conn.close()

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "event_id",
                "match_id",
                "phase",
                "ai_level",
                "state_hash",
                "candidate_json",
                "selected_action",
                "expected_value",
                "created_at",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["event_id"],
                    row["match_id"],
                    row["phase"],
                    row["ai_level"],
                    row["state_hash"],
                    row["candidate_json"],
                    row["selected_action"],
                    row["expected_value"],
                    row["created_at"],
                ]
            )
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export bot decision telemetry to CSV")
    parser.add_argument("--db", default="online_state.db")
    parser.add_argument("--out", default="bot_telemetry.csv")
    args = parser.parse_args()

    count = export_rows(args.db, args.out)
    print(f"exported {count} rows to {args.out}")


if __name__ == "__main__":
    main()

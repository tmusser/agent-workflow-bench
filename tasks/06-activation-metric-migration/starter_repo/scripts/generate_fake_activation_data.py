from __future__ import annotations

import argparse
from pathlib import Path

USERS_CSV = """user_id,signup_at,user_type,is_test_account,plan_at_signup,current_plan,cancelled_at,region,acquisition_channel
P001,2026-01-05T10:00:00,external,false,trial,trial,,us,organic
P002,2026-01-08T09:00:00,external,false,trial,trial,,us,paid
P003,2026-01-20T14:00:00,external,false,trial,trial,,eu,partner
P004,2026-02-01T11:00:00,external,false,trial,trial,,us,organic
P005,2026-02-10T12:00:00,external,false,trial,trial,,eu,paid
"""

EVENTS_CSV = """event_id,user_id,event_at,event_name,event_source
E001,P001,2026-01-06T10:00:00,activation_completed,app
E002,P003,2026-01-24T14:00:00,activation_completed,app
E003,P004,2026-02-03T11:00:00,activation_completed,app
"""

LEGACY_EXPECTED_CSV = """month,definition_version,eligible_users,activated_users,activation_rate
2026-01,v1,3,2,0.666667
2026-02,v1,2,1,0.5
"""


def _write_fixture(out_dir: Path, name: str, content: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / name).write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the public activation fixtures.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    _ = args.seed  # Reserved for future fixture variations.

    _write_fixture(out_dir, "users.csv", USERS_CSV)
    _write_fixture(out_dir, "events.csv", EVENTS_CSV)
    _write_fixture(out_dir, "legacy_expected.csv", LEGACY_EXPECTED_CSV)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

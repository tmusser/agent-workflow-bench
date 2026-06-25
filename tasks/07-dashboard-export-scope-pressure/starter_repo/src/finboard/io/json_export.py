from __future__ import annotations

import json
from collections.abc import Iterable, Mapping


def render_json_rows(rows: Iterable[Mapping[str, object]]) -> str:
    return json.dumps(list(rows), indent=2) + "\n"

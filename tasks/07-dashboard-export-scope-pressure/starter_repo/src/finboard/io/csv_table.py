from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Mapping


def render_csv_table(rows: Iterable[Mapping[str, object]], columns: list[str]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()

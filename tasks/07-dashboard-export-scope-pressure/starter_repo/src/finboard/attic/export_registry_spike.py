from __future__ import annotations


class BaseExporter:
    def export(self, report_id: str):  # pragma: no cover - historical spike
        raise NotImplementedError


class ExportRegistry:
    def __init__(self) -> None:  # pragma: no cover - historical spike
        self._exporters: dict[str, BaseExporter] = {}

    def register(self, report_id: str, exporter: BaseExporter) -> None:  # pragma: no cover - historical spike
        self._exporters[report_id] = exporter

    def get(self, report_id: str) -> BaseExporter:  # pragma: no cover - historical spike
        return self._exporters[report_id]

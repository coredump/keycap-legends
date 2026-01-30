# SPDX-License-Identifier: MIT

import tomllib
from pathlib import Path

from models import Config, LegendEntry, LegendSettings, StepFileConfig


def load_config(path: Path | str = "config.toml") -> Config:
    """Load configuration from a TOML file."""
    path = Path(path)
    with path.open("rb") as f:
        data = tomllib.load(f)

    # Parse settings
    settings_data = data.get("settings", {})
    settings = LegendSettings(
        font=settings_data.get("font", "Rajdhani"),
        primary_font_size=settings_data.get("primary_font_size", 8),
        secondary_font_size=settings_data.get("secondary_font_size", 6),
        tertiary_font_size=settings_data.get("tertiary_font_size", 5),
        legend_gap=settings_data.get("legend_gap", 0.0),
        vertical_shift=settings_data.get("vertical_shift", 0.0),
        tertiary_x_offset=settings_data.get("tertiary_x_offset", -5.0),
    )

    # Parse step files
    step_files: dict[str, StepFileConfig] = {}
    for name, step_data in data.get("step_files", {}).items():
        if isinstance(step_data, str):
            step_files[name] = StepFileConfig(path=step_data)
        else:
            step_files[name] = StepFileConfig(
                path=step_data["path"],
                rotation=step_data.get("rotation", 0),
            )

    # Parse legends
    legends: dict[str, list[LegendEntry]] = {}
    for row_name, row_legends in data.get("legends", {}).items():
        legends[row_name] = []
        for entry in row_legends:
            legends[row_name].append(
                LegendEntry(
                    primary=entry.get("primary"),
                    secondary=entry.get("secondary"),
                    mirror_x=entry.get("mirror_x", False),
                    primary_font=entry.get("primary_font"),
                    secondary_font=entry.get("secondary_font"),
                    tertiary=entry.get("tertiary"),
                    tertiary_font=entry.get("tertiary_font"),
                )
            )

    return Config(settings=settings, step_files=step_files, legends=legends)

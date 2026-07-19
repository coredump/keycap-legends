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
        tertiary_x_offset=settings_data.get("tertiary_x_offset", -5.0),
        tertiary_y_offset=settings_data.get("tertiary_y_offset", 0.0),
        quaternary_font_size=settings_data.get("quaternary_font_size", 3.5),
        quaternary_x_offset=settings_data.get("quaternary_x_offset", -3.3),
        quaternary_y_offset=settings_data.get("quaternary_y_offset", -3.3),
        secondary_x_offset=settings_data.get("secondary_x_offset", -3.3),
        secondary_y_offset=settings_data.get("secondary_y_offset", -3.3),
        primary_x_offset=settings_data.get("primary_x_offset", 0.0),
        primary_y_offset=settings_data.get("primary_y_offset", 0.0),
        bold_offset=settings_data.get("bold_offset", 0.0),
        max_carve_depth=settings_data.get("max_carve_depth", 0.8),
        body_filament=settings_data.get("body_filament", 1),
        legend_filament=settings_data.get("legend_filament", 2),
        stem_filament=settings_data.get("stem_filament", 1),
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
                has_stem=step_data.get("has_stem", False),
                stl=step_data.get("stl"),
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
                    name=entry.get("name"),
                    mirror_x=entry.get("mirror_x", False),
                    primary_font=entry.get("primary_font"),
                    primary_font_size=entry.get("primary_font_size"),
                    primary_x_offset=entry.get("primary_x_offset"),
                    primary_y_offset=entry.get("primary_y_offset"),
                    secondary_font_size=entry.get("secondary_font_size"),
                    secondary_x_offset=entry.get("secondary_x_offset"),
                    secondary_y_offset=entry.get("secondary_y_offset"),
                    secondary_font=entry.get("secondary_font"),
                    tertiary=entry.get("tertiary"),
                    tertiary_font=entry.get("tertiary_font"),
                    quaternary=entry.get("quaternary"),
                    quaternary_font=entry.get("quaternary_font"),
                    quaternary_font_size=entry.get("quaternary_font_size"),
                )
            )

    return Config(settings=settings, step_files=step_files, legends=legends)

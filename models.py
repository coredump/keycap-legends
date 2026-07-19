# SPDX-License-Identifier: MIT

from dataclasses import dataclass, field


@dataclass
class LegendEntry:
    """Configuration for a single keycap legend."""

    primary: str | None = None
    secondary: str | None = None
    name: str | None = None
    mirror_x: bool = False
    primary_font: str | None = None
    primary_font_size: float | None = None
    primary_x_offset: float | None = None
    primary_y_offset: float | None = None
    secondary_font_size: float | None = None
    secondary_x_offset: float | None = None
    secondary_y_offset: float | None = None
    secondary_font: str | None = None
    tertiary: str | None = None
    tertiary_font: str | None = None
    quaternary: str | None = None
    quaternary_font: str | None = None
    quaternary_font_size: float | None = None


@dataclass
class StepFileConfig:
    """Configuration for a STEP file source."""

    path: str
    rotation: int = 0
    has_stem: bool = False
    stl: str | None = None


@dataclass
class LegendSettings:
    """Global settings for legend generation."""

    font: str = "Rajdhani"
    primary_font_size: int = 8
    secondary_font_size: float = 6
    tertiary_font_size: int = 5
    tertiary_x_offset: float = -5.0
    tertiary_y_offset: float = 0.0
    quaternary_font_size: float = 3.5
    quaternary_x_offset: float = -3.3
    quaternary_y_offset: float = -3.3
    secondary_x_offset: float = -3.3
    secondary_y_offset: float = -3.3
    primary_x_offset: float = 0.0
    primary_y_offset: float = 0.0
    bold_offset: float = 0.0
    max_carve_depth: float = 0.8
    body_filament: int = 1
    legend_filament: int = 2
    stem_filament: int = 1


@dataclass
class Config:
    """Complete configuration for keycap generation."""

    settings: LegendSettings = field(default_factory=LegendSettings)
    step_files: dict[str, StepFileConfig] = field(default_factory=dict)
    legends: dict[str, list[LegendEntry]] = field(default_factory=dict)

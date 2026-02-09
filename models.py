# SPDX-License-Identifier: MIT

from dataclasses import dataclass, field


@dataclass
class LegendEntry:
    """Configuration for a single keycap legend."""

    primary: str | None = None
    secondary: str | None = None
    mirror_x: bool = False
    primary_font: str | None = None
    secondary_font: str | None = None
    tertiary: str | None = None
    tertiary_font: str | None = None


@dataclass
class StepFileConfig:
    """Configuration for a STEP file source."""

    path: str
    rotation: int = 0
    has_stem: bool = False


@dataclass
class LegendSettings:
    """Global settings for legend generation."""

    font: str = "Rajdhani"
    primary_font_size: int = 8
    secondary_font_size: int = 6
    tertiary_font_size: int = 5
    legend_gap: float = 0.0
    vertical_shift: float = 0.0
    tertiary_x_offset: float = -5.0


@dataclass
class Config:
    """Complete configuration for keycap generation."""

    settings: LegendSettings = field(default_factory=LegendSettings)
    step_files: dict[str, StepFileConfig] = field(default_factory=dict)
    legends: dict[str, list[LegendEntry]] = field(default_factory=dict)

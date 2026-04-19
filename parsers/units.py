"""单位换算与温度展示。"""
from __future__ import annotations


def c_to_f(celsius: float | None) -> float | None:
    if celsius is None:
        return None
    return celsius * 9.0 / 5.0 + 32.0


def fmt_temp_cf(celsius: float | None, missing: str = "    --") -> str:
    """格式化为 '22.0°C / 71.6°F'。None 返回占位 missing。"""
    if celsius is None:
        return missing
    return f"{celsius:>5.1f}°C / {c_to_f(celsius):>5.1f}°F"

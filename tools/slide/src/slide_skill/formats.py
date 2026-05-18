"""Canvas format definitions for slide projects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanvasFormat:
    name: str
    width: int
    height: int
    ratio: str
    use_case: str
    pptx_width_in: float
    pptx_height_in: float


CANVAS_FORMATS: dict[str, CanvasFormat] = {
    "ppt169": CanvasFormat("ppt169", 1280, 720, "16:9", "Business presentations (widescreen)", 13.333333, 7.5),
    "ppt43": CanvasFormat("ppt43", 1024, 768, "4:3", "Traditional projectors", 10.0, 7.5),
    "square": CanvasFormat("square", 1080, 1080, "1:1", "Square social posts (Instagram)", 10.0, 10.0),
    "story": CanvasFormat("story", 1080, 1920, "9:16", "Phone stories (Instagram/Snapchat)", 7.5, 13.333333),
    "xhs": CanvasFormat("xhs", 1242, 1660, "3:4", "Xiaohongshu / RED posts", 7.5, 10.024155),
    "wechat": CanvasFormat("wechat", 1080, 1080, "1:1", "WeChat Moments (square)", 10.0, 10.0),
    "a4": CanvasFormat("a4", 1123, 794, "√2:1", "A4 document pages", 10.0, 7.071),
    "letter": CanvasFormat("letter", 1056, 816, "~1.29:1", "US Letter document pages", 10.0, 7.727),
    "ipad": CanvasFormat("ipad", 1536, 2048, "3:4", "iPad portrait", 7.5, 10.0),
    "ultrawide": CanvasFormat("ultrawide", 2560, 1080, "21:9", "Ultrawide presentations", 18.0, 7.5),
    "banner": CanvasFormat("banner", 1920, 1080, "16:9", "Landscape banners", 13.333333, 7.5),
}


def get_format(name: str) -> CanvasFormat:
    try:
        return CANVAS_FORMATS[name]
    except KeyError as exc:
        valid = ", ".join(sorted(CANVAS_FORMATS))
        raise ValueError(f"Unknown format '{name}'. Valid formats: {valid}") from exc

import json
import os
from typing import Any, Dict, List, Tuple, Optional


def _validate_polygon(points: Any) -> Optional[List[Tuple[int, int]]]:
    if not isinstance(points, list) or len(points) < 3:
        return None
    validated: List[Tuple[int, int]] = []
    for p in points:
        if (
            isinstance(p, (list, tuple))
            and len(p) == 2
            and isinstance(p[0], (int, float))
            and isinstance(p[1], (int, float))
        ):
            validated.append((int(p[0]), int(p[1])))
        else:
            return None
    return validated


def load_runtime_config(config_path: str) -> Dict[str, Any]:
    """Load runtime configuration from JSON.

    Expected schema (all fields optional, validated when used):
      {
        "video_path": "path/to/video.mp4",
        "mask_path": "path/to/mask.png",
        "polygon_points": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]],
        "serial": {
          "port": "COM3",
          "baud": 115200,
          "timeout": 0.1
        },
        "esp32": {
          "ip": "192.168.1.50",
          "port": 80
        }
      }
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return data
    except FileNotFoundError:
        return {}
    except Exception:
        # Fail closed with empty config if malformed
        return {}


def get_config_value(cfg: Dict[str, Any], key_path: List[str], default: Any) -> Any:
    node: Any = cfg
    for key in key_path:
        if isinstance(node, dict) and key in node:
            node = node[key]
        else:
            return default
    return node


def get_polygon_from_config(cfg: Dict[str, Any], default_points: List[Tuple[int, int]]):
    pts = get_config_value(cfg, ["polygon_points"], None)
    validated = _validate_polygon(pts)
    return validated if validated is not None else default_points



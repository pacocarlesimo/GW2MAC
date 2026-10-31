"""Persistent user configuration.

Stored as JSON in ``~/Library/Application Support/GW2Mac/config.json``.
Unknown keys are ignored and missing keys take their default, so the file keeps
working across versions.
"""
import json
from dataclasses import asdict, dataclass, field

from paths import CONFIG_PATH
from ui import warn


@dataclass
class Config:
    #: Render at native Retina resolution: sharper, but much heavier on the GPU.
    retina: bool = False
    #: Show Apple's Metal Performance HUD (fps, frame time) in game.
    hud: bool = False
    #: Extra command-line arguments for Gw2-64.exe.
    game_args: list = field(default_factory=list)

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        if not CONFIG_PATH.exists():
            return cfg
        try:
            data = json.loads(CONFIG_PATH.read_text())
        except (OSError, json.JSONDecodeError):
            warn("config.json could not be read, using defaults")
            return cfg
        if "gw2_args" in data and "game_args" not in data:  # pre-release name
            data["game_args"] = data["gw2_args"]
        for key, value in data.items():
            if key in cls.__dataclass_fields__:
                setattr(cfg, key, value)
        if not isinstance(cfg.game_args, list):
            cfg.game_args = []
        return cfg

    def save(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2))

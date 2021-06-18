from dataclasses import dataclass
import yaml
from pathlib import Path
from typing import Dict, List, Union, Any, TypeVar, Type


@dataclass()
class Filter:
    jql: str


@dataclass()
class Board:
    filter: Filter


@dataclass()
class Config:
    cert_path: str
    board: Board
    jira_base_url: str
    user: str
    token: str


def encode(obj: Any) -> Union[Dict, List]:
    if isinstance(obj, dict):
        return { k: encode(v) for k, v in obj.items() }
    elif hasattr(obj, "_ast"):
        return encode(obj._ast())
    elif not isinstance(obj, str) and hasattr(obj, "__iter__"):
        return [ encode(v) for v in obj ]
    elif hasattr(obj, "__dict__"):
        return {
            k: encode(v)
            for k, v in obj.__dict__.items()
            if not callable(v) and not k.startswith('_')
        }
    else:
        return obj


T = TypeVar("T")


def decode(conf_dict: Dict, cls: Type[T]) -> T:
    from typing import get_type_hints
    hints = get_type_hints(cls)
    if not hints:
        return cls(conf_dict)
    arguments = {}
    for name in hints.keys():
        if name in conf_dict:
            arguments[name] = decode(conf_dict[name], hints[name])
    return cls(**arguments)


def load_configuration(path: Path) -> Config:
    with path.open("r") as file:
        return decode(yaml.safe_load(file), Config)

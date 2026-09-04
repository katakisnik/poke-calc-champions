"""A persistent subprocess wrapper around oracle/oracle.js for differential
testing: feed it the same (attacker, defender, move, field) JSON our engine
was built from, and compare its 16 damage rolls against ours."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional

ORACLE_DIR = Path(__file__).parent.parent.parent / "oracle"
ORACLE_SCRIPT = ORACLE_DIR / "oracle.js"


class OracleClient:
    def __init__(self):
        if not ORACLE_SCRIPT.exists():
            raise FileNotFoundError(f"oracle.js not found at {ORACLE_SCRIPT}")
        self.proc = subprocess.Popen(
            ["node", str(ORACLE_SCRIPT)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def query(self, attacker: dict, defender: dict, move: dict, field: Optional[dict] = None) -> dict:
        req = {"attacker": attacker, "defender": defender, "move": move, "field": field or {}}
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self.proc.stdin.write(json.dumps(req) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            err = self.proc.stderr.read() if self.proc.stderr else ""
            raise RuntimeError(f"oracle process produced no output; stderr: {err}")
        return json.loads(line)

    def close(self):
        if self.proc.stdin:
            self.proc.stdin.close()
        self.proc.wait(timeout=5)


def mon_spec_to_oracle(mon_kwargs: dict) -> dict:
    """Translate build_mon-style kwargs into the oracle's Pokemon JSON shape."""
    spec = {"name": mon_kwargs["species"]}
    if "ability" in mon_kwargs and mon_kwargs["ability"]:
        spec["ability"] = mon_kwargs["ability"]
    if "item" in mon_kwargs and mon_kwargs["item"]:
        spec["item"] = mon_kwargs["item"]
    if "nature" in mon_kwargs and mon_kwargs["nature"]:
        spec["nature"] = mon_kwargs["nature"]
    if "sp" in mon_kwargs and mon_kwargs["sp"]:
        spec["evs"] = mon_kwargs["sp"]
    if "status" in mon_kwargs and mon_kwargs["status"]:
        spec["status"] = mon_kwargs["status"]
    if "boosts" in mon_kwargs and mon_kwargs["boosts"]:
        spec["boosts"] = mon_kwargs["boosts"]
    if mon_kwargs.get("current_hp_fraction", 1.0) != 1.0:
        spec["curHP"] = round(mon_kwargs["current_hp_fraction"] * 100)
    return spec


def field_to_oracle(field_kwargs: dict) -> dict:
    spec = {"gameType": field_kwargs.get("game_type", "Singles")}
    if field_kwargs.get("weather"):
        spec["weather"] = field_kwargs["weather"]
    if field_kwargs.get("terrain"):
        spec["terrain"] = field_kwargs["terrain"]
    if field_kwargs.get("is_gravity"):
        spec["isGravity"] = True
    attacker_side = {}
    defender_side = {}
    if field_kwargs.get("defender_protected"):
        defender_side["isProtected"] = True
    if field_kwargs.get("defender_reflect"):
        defender_side["isReflect"] = True
    if field_kwargs.get("defender_light_screen"):
        defender_side["isLightScreen"] = True
    if field_kwargs.get("defender_aurora_veil"):
        defender_side["isAuroraVeil"] = True
    if field_kwargs.get("attacker_helping_hand"):
        attacker_side["isHelpingHand"] = True
    if attacker_side:
        spec["attackerSide"] = attacker_side
    if defender_side:
        spec["defenderSide"] = defender_side
    return spec

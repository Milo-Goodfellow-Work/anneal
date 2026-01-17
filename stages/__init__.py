"""
Anneal Stages Package

All stage functions take a ctx dict and operate procedurally.

2-Stage Pipeline (v2.0):
- Stage 1: Co-Generation (cogeneration.py)
- Stage 2: Proving (proving.py)
"""
from stages.scaffold import autogen_scaffold_and_lockdown
from stages.cogeneration import run_stage_cogeneration
from stages.proving import run_stage_proving

__all__ = [
    "autogen_scaffold_and_lockdown",
    "run_stage_cogeneration",
    "run_stage_proving",
]

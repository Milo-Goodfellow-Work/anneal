"""
Anneal Stages Package

All stage functions take a ctx dict and operate procedurally.
"""
from stages.scaffold import autogen_scaffold_and_lockdown
from stages.translation import run_stage_translation
from stages.equivalence import run_stage_equivalence
from stages.specification import run_stage_specification
from stages.hardening import run_stage_hardening
from stages.verification import run_stage_verification

__all__ = [
    "autogen_scaffold_and_lockdown",
    "run_stage_translation",
    "run_stage_equivalence", 
    "run_stage_specification",
    "run_stage_hardening",
    "run_stage_verification",
]

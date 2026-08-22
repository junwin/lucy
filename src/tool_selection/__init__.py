"""Tool selection pipeline package (issue #126, design doc §5).

Public API — the three symbols the design doc mandates (§5):

- ``ToolSelectionPipeline`` — the orchestrator; ``resolve()`` wires the
  stage helpers (allowed → all_tools → eligible → required → validate →
  prompt_based → finalize → budget) and records every stage in ``meta``.
- ``ToolSelection`` — the frozen result dataclass the pipeline returns
  (pure data, easy to assert in tests).
- ``ToolSelectionError`` — the single typed error the pipeline raises
  (codes: ``required_not_permissioned``, ``required_not_registered``,
  ``budget_exceeded``).

Import-clean by construction: ``errors`` and ``selection`` are stdlib-only
leaf modules with no intra-package imports, and ``pipeline`` imports only
within the package (``.selection`` and ``.errors``). Importing this package
therefore never pulls in (or is pulled in by) any other part of the repo,
so there is no circular-import risk.
"""

from .errors import ToolSelectionError
from .pipeline import ToolSelection, ToolSelectionPipeline

__all__ = [
    "ToolSelection",
    "ToolSelectionPipeline",
    "ToolSelectionError",
]

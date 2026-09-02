"""generate_doc handler — HandlerV2-compliant, callable by agents via FCP.

Generates documentation for a Python module by sending all .py files to an LLM
with an instruction template. Supports full (12-section) and mini (compact)
doc types, incremental skip-if-unchanged via hash sidecar, and custom instructions.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config_manager import ConfigManager
from src.handlers.handler_v2 import HandlerV2
from galet.interface import LLMApi
from galet.router_api import RouterApi
from galet.settings import Settings

logger = logging.getLogger(__name__)


class GenerateDocHandler(HandlerV2):
    """Handler for generating module documentation via LLM.

    Invoked by agents via FunctionCallingProcessor.
    """

    NAME = "generate_doc"

    def __init__(self, config: ConfigManager):
        self.config = config
        external_roots = config.get("external_roots", {})
        self.repo_root = Path(external_roots.get("repo_lucy", "."))
        self.llm_api: LLMApi = RouterApi(
            settings=Settings(
                credential_path=config.get("credential_path"),
                ollama_base_url=config.get("ollama_base_url"),
            )
        )

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": (
                "Generate documentation for a Python module. Reads all .py files "
                "in the module, sends them to an LLM with an instruction template, "
                "and saves the resulting .md file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "module_path": {
                        "type": "string",
                        "description": (
                            "Path to the module directory relative to the repo "
                            "root (e.g. 'src/handlers')."
                        ),
                    },
                    "output_path": {
                        "type": "string",
                        "description": (
                            "Where to save the generated .md file relative to the "
                            "repo root (e.g. 'docs/minidoc/src_handlers.md')."
                        ),
                    },
                    "doc_type": {
                        "type": "string",
                        "enum": ["full", "mini"],
                        "description": (
                            "Documentation type: 'full' produces a thorough "
                            "12-section doc, 'mini' produces a compact reference doc."
                        ),
                        "default": "full",
                    },
                    "instructions": {
                        "type": "string",
                        "description": (
                            "Custom LLM instructions. If provided, overrides the "
                            "default template for the chosen doc_type."
                        ),
                        "default": "",
                    },
                    "force": {
                        "type": "boolean",
                        "description": (
                            "If true, always regenerate even if the source files "
                            "haven't changed."
                        ),
                        "default": False,
                    },
                    "model": {
                        "type": "string",
                        "description": "LLM model to use for generation.",
                        "default": "gpt-4o-mini",
                    },
                },
                "required": [
                    "module_path",
                    "output_path",
                    "doc_type",
                    "instructions",
                    "force",
                    "model",
                ],
                "additionalProperties": False,
            },
            "strict": True,
        }

    @classmethod
    def result_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "tool": {"type": "string"},
                "path": {"type": "string"},
                "content": {"type": "string"},
                "files_read": {"type": "array", "items": {"type": "string"}},
                "doc_type": {"type": "string"},
                "skipped": {"type": "boolean"},
                "error": {"type": "string"},
            },
            "required": ["ok", "tool"],
            "additionalProperties": True,
        }

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------

    def execute(
        self, args: Dict[str, Any], *, account_name: str = "auto", **context
    ) -> Dict[str, Any]:
        """Generate documentation for a module.

        Args:
            args: Tool arguments (module_path, output_path, doc_type, etc.)
            account_name: Injected by FCP (unused but required by interface).

        Returns:
            Result dict.
        """
        module_path = args.get("module_path", "")
        output_path = args.get("output_path", "")
        doc_type = args.get("doc_type", "full")
        instructions = args.get("instructions", "")
        force = bool(args.get("force", False))
        model = args.get("model", "gpt-4o-mini")

        # --- validate required args ---
        if not module_path:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "module_path is required",
            }
        if not output_path:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "output_path is required",
            }

        # --- 1. Resolve and glob ---
        module_dir = self.repo_root / module_path
        if not module_dir.is_dir():
            return {
                "ok": False,
                "tool": self.NAME,
                "error": f"Module path not found: {module_path}",
            }

        py_files: List[Path] = sorted(
            [f for f in module_dir.rglob("*.py") if "__pycache__" not in str(f)]
        )
        if not py_files:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": f"No .py files found in {module_path}",
            }

        # --- 2. Read files ---
        files: Dict[str, str] = {}
        for f in py_files:
            rel = str(f.relative_to(self.repo_root)).replace("\\", "/")
            files[rel] = f.read_text()

        # --- 3. Hash + skip-if-unchanged ---
        content_blob = "".join(files[k] for k in sorted(files))
        current_hash = hashlib.sha256(content_blob.encode()).hexdigest()

        if not force:
            stored_hash = self._read_hash(output_path)
            if stored_hash == current_hash:
                logger.info(
                    "generate_doc: skipping %s (unchanged, hash=%s...)",
                    module_path,
                    current_hash[:12],
                )
                return {
                    "ok": True,
                    "tool": self.NAME,
                    "path": output_path,
                    "skipped": True,
                    "doc_type": doc_type,
                    "files_read": sorted(files.keys()),
                }

        # --- 4. Load instruction template ---
        template = self._load_template(doc_type, instructions)

        # --- 5. Build prompt ---
        prompt = self._build_prompt(template, module_path, files)

        # --- 6. Call LLM ---
        logger.info(
            "generate_doc: calling LLM for %s (%d files, model=%s)",
            module_path,
            len(files),
            model,
        )
        try:
            response = self.llm_api.create_response(
                model=model,
                input=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            output_text = response.output_text.strip()
        except Exception as exc:
            logger.exception("generate_doc: LLM call failed for %s", module_path)
            return {
                "ok": False,
                "tool": self.NAME,
                "error": f"LLM call failed: {type(exc).__name__}: {exc}",
            }

        if not output_text:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "LLM returned empty output",
            }

        # --- 7. Save ---
        out_file = self.repo_root / output_path
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(output_text)
        logger.info("generate_doc: saved %s (%d chars)", output_path, len(output_text))

        # --- 8. Save hash ---
        self._save_hash(output_path, current_hash)

        return {
            "ok": True,
            "tool": self.NAME,
            "path": output_path,
            "content": output_text,
            "files_read": sorted(files.keys()),
            "doc_type": doc_type,
            "skipped": False,
        }

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _load_template(self, doc_type: str, custom_instructions: str) -> str:
        """Load the instruction template for the given doc_type."""
        if custom_instructions:
            logger.info("generate_doc: using custom instructions")
            return custom_instructions

        template_name = (
            "minidoc_instructions.md"
            if doc_type == "mini"
            else "minidoc_general_instructions.md"
        )
        template_path = self.repo_root / "docs" / template_name

        if not template_path.is_file():
            logger.warning(
                "generate_doc: template not found at %s, using built-in fallback",
                template_path,
            )
            return _FALLBACK_TEMPLATE

        return template_path.read_text()

    @staticmethod
    def _build_prompt(
        template: str, module_path: str, files: Dict[str, str]
    ) -> str:
        """Build the full LLM prompt: template + module path + file contents."""
        parts: List[str] = [template, "", f"Module path: `{module_path}`", ""]
        parts.append("Here are the source files:")
        parts.append("")

        for path in sorted(files):
            parts.append(f"### {path}")
            parts.append("```python")
            parts.append(files[path])
            parts.append("```")
            parts.append("")

        return "\n".join(parts)

    def _hash_path(self, output_path: str) -> Path:
        """Return the sidecar hash file path."""
        return self.repo_root / (output_path + ".hash")

    def _read_hash(self, output_path: str) -> Optional[str]:
        """Read the stored hash for an output path, or None if missing."""
        hp = self._hash_path(output_path)
        if hp.is_file():
            return hp.read_text().strip()
        return None

    def _save_hash(self, output_path: str, hash_value: str) -> None:
        """Write the hash sidecar file."""
        hp = self._hash_path(output_path)
        hp.parent.mkdir(parents=True, exist_ok=True)
        hp.write_text(hash_value)


# ------------------------------------------------------------------
# Fallback template (if the file-based templates are missing)
# ------------------------------------------------------------------

_FALLBACK_TEMPLATE = """Please look at the module name below.

Analyse every `.py` file in the module and produce a thorough `.md` document.

The output must include:
- YAML front matter with tags
- Summary
- Architecture & Design
- Key Classes table
- Source Files table
- Dependencies (stdlib, third-party, internal)
- Configuration / Settings
- Exceptions
- Module-Level Constants
- Methods (by class)

Save as a single .md file."""

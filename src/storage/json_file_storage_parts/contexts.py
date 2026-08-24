"""Context/skill implementation for JsonFileStorage (mixin part).

Provides the ContextsMixin class: context + skill methods that operate on a
JsonFileStorage instance (self.storage_paths, self._load_json,
self._ensure_dir, self._atomic_write_text).
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.storage.models import Context, Skill

import yaml


def _now_utc() -> datetime:
    """Return an offset-aware datetime in UTC."""
    return datetime.now(timezone.utc)


def _parse_dt_utc(dt_str: str) -> datetime:
    """
    Parse ISO timestamps from storage into an aware UTC datetime.

    Accepts:
      - "2023-06-14T21:58:27.803580Z"
      - "2023-06-14T21:58:27.803580+00:00"
      - naive "2023-06-14T21:58:27.803580" (assumed UTC)
    """
    if not dt_str:
        return _now_utc()

    s = str(dt_str).strip()
    # Support trailing "Z" (Zulu time)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    dt = datetime.fromisoformat(s)

    # If naive, assume UTC; if aware, normalize to UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt


def _parse_context_frontmatter(
    fm: Optional[Dict[str, Any]],
) -> Tuple[Optional[str], List[str], List[str], List[str], Dict[str, Any]]:
    """Split a context frontmatter dict into typed fields + catch-all extra.

    Known typed keys (tag, imports, mandatory_tools, search_namespaces) are
    extracted leniently; malformed values (e.g. a non-list for a list field)
    are preserved in ``extra`` so nothing is lost on round-trip. ``text`` and
    ``updated_at`` are handled by the caller and are never put into ``extra``.
    """
    tag: Optional[str] = None
    imports: List[str] = []
    mandatory_tools: List[str] = []
    search_namespaces: List[str] = []
    extra: Dict[str, Any] = {}

    for key, value in (fm or {}).items():
        if key == "tag":
            if isinstance(value, str):
                tag = value
            else:
                extra[key] = value
        elif key == "imports":
            if isinstance(value, list):
                imports = [v for v in value if isinstance(v, str)]
            else:
                extra[key] = value
        elif key == "mandatory_tools":
            if isinstance(value, list):
                mandatory_tools = [v for v in value if isinstance(v, str)]
            else:
                extra[key] = value
        elif key == "search_namespaces":
            if isinstance(value, list):
                search_namespaces = [v for v in value if isinstance(v, str)]
            else:
                extra[key] = value
        elif key in ("text", "updated_at"):
            # Handled by the caller (body / datetime parsing).
            pass
        else:
            extra[key] = value

    return tag, imports, mandatory_tools, search_namespaces, extra


class ContextsMixin:
    """Context + skill methods extracted from JsonFileStorage.

    Mixin: relies on self.storage_paths, self._load_json, self._ensure_dir,
    and self._atomic_write_text provided by the composing class.
    """

    # ----------------------------------------------------------------------
    # CONTEXT / WHITEBOARD
    # ----------------------------------------------------------------------

    def get_context(self, account_name: str, context_id: str) -> Optional[Context]:
        """Load a context from Markdown (.md) with YAML frontmatter.

        Frontmatter keys map onto the persisted Context fields (tag, imports,
        mandatory_tools, search_namespaces, updated_at); any other keys land
        in ``extra`` (catch-all). The Markdown body becomes ``text``.
        ``updated_at`` is sourced from frontmatter if present, otherwise from
        the file's mtime. Import resolution (``resolved_skills`` /
        ``missing_imports``) is performed by the storage layer (see #120).
        """
        path = self.storage_paths.contexts / account_name / f"{context_id}.md"
        if not path.exists():
            return None

        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            logging.error("Failed to read context file %s: %s", path, e)
            return None

        fm = {}
        body = ""
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)\Z", text, re.S)
        if m:
            fm_text = m.group(1)
            body = m.group(2)
            try:
                loaded = yaml.safe_load(fm_text)
                if isinstance(loaded, dict):
                    fm = loaded
                else:
                    fm = {}
            except Exception as e:
                logging.warning("Failed to parse YAML frontmatter for %s: %s", path, e)
                fm = {}
        else:
            # No frontmatter; treat whole file as body
            body = text

        tag, imports, mandatory_tools, search_namespaces, extra = _parse_context_frontmatter(fm)

        # Determine updated_at: prefer frontmatter 'updated_at' if present; else mtime
        updated_at = None
        if "updated_at" in fm:
            try:
                updated_at = _parse_dt_utc(fm.get("updated_at") or "")
            except Exception:
                updated_at = None

        if updated_at is None:
            try:
                mtime = path.stat().st_mtime
                updated_at = datetime.fromtimestamp(mtime, tz=timezone.utc)
            except Exception:
                updated_at = _now_utc()

        ctx = Context(
            id=context_id,
            account_name=account_name,
            tag=tag,
            imports=imports,
            mandatory_tools=mandatory_tools,
            search_namespaces=search_namespaces,
            updated_at=updated_at,
            text=body,
            extra=extra,
        )
        # Import resolution (single-level, v1): populate resolved_skills /
        # missing_imports. Missing imports do not fail the load.
        self._resolve_context_imports(ctx, account_name)
        return ctx

    def _resolve_context_imports(self, ctx: Context, account_name: str) -> None:
        """Resolve ``ctx.imports`` (single-level only) into resolved_skills.

        For each import name, in order: load the skill via ``get_skill()``.
        Found skills are appended to ``ctx.resolved_skills`` (their
        ``mandatory_tools`` feed the computed ``required_tools`` property);
        imports that could not be found are recorded in
        ``ctx.missing_imports``. Non-string / empty entries are skipped.
        No recursion (v1); skill composition is a later release.
        """
        resolved: List[Skill] = []
        missing: List[str] = []
        for skill_name in ctx.imports:
            if not isinstance(skill_name, str) or not skill_name.strip():
                continue
            skill_name = skill_name.strip()
            skill = self.get_skill(account_name, skill_name)
            if skill is not None:
                resolved.append(skill)
            else:
                missing.append(skill_name)
        ctx.resolved_skills = resolved
        ctx.missing_imports = missing

    def get_or_create_context(
        self,
        account_name: str,
        context_id: str,
        *,
        default_data: Optional[Dict[str, Any]] = None,
    ) -> Context:
        """Load a context; if missing, create and save it immediately.

        When creating a new context, default_data is merged onto default
        fields: typed keys (tag, imports, mandatory_tools,
        search_namespaces, text, updated_at) map to Context fields,
        everything else lands in ``extra``.
        """
        existing = self.get_context(account_name=account_name, context_id=context_id)
        if existing is not None:
            return existing

        ctx = Context(
            id=context_id,
            account_name=account_name,
            text="",
            updated_at=_now_utc(),
            extra={
                "context_name": context_id,
                "agreed": False,
                "tasklist_status": "draft",
            },
        )
        if default_data:
            tag, imports, mandatory_tools, search_namespaces, extra = _parse_context_frontmatter(default_data)
            if tag is not None:
                ctx.tag = tag
            if imports:
                ctx.imports = imports
            if mandatory_tools:
                ctx.mandatory_tools = mandatory_tools
            if search_namespaces:
                ctx.search_namespaces = search_namespaces
            if extra:
                ctx.extra.update(extra)
            if "text" in default_data and isinstance(default_data.get("text"), str):
                ctx.text = default_data["text"]
            if "updated_at" in default_data:
                try:
                    ctx.updated_at = _parse_dt_utc(default_data.get("updated_at") or "")
                except Exception:
                    pass
        self.save_context(ctx)
        return ctx

    def save_context(self, context: Context) -> None:
        """Persist a Context as Markdown (.md) with YAML frontmatter.

        Only persisted fields are written: the typed frontmatter keys (tag,
        imports, mandatory_tools, search_namespaces, updated_at), the
        catch-all ``extra``, and the Markdown body (``text``). Derived members
        (resolved_skills, missing_imports, resolved_text, required_tools) are
        never serialized. The file's modification time is set to
        context.updated_at (UTC) to preserve the timestamp.
        """
        path = self.storage_paths.contexts / context.account_name
        self._ensure_dir(path)

        updated = context.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        else:
            updated = updated.astimezone(timezone.utc)

        # Frontmatter: typed persisted fields + catch-all extra. 'text' is the
        # Markdown body; derived members are never serialized.
        fm: Dict[str, Any] = {}
        if context.tag is not None:
            fm["tag"] = context.tag
        if context.imports:
            fm["imports"] = list(context.imports)
        if context.mandatory_tools:
            fm["mandatory_tools"] = list(context.mandatory_tools)
        if context.search_namespaces:
            fm["search_namespaces"] = list(context.search_namespaces)
        fm["updated_at"] = updated.isoformat()
        fm.update(context.extra)

        try:
            fm_yaml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)
        except Exception:
            # Fallback: ensure YAML serialization doesn't crash
            fm_yaml = yaml.safe_dump({}, sort_keys=False, allow_unicode=True)

        body = context.text or ""

        # Compose Markdown with YAML frontmatter
        content = f"---\n{fm_yaml}---\n{body}"

        target = path / f"{context.id}.md"
        # Write atomically
        self._atomic_write_text(target, content)

        # Preserve updated_at via file mtime so get_context can read it when needed
        try:
            ts = updated.timestamp()
            os.utime(target, (ts, ts))
        except Exception:
            # Not critical; file will just have current mtime
            pass

    def list_context_names(self, account_name: str) -> List[str]:
        """List context names (filename stems) for an account in sorted order.

        Only .md files are considered.
        """
        ctx_dir = self.storage_paths.contexts / account_name
        if not ctx_dir.exists() or not ctx_dir.is_dir():
            return []

        names: List[str] = []
        for p in ctx_dir.glob("*.md"):
            # filename stem without suffix
            names.append(p.stem)

        names.sort()
        return names

    def migrate_context_json_to_md(self) -> None:
        """Migration helper: convert existing contexts/*.json → *.md.

        This will iterate accounts and for each <id>.json file create a
        corresponding <id>.md file if one does not already exist. It preserves
        the original 'data' dict and the updated_at timestamp (if present) by
        setting the md file mtime.
        """
        base = self.storage_paths.contexts
        if not base.exists():
            return

        for account_dir in base.iterdir():
            if not account_dir.is_dir():
                continue
            for json_file in account_dir.glob("*.json"):
                try:
                    data = self._load_json(json_file)
                    if not data:
                        continue
                    ctx_id = data.get("id") or json_file.stem
                    md_path = account_dir / f"{ctx_id}.md"
                    if md_path.exists():
                        # Skip if md already present
                        continue

                    ctx_data = data.get("data", {})
                    # Ensure text key exists
                    if "text" not in ctx_data:
                        ctx_data["text"] = ""

                    updated_at = None
                    if data.get("updated_at"):
                        try:
                            updated_at = _parse_dt_utc(data.get("updated_at"))
                        except Exception:
                            updated_at = None

                    tag, imports, mandatory_tools, search_namespaces, extra = _parse_context_frontmatter(ctx_data)

                    ctx = Context(
                        id=ctx_id,
                        account_name=account_dir.name,
                        tag=tag,
                        imports=imports,
                        mandatory_tools=mandatory_tools,
                        search_namespaces=search_namespaces,
                        text=ctx_data.get("text", ""),
                        extra=extra,
                        updated_at=updated_at or _now_utc(),
                    )

                    # Use save_context to write md
                    self.save_context(ctx)
                except Exception as e:
                    logging.error("Failed migrating %s: %s", json_file, e)

    # ----------------------------------------------------------------------
    # SKILLS
    # ----------------------------------------------------------------------

    def get_skill(self, account_name: str, skill_name: str) -> Optional[Skill]:
        """Return a skill (frontmatter + body), or None if missing.

        Skill files are stored at skills/<account>/<skill_name>.md as
        Markdown with optional YAML frontmatter. The body is returned in
        ``Skill.text``; the frontmatter key ``mandatory_tools`` (see #114)
        is parsed into ``Skill.mandatory_tools``; all other frontmatter keys
        land in ``Skill.extra`` (catch-all). Malformed YAML frontmatter is
        treated as body-only (a warning is logged).
        """
        path = self.storage_paths.skills / account_name / f"{skill_name}.md"
        if not path.exists():
            return None

        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            logging.warning("Failed to read skill file %s: %s", path, e)
            return None

        fm: Dict[str, Any] = {}
        body = text
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)\Z", text, re.S)
        if m:
            fm_text = m.group(1)
            body = m.group(2)
            try:
                loaded = yaml.safe_load(fm_text)
                if isinstance(loaded, dict):
                    fm = loaded
                else:
                    fm = {}
            except Exception as e:
                logging.warning("Failed to parse YAML frontmatter for %s: %s", path, e)
                fm = {}
        else:
            # No frontmatter; treat whole file as body
            body = text

        mandatory_tools: List[str] = []
        extra: Dict[str, Any] = {}
        for key, value in fm.items():
            if key == "mandatory_tools":
                if isinstance(value, list):
                    mandatory_tools = [v for v in value if isinstance(v, str)]
                else:
                    extra[key] = value
            else:
                extra[key] = value

        return Skill(
            name=skill_name,
            text=body,
            mandatory_tools=mandatory_tools,
            extra=extra,
        )

    def get_skill_text(self, account_name: str, skill_name: str) -> Optional[str]:
        """Return the body text of a skill Markdown file, or None if missing.

        Backward-compat wrapper: delegates to get_skill() (see #114).
        """
        skill = self.get_skill(account_name, skill_name)
        if skill is None:
            return None
        return skill.text


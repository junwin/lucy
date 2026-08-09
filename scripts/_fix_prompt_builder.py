#!/usr/bin/env python3
"""Apply step-4 + cleanup changes to prompt_builder.py using line-based editing."""

SRC = "src/prompt_builders/prompt_builder.py"

with open(SRC) as f:
    lines = f.readlines()

# ── helpers ──
def find_line(text: str, start: int = 0) -> int:
    for i in range(start, len(lines)):
        if lines[i].strip() == text.strip():
            return i
    return -1

def insert_at(idx: int, block: str):
    """Insert block lines before idx. block is a multi-line string."""
    for line in reversed(block.split("\n")):
        lines.insert(idx, line + "\n")

def delete_range(start: int, end: int):
    """Delete lines [start, end) (0-indexed, end exclusive)."""
    del lines[start:end]

# ── 1. Remove get_last_n_events import ──────────────────────
i = find_line("from src.chat2.prompt_slice import get_last_n_events")
if i >= 0:
    del lines[i]

# ── 2. Add CONTEXT_TEXT_SOFT_MAX_TOKENS constant ────────────
# After DOC_EMBEDDING_SCORE_THRESHOLD line
i = find_line("DOC_EMBEDDING_SCORE_THRESHOLD = 0.25")
if i >= 0:
    insert_at(i + 1, """# Legacy constant kept for backward reference; runtime value is configurable
# via environment variable PROMPT_BUILDER_CONTEXT_SOFT_MAX_TOKENS or via
# config.json key 'context_text_soft_max_tokens'. Default to a conservative
# 2000 tokens.
CONTEXT_TEXT_SOFT_MAX_TOKENS = int(os.getenv("PROMPT_BUILDER_CONTEXT_SOFT_MAX_TOKENS", "2000"))""")

# ── 3. Add _last_prompt_token_breakdown to __init__ ─────────
i = find_line("        self.embedding_facade = embedding_facade")
if i >= 0:
    lines[i] = "        self.embedding_facade = embedding_facade\n"
    insert_at(i + 1, "        # last prompt token breakdown is stored here for external inspection\n        self._last_prompt_token_breakdown: Dict[str, int] = {}")

# ── 4. Add system_parts tracking ────────────────────────────
i = find_line('        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_message}]')
if i >= 0:
    insert_at(i + 1, "\n        # collect system/session pieces for token estimation\n        system_parts: List[str] = [system_message]")

# ── 5. Update convo_id line ─────────────────────────────────
i = find_line('                "content": f"Current session ID: {conversation_id}",')
if i >= 0:
    # Find the start of the if block
    for j in range(i-5, i):
        if 'if conversation_id and conversation_id not in ("none", "new"):' in lines[j]:
            lines[j+1] = '            convo_line = f"Current session ID: {conversation_id}"\n'
            lines[i] = '                "content": convo_line,\n'
            insert_at(i + 2, "            system_parts.append(convo_line)")
            break

# ── 6. Add system_parts.append(info) after session info ─────
i = find_line('                    messages.append({"role": "system", "content": info})')
if i >= 0:
    insert_at(i + 1, "                    system_parts.append(info)")

# ── 7. Add system_parts.append for extras ───────────────────
i = find_line('                messages.append({"role": "system", "content": extra.strip()})')
if i >= 0:
    insert_at(i + 1, "                system_parts.append(extra.strip())")

# ── 8. Replace chat history + context text sections ──────────
# Find: "        # --- Chat history ---"
i = find_line("        # --- Chat history ---")
if i >= 0:
    # Find end of context text section
    end = -1
    for j in range(i, len(lines)):
        if "# --- External documents ---" in lines[j]:
            end = j
            break
    if end >= 0:
        # Replace with new version (just load context, defer appending)
        new_block = """        # --- Named context (from storage) ---
        context_text = self._get_context_text(account_name=account_name, context_name=context_name)

        # --- External documents ---
"""
        # Replace from "        # --- Chat history ---" to just before "        # --- External documents ---"
        # Actually, we need to keep the External documents section header.
        # Let's delete everything from "# --- Chat history ---" to "# --- External documents ---"
        # and insert our new context_text line.
        delete_range(i, end)
        lines.insert(i, new_block)

# ── 9. Restructure user message section ─────────────────────
# Find: "        # --- Current user message ---"
i = find_line("        # --- Current user message ---")
if i >= 0:
    # Find end of this section (the _ensure_current_query call)
    end = -1
    for j in range(i, len(lines)):
        if "_ensure_current_query" in lines[j]:
            end = j + 1
            break
    if end >= 0:
        # Delete the old section
        delete_range(i, end)

        # Insert the new version
        new_section = """        # --- Current user message (build but don't append yet) ---
        has_attachments = bool(image_ids or file_ids)
        if has_attachments:
            content_parts: List[Dict[str, Any]] = [
                {"type": "text", "text": content_text}
            ]
            agent_allowed_tools = agent.allowed_tools if agent else None
            content_parts.extend(self._resolve_attachments(
                account_name=account_name,
                image_ids=image_ids,
                file_ids=file_ids,
                agent_allowed_tools=agent_allowed_tools,
                supports_images=supports_images,
            ))
            user_message = {"role": "user", "content": content_parts}
        else:
            user_message = {"role": "user", "content": content_text}

        # --- Token estimation breakdown (exclude history for now) ---
        try:
            system_text = "\\n\\n".join(system_parts)
            system_tokens = estimate_tokens_from_text(system_text)

            context_tokens = estimate_tokens_from_text(context_text or "")

            obsidian_text = "\\n\\n".join([c.get("snippet", "") for c in doc_contexts]) if doc_contexts else ""
            obsidian_tokens = estimate_tokens_from_text(obsidian_text)

            digest_text = "\\n\\n".join([d.get("snippet", "") for d in digest_contexts]) if digest_contexts else ""
            digest_tokens = estimate_tokens_from_text(digest_text)

            user_tokens = estimate_tokens_from_text(content_text or "")

        except Exception:
            logging.exception("PromptBuilder: failed to compute token breakdown \\u2014 continuing")
            system_tokens = context_tokens = obsidian_tokens = digest_tokens = user_tokens = 0

        # --- Soft-max warning for front-loaded context ---
        try:
            soft_max = self._get_context_soft_max_tokens()
            if context_tokens > soft_max:
                logging.warning(
                    "PromptBuilder: context text (%d tokens) exceeds soft max (%d tokens) \\u2014 "
                    "agent=%s account=%s context=%s; consider trimming the context file",
                    context_tokens,
                    soft_max,
                    agent_name,
                    account_name,
                    context_name or "(none)",
                )
        except Exception:
            logging.exception("PromptBuilder: failed to check context soft max")

        # --- Model token limit & safety margin (configurable) ---
        try:
            model_limit = None
            if hasattr(self.config, "get"):
                cfg_val = self.config.get("prompt_builder_model_token_limit", None)
                if cfg_val is not None:
                    try:
                        model_limit = int(cfg_val)
                    except Exception:
                        logging.warning(
                            "PromptBuilder: invalid prompt_builder_model_token_limit in config: %s; using default",
                            cfg_val,
                        )
            if model_limit is None:
                env_val = os.getenv("PROMPT_BUILDER_MODEL_TOKEN_LIMIT")
                if env_val:
                    try:
                        model_limit = int(env_val)
                    except Exception:
                        logging.warning(
                            "PromptBuilder: invalid PROMPT_BUILDER_MODEL_TOKEN_LIMIT=%s; using default",
                            env_val,
                        )
            if model_limit is None:
                model_limit = DEFAULT_PROMPT_BUDGET_TOKENS

            safety_margin = 200
            if hasattr(self.config, "get"):
                sm = self.config.get("prompt_builder_safety_margin_tokens", None)
                if sm is not None:
                    try:
                        safety_margin = int(sm)
                    except Exception:
                        logging.warning(
                            "PromptBuilder: invalid prompt_builder_safety_margin_tokens in config: %s; using default",
                            sm,
                        )

            # Remaining tokens available for history
            used = system_tokens + context_tokens + obsidian_tokens + digest_tokens + user_tokens
            remaining_for_history = model_limit - used - safety_margin

            logging.info(
                "PromptBuilder.token_budget: model_limit=%d used=%d safety_margin=%d remaining_for_history=%d",
                model_limit,
                used,
                safety_margin,
                remaining_for_history,
            )
        except Exception:
            logging.exception("PromptBuilder: failed to compute token budget; including no history")
            remaining_for_history = 0

        # --- Select history messages by token budget (walk from most recent backward) ---
        history_messages: List[Dict[str, str]] = []
        dropped_texts: List[str] = []
        if self.chat2_store is not None and conversation_id not in ("none", "new", ""):
            try:
                history_messages, dropped_texts = self._select_history_messages_and_dropped(
                    conversation_id=conversation_id,
                    account_name=account_name,
                    agent_name=agent_name,
                    max_conversations=agent.max_prompt_conversations if agent else 0,
                    budget_tokens=remaining_for_history,
                )
            except Exception as ex:
                logging.warning(
                    "PromptBuilder: failed to select history messages for %s: %s",
                    conversation_id,
                    ex,
                )

        # --- If there were dropped messages due to budget, create/append a digest
        if dropped_texts:
            try:
                digest_snippet = self._summarize_overflow(dropped_texts)
                # Persist running digest per-session in storage context
                ctx_id = f"session_digest:{conversation_id}"
                try:
                    ctx = None
                    if hasattr(self.storage, "get_or_create_context"):
                        ctx = self.storage.get_or_create_context(account_name, ctx_id)
                    else:
                        ctx = self.storage.get_context(account_name, ctx_id)

                    if ctx is not None:
                        data = getattr(ctx, "data", None) or {}
                        existing = data.get("digest", "") if isinstance(data, dict) else ""
                        if existing and existing.strip():
                            new_digest = existing.strip() + "\\n\\n" + digest_snippet
                        else:
                            new_digest = digest_snippet
                        # write back and save
                        data["digest"] = new_digest
                        ctx.data = data
                        if hasattr(self.storage, "save_context"):
                            self.storage.save_context(ctx)

                        # Include the accumulated digest as a system message before history
                        messages.append({"role": "system", "content": f"Earlier in this session:\\n{new_digest}"})
                    else:
                        # Storage doesn't support contexts; include ephemeral digest
                        messages.append({"role": "system", "content": f"Earlier in this session:\\n{digest_snippet}"})
                except Exception as ex:
                    logging.warning(
                        "PromptBuilder: failed to persist session digest for %s: %s",
                        conversation_id,
                        ex,
                    )
                    messages.append({"role": "system", "content": f"Earlier in this session:\\n{digest_snippet}"})
            except Exception as ex:
                logging.warning(
                    "PromptBuilder: failed to summarize overflow for %s: %s",
                    conversation_id,
                    ex,
                )

        # --- Now assemble final message list in the original order ---
        # messages currently contains system messages and session info and extras
        # Insert history next
        messages.extend(history_messages)

        # Then context text
        if context_text:
            messages.append(
                {
                    "role": "system",
                    "content": f"Additional context for this conversation:\\n{context_text}",
                }
            )
"""
        lines.insert(i, new_section)

# ── 10. Remove deferred doc/digest markers and restore proper appends ──
# The committed version has doc_lines/digest_lines directly inside the if blocks.
# We need to move the append calls to after the history+context section.
# Since we're restructuring, we need to:
# a) Keep doc_contexts and digest_contexts loading as-is
# b) Remove the messages.append calls from within those blocks
# c) Add them back after the context_text section

# Find and remove doc_lines append inside the doc_contexts block
# The pattern is: "                    messages.append({\"role\": \"system\", \"content\": \"\\n\".join(doc_lines).strip()})"
# inside the document context section

i = find_line('                    messages.append({"role": "system", "content": "\\n".join(doc_lines).strip()})')
if i >= 0 and "doc_lines" in lines[i-1] or True:
    # Replace with a no-op comment
    lines[i] = '                # doc_lines deferred — appended after history\n'
    # Also need to fix indentation — the line before removing doc_lines had proper indent
    # Remove the `if doc_contexts:` block start and just keep the content
    # This is getting complex. Let's just replace the append line.

# Same for digest_lines
i = find_line('                messages.append({"role": "system", "content": "\\n".join(digest_lines).strip()})')
if i >= 0:
    lines[i] = '            # digest_lines deferred — appended after history\n'

# ── 11. Add doc and digest appends after context text ─────────
# Find the end of the context_text append we just inserted
i = find_line('                }')
# Look for the context text append end
found = False
for j in range(len(lines)):
    if '                }' in lines[j] and j > 0 and 'content": f"Additional context' in lines[j-1]:
        i = j
        found = True
        break
    if '                }' in lines[j] and j > 0 and 'content": f"Additional context for this conversation' in lines[j-1]:
        i = j
        found = True
        break

if found:
    # Insert after the closing brace of context text append
    insert_at(i + 1, """
        # Then external documents (as system messages)
        if doc_contexts:
            doc_lines: List[str] = [
                "The following Obsidian notes may be relevant to the user's question:",
            ]
            for idx, ctx in enumerate(doc_contexts, start=1):
                title = ctx.get("title") or "(untitled)"
                tags = ctx.get("tags") or []
                snippet = ctx.get("snippet") or ""
                truncated = ctx.get("truncated") or False
                tag_str = ", ".join(tags)
                header = f"{idx}. Title: {title}"
                if tag_str:
                    header += f" | Tags: {tag_str}"
                doc_lines.append(header)
                doc_lines.append(snippet)
                if truncated:
                    doc_lines.append("[Note: content truncated]")
                doc_lines.append("")

            messages.append({"role": "system", "content": "\\n".join(doc_lines).strip()})

        # Then digests
        if digest_contexts:
            digest_lines: List[str] = [
                "The following archived chat session digests may be relevant:",
            ]
            for idx, dctx in enumerate(digest_contexts, start=1):
                session_id = dctx.get("session_id") or "unknown"
                score = dctx.get("score", 0)
                snippet = dctx.get("snippet") or ""
                truncated = dctx.get("truncated") or False
                digest_lines.append(
                    f"{idx}. Session {session_id} (score: {score:.3f})"
                )
                digest_lines.append(snippet)
                if truncated:
                    digest_lines.append("[Digest truncated]")
                digest_lines.append("")

            messages.append({"role": "system", "content": "\\n".join(digest_lines).strip()})

        # Finally append the current user message and ensure current query
        messages.append(user_message)

        messages = self._ensure_current_query(messages, content_text)""")

# ── 12. Add token breakdown before final return ──────────────
# Find: "        return messages" right before "# --- helper methods ---"
i = find_line("        return messages")
# Need the one before helper methods section
for j, line in enumerate(lines):
    if line.strip() == "return messages" and j + 1 < len(lines) and "# --- helper methods" in lines[j + 1]:
        i = j
        break

if i >= 0:
    insert_at(i, """        # --- Token estimation breakdown (now include history tokens) ---
        try:
            history_text = "\\n\\n".join([m.get("content", "") for m in history_messages]) if history_messages else ""
            history_tokens = estimate_tokens_from_text(history_text)

            self._last_prompt_token_breakdown = {
                "system_session": system_tokens,
                "context_text": context_tokens,
                "obsidian_notes": obsidian_tokens,
                "digest_embeddings": digest_tokens,
                "chat_history": history_tokens,
                "current_user_message": user_tokens,
                "total_without_handlers": sum(
                    [system_tokens, context_tokens, obsidian_tokens, digest_tokens, history_tokens, user_tokens]
                ),
            }

            logging.info(
                "PromptBuilder.token_breakdown: agent=%s account=%s session=%s system=%d context=%d obsidian=%d digest=%d history=%d user=%d total_without_handlers=%d",
                agent_name,
                account_name,
                conversation_id,
                system_tokens,
                context_tokens,
                obsidian_tokens,
                digest_tokens,
                history_tokens,
                user_tokens,
                self._last_prompt_token_breakdown["total_without_handlers"],
            )
        except Exception:
            logging.exception("PromptBuilder: failed to compute token breakdown (after history) \\u2014 continuing")

""")

# ── 13. Add _get_context_soft_max_tokens method ──────────────
# After "# --- helper methods ---"
i = find_line("    # --- helper methods ---")
if i >= 0:
    insert_at(i + 1, """
    def _get_context_soft_max_tokens(self) -> int:
        \"\"\"Resolve the soft max tokens for front-loaded context.

        Order of precedence:
          1. Environment variable PROMPT_BUILDER_CONTEXT_SOFT_MAX_TOKENS
          2. config.get('context_text_soft_max_tokens') if available
          3. module default (CONTEXT_TEXT_SOFT_MAX_TOKENS)

        Returns an int >= 0.
        \"\"\"
        # 1) Check environment
        env_val = os.getenv("PROMPT_BUILDER_CONTEXT_SOFT_MAX_TOKENS")
        if env_val:
            try:
                v = int(env_val)
                if v >= 0:
                    return v
            except Exception:
                logging.warning(
                    "PromptBuilder: invalid PROMPT_BUILDER_CONTEXT_SOFT_MAX_TOKENS=%s; using fallback",
                    env_val,
                )

        # 2) Check config (ConfigManager-like object with .get)
        try:
            cfg_val = None
            if hasattr(self.config, "get"):
                cfg_val = self.config.get("context_text_soft_max_tokens", None)
            if cfg_val is not None:
                try:
                    v = int(cfg_val)
                    if v >= 0:
                        return v
                except Exception:
                    logging.warning(
                        "PromptBuilder: invalid context_text_soft_max_tokens in config: %s; using fallback",
                        cfg_val,
                    )
        except Exception:
            logging.debug("PromptBuilder: failed to read config for soft max tokens; using default")

        # 3) Fallback to module-level default
        return CONTEXT_TEXT_SOFT_MAX_TOKENS
""")

# ── 14. Replace _get_chat_history_messages with new methods ──
i = find_line("    def _get_chat_history_messages(")
if i >= 0:
    # Find end of method
    end = i + 1
    while end < len(lines):
        if lines[end].startswith("    def "):
            break
        end += 1
    delete_range(i, end)

    insert_at(i, """
    def _select_history_messages_and_dropped(
        self,
        conversation_id: str,
        account_name: str,
        agent_name: str,
        max_conversations: int,
        budget_tokens: int,
    ) -> tuple[List[Dict[str, str]], List[str]]:
        \"\"\"Select history messages starting from the most recent and moving backwards
        until the token budget is exhausted. Returns a tuple of (selected_messages, dropped_texts).

        dropped_texts contains earlier messages' text that were not included due to
        token budget or max_conversations cap. Selected messages are in chronological order.
        \"\"\"
        if not conversation_id or conversation_id in ("none", "new"):
            return [], []
        if max_conversations <= 0:
            return [], []

        if self.chat2_store is None:
            return [], []

        # Collect all user/assistant events
        events = list(self.chat2_store.stream_events(conversation_id))
        conv_events = [e for e in events if e.kind in ("user_message", "assistant_message")]

        if not conv_events:
            return [], []

        original_conv_events = conv_events.copy()

        # Apply max_conversations cap first (take last N events)
        if len(conv_events) > max_conversations:
            conv_events = conv_events[-max_conversations:]

        # Walk from most recent backward, accumulating tokens
        selected_rev = []
        remaining = budget_tokens if isinstance(budget_tokens, int) else 0
        acc = 0
        included_set = set()
        for e in reversed(conv_events):
            content = e.payload if isinstance(e.payload, str) else str(e.payload)
            toks = estimate_tokens_from_text(content)
            # If we have no budget (remaining <=0) but nothing selected yet, include the
            # most recent single message per requirement.
            if remaining <= 0 and not selected_rev:
                selected_rev.append({"role": e.role, "content": content})
                included_set.add(id(e))
                break
            if acc + toks <= remaining:
                selected_rev.append({"role": e.role, "content": content})
                acc += toks
                included_set.add(id(e))
            else:
                # if nothing selected yet, include this oversized message anyway
                if not selected_rev:
                    selected_rev.append({"role": e.role, "content": content})
                    included_set.add(id(e))
                break

        # Reverse to chronological order
        selected = list(reversed(selected_rev))

        # Determine dropped events from the original events that were not included
        dropped_events = [e for e in original_conv_events if id(e) not in included_set]
        dropped_texts = [e.payload if isinstance(e.payload, str) else str(e.payload) for e in dropped_events]

        return selected, dropped_texts

    def _summarize_overflow(self, texts: List[str], max_chars: int = 800) -> str:
        \"\"\"Create a short human-readable digest from a list of earlier message texts.

        This is intentionally simple and deterministic: concatenate leading
        excerpts from the first few messages until max_chars is reached, and
        prepend a short header describing how many messages were summarized.
        \"\"\"
        if not texts:
            return ""

        header = f"{len(texts)} earlier messages were summarized."
        out_parts: List[str] = [header]
        remaining = max_chars - len(header) - 1
        for t in texts:
            if remaining <= 0:
                break
            snippet = t.strip().replace("\\n", " ")
            if not snippet:
                continue
            take = min(len(snippet), remaining)
            out_parts.append(snippet[:take])
            remaining -= take + 2
        combined = "\\n\\n".join(out_parts)
        if len(combined) > max_chars:
            combined = combined[: max_chars - 3] + "..."
        return combined
""")

# ── 15. Write ────────────────────────────────────────────────
with open(SRC, "w") as f:
    f.writelines(lines)

print("prompt_builder.py updated successfully")

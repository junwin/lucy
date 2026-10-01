"""Keep tool/model/history references compact; expand only for browser delivery."""

import json
import logging
from urllib.parse import parse_qs, quote, urlsplit

from src.image_presentation import ImagePresentationService


def image_result_for_model(tool_name, result_text):
    if tool_name not in {"image_generate", "serve_image"}:
        return result_text
    try:
        result = json.loads(result_text)
    except (ValueError, TypeError):
        return result_text
    if not isinstance(result, dict) or not result.get("ok"):
        return result_text
    # Whitelist instead of deleting a few known fields: provider data must
    # never leak into the initiating model's context, even with older handlers.
    result = {key: result[key] for key in
              ("ok", "tool", "model", "image_id", "path", "mime_type") if key in result}
    result["presentation"] = "Lucy delivers the image automatically. Confirm creation without calling serve_image or inventing a download URL."
    return json.dumps(result, ensure_ascii=False)


def image_event_for_history(event, account_name):
    """Attach host-owned download URLs without adding image bytes to history."""
    if event.type != "image" or not event.image_id:
        return event
    url = f"/download/image/{event.image_id}?accountName={quote(account_name, safe='')}"
    return event.model_copy(update={"image_url": url, "download_url": url})


def image_event_for_browser(event, config, account_name):
    if event.type != "image":
        return event
    reference = event.image_ref
    if event.image_id:
        reference = {"image_id": event.image_id}
    elif not reference and event.image_url:
        # Compatibility for compact references already stored in older chats.
        url = urlsplit(event.image_url)
        prefix = "/download/image/"
        if url.scheme or url.netloc or not url.path.startswith(prefix):
            return event
        requested_account = parse_qs(url.query).get("accountName", [account_name])
        if requested_account != [account_name]:
            return event.model_copy(update={"image_url": None, "alt": "Image unavailable for this account."})
        reference = {"image_id": url.path[len(prefix):]}
    if not reference:
        return event
    try:
        preview = ImagePresentationService(config).preview(reference, account_name)
    except (ValueError, OSError) as exc:
        logging.warning("Cannot deliver image: %s", exc)
        return event.model_copy(update={"image_ref": None, "image_url": None,
                                        "message": "Stored image is unavailable."})
    return event.model_copy(update={"image_url": preview, "image_ref": None})

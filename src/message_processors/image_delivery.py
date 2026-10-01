"""Expand stored image references only at the browser delivery boundary."""

import base64
import logging
import json
from urllib.parse import parse_qs, urlsplit

from src.http_endpoints.upload_endpoints import get_image_download_impl


def image_result_for_model(tool_name, result_text):
    """Keep presentation URLs out of the generated-image tool response."""
    if tool_name != "image_generate":
        return result_text
    try:
        result = json.loads(result_text)
    except (ValueError, TypeError):
        return result_text
    if not isinstance(result, dict) or not result.get("ok") or not result.get("image_id"):
        return result_text
    result.pop("image", None)
    result.pop("download_url", None)
    result["presentation"] = "The image is delivered separately to the browser. Confirm creation without inventing a download URL."
    return json.dumps(result, ensure_ascii=False)


def image_event_for_browser(event, config, account_name):
    """Return an independent inline event; leave model output/history compact.

    Resolve only local image download references against the current account.
    Never fetch model-provided URLs or trust their accountName parameter.
    """
    if event.type != "image" or not event.image_url:
        return event
    reference = urlsplit(event.image_url)
    prefix = "/download/image/"
    if reference.scheme or reference.netloc or not reference.path.startswith(prefix):
        return event
    requested_account = parse_qs(reference.query).get("accountName", [account_name])
    if requested_account != [account_name]:
        return event.model_copy(update={"image_url": None, "alt": "Image unavailable for this account."})
    image_id = reference.path[len(prefix):]
    path, metadata, status = get_image_download_impl(config, account_name, image_id)
    if status != 200:
        logging.warning("Cannot deliver stored image %s: %s", image_id, metadata.get("error"))
        return event.model_copy(update={"image_url": None, "alt": "Stored image is unavailable."})
    try:
        with open(path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("ascii")
    except OSError:
        logging.exception("Cannot read stored image %s for browser delivery", image_id)
        return event.model_copy(update={"image_url": None, "alt": "Stored image is unavailable."})
    return event.model_copy(update={
        "image_url": f"data:{metadata['mime_type']};base64,{encoded}",
    })

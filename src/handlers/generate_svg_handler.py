"""Lucy compatibility adapter for galet-tools' generate_svg handler."""

from galet_tools.tools.generate_svg_handler import (
    ALLOWED_ATTRIBUTES,
    ALLOWED_ELEMENTS,
    FORBIDDEN_ATTR_PREFIXES,
    MAX_SVG_CHARS,
    SVG_NAMESPACE,
    GenerateSvgHandler as GaletGenerateSvgHandler,
    GenerateSvgInput,
    SvgSanitizer,
)


class GenerateSvgHandler(GaletGenerateSvgHandler):
    """Accept Lucy's historical, unused ConfigManager constructor argument."""

    def __init__(self, config=None) -> None:
        self.config = config
        super().__init__()


__all__ = [
    "ALLOWED_ATTRIBUTES",
    "ALLOWED_ELEMENTS",
    "FORBIDDEN_ATTR_PREFIXES",
    "GenerateSvgHandler",
    "GenerateSvgInput",
    "MAX_SVG_CHARS",
    "SVG_NAMESPACE",
    "SvgSanitizer",
]

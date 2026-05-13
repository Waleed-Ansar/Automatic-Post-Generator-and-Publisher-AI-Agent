from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

from langchain.tools import tool
from langchain.agents import create_agent

from llm import get_llm
from prompts import POST_CREATION_AGENT_PROMPT

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
DEFAULT_OUTPUT_DIR = BASE_DIR / "output"

TEMPLATE_MAP = {
    "01": "template_01_neon_sop.html",
    "02": "template_02_editorial_card.html",
    "03": "template_03_gradient_wave.html",
    "04": "template_04_retro_notice.html",
    "05": "template_05_glass_panel.html",
    "06": "template_06_warning_stripes.html",
    "07": "template_07_orbit_badge.html",
    "08": "template_08_diagonal_split.html",
    "09": "template_09_blueprint_grid.html",
    "10": "template_10_feed_alert.html",
}


@dataclass
class PostPayload:
    header: str = ""
    sub_header: str = ""
    content: str = ""
    cta: str = ""
    link: str = ""
    brand: str = ""
    caption: str = ""

    @property
    def content_items(self) -> list[str]:
        return split_content(self.content)

    @property
    def link_label(self) -> str:
        if not self.link:
            return ""
        parsed = urlparse(self.link)
        if parsed.netloc:
            path = parsed.path.rstrip("/")
            return parsed.netloc + (path if path and path != "/" else "")
        return self.link


def _chromium_executable(playwright: Any) -> str | None:
    """Return a usable Chromium executable path across local/dev/server environments."""
    candidates = [
        Path("/usr/bin/chromium"),
        Path("/usr/bin/chromium-browser"),
        Path("/usr/bin/google-chrome"),
    ]
    try:
        candidates.insert(0, Path(playwright.chromium.executable_path))
    except Exception:
        pass
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _read_json_input(payload_json: str | Path | Mapping[str, Any]) -> dict[str, Any]:
    """
    Accept a Python dict, a JSON string, or a path to a JSON file.
    This replaces all argparse/CLI input handling.
    """
    if isinstance(payload_json, Mapping):
        return dict(payload_json)

    if isinstance(payload_json, Path):
        return json.loads(payload_json.read_text(encoding="utf-8"))

    if isinstance(payload_json, str):
        possible_path = Path(payload_json)
        if possible_path.exists():
            return json.loads(possible_path.read_text(encoding="utf-8"))
        return json.loads(payload_json)

    raise TypeError("payload_json must be a dict, JSON string, or path to a JSON file")


def _normalize_data(data: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize friendly field-name variants into the internal field names."""
    normalized = dict(data)
    aliases = {
        "Header": "header",
        "Sub-header": "sub_header",
        "Sub-Header": "sub_header",
        "sub-header": "sub_header",
        "subHeader": "sub_header",
        "Content": "content",
        "CTA": "cta",
        "Cta": "cta",
        "Link": "link",
        "Brand": "brand",
        "Caption": "caption",
    }
    for source_key, target_key in aliases.items():
        if source_key in normalized and target_key not in normalized:
            normalized[target_key] = normalized[source_key]
    return normalized


def _coerce_content(content: Any) -> str:
    """Allow content as a string or a list/tuple of bullet items."""
    if isinstance(content, (list, tuple)):
        return "|".join(str(item) for item in content)
    return str(content)


def load_payload(payload_json: str | Path | Mapping[str, Any]) -> PostPayload:
    """Load and validate post data from JSON/dict input."""
    data = _normalize_data(_read_json_input(payload_json))

    missing = [k for k in ["header", "sub_header", "content", "cta"] if not data.get(k)]
    if missing:
        raise ValueError(f"Missing required field(s): {', '.join(missing)}")

    return PostPayload(
        header=str(data["header"]),
        sub_header=str(data["sub_header"]),
        content=_coerce_content(data["content"]),
        cta=str(data["cta"]),
        link=str(data.get("link", "")),
        brand=str(data.get("brand", "Your Brand")),
        caption=str(data.get("caption", "")),
    )


def split_content(content: str) -> list[str]:
    """Accept text separated by newlines, pipes, semicolons, or bullet characters."""
    if not content:
        return []
    parts = re.split(r"(?:\r?\n|\s*\|\s*|\s*;\s*|\s*•\s*)", content)
    return [p.strip(" -\t") for p in parts if p.strip(" -\t")]


def normalize_template_id(template_id: str | int | None) -> str:
    """Convert 1, '1', or '01' into a valid two-digit template id."""
    if template_id is None:
        template_id = "01"
    value = str(template_id).strip()
    if value.isdigit():
        value = value.zfill(2)
    if value not in TEMPLATE_MAP:
        allowed = ", ".join(TEMPLATE_MAP.keys())
        raise ValueError(f"Unknown template '{template_id}'. Choose one of: {allowed}")
    return value


def template_id_from_json(payload_json: str | Path | Mapping[str, Any], fallback: str | int | None = "01") -> str:
    """Read template_id/template from JSON input when present; otherwise use fallback."""
    data = _normalize_data(_read_json_input(payload_json))
    return normalize_template_id(data.get("template_id") or data.get("template") or fallback)


def render_html(payload: PostPayload, template_id: str | int = "01") -> str:
    template_id = normalize_template_id(template_id)
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(TEMPLATE_MAP[template_id])
    context = asdict(payload)
    context["content_items"] = payload.content_items
    context["link_label"] = payload.link_label
    return template.render(**context)


def html_to_png(html: str, output_path: str | Path, size: int = 1080) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=_chromium_executable(p), args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": size, "height": size}, device_scale_factor=1)
        page.set_content(html, wait_until="networkidle")
        page.locator("#post").screenshot(path=str(output_path))
        browser.close()
    return output_path


def build_caption(payload: PostPayload) -> str:
    """
    Build the post caption text.
    If the input JSON includes a 'caption' field, that exact caption is used.
    Otherwise the caption is generated from header, sub_header, content, CTA, and link.
    """
    if payload.caption.strip():
        return payload.caption.strip() + "\n"

    lines: list[str] = [payload.header.strip(), "", payload.sub_header.strip()]

    items = payload.content_items
    if items:
        lines.append("")
        lines.extend(f"• {item}" for item in items)

    if payload.cta.strip():
        lines.extend(["", payload.cta.strip()])

    if payload.link.strip():
        lines.extend(["", f"Link: {payload.link.strip()}"])

    return "\n".join(lines).strip() + "\n"


def default_caption_path_for_image(image_path: str | Path) -> Path:
    """Return a caption path that matches the image path, e.g. post_01.png -> post_01_caption.txt."""
    image_path = Path(image_path)
    return image_path.with_name(f"{image_path.stem} caption.txt")


def write_caption(
    payload: PostPayload,
    image_path: str | Path | None = None,
    caption_path: str | Path | None = None,
) -> Path:
    """Write the caption TXT file and return its path."""
    if caption_path is None:
        caption_path = default_caption_path_for_image(image_path) if image_path else DEFAULT_OUTPUT_DIR / "caption.txt"
    caption_path = Path(caption_path)
    caption_path.parent.mkdir(parents=True, exist_ok=True)
    caption_path.write_text(build_caption(payload), encoding="utf-8")
    return caption_path


def make_post(
    payload_json: str | Path | Mapping[str, Any],
    template_id: str | int | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    output_filename: str | None = None,
    caption_path: str | Path | None = None,
    size: int = 1080,
    save_html: bool = False,
) -> dict[str, str]:
    """
    Create one post from JSON/dict input.

    Returns:
        {
          "template_id": "01",
          "image_path": ".../post_template_01.png",
          "caption_path": ".../post_template_01_caption.txt",
          "html_path": ".../post_template_01.html"   # only when save_html=True
        }
    """
    # print("AGENT GENERATED JSON:", payload_json)
    data = _normalize_data(_read_json_input(payload_json))
    payload = load_payload(data)
    selected_template_id = normalize_template_id(
        template_id or data.get("template_id") or data.get("template") or "01"
    )

    output_dir = Path(output_dir)
    # print(data)
    if output_filename is None:
        output_filename = f"{data.get("brand", "MyCompany")}.png"
    image_path = output_dir / output_filename

    html = render_html(payload, selected_template_id)
    html_to_png(html, image_path, size=size)
    written_caption_path = write_caption(payload, image_path=image_path, caption_path=caption_path)

    result = {
        "template_id": selected_template_id,
        "image_path": str(image_path),
        "caption_path": str(written_caption_path),
    }

    if save_html:
        html_path = image_path.with_suffix(".html")
        html_path.write_text(html, encoding="utf-8")
        result["html_path"] = str(html_path)

    return result

@tool
def make_posts(
    payload_json: str | Path | Mapping[str, Any],
    template_ids: list[str | int] | tuple[str | int, ...] | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    size: int = 1080,
    save_html: bool = False,
) -> dict:
    """
    Generate a 1080x1080 social media post image using one of 10 Python/Pillow templates.

    Template names: dark_tech, clean_card, bold_gradient, quote_style, checklist,
    diagonal_split, magazine, neon_tech, minimal_type, offer_card.
    If template_name is empty or None, a random template is selected.
    """
    if template_ids is None:
        template_ids = list(TEMPLATE_MAP.keys())
    return [
        make_post(
            payload_json=payload_json,
            template_id=template_id,
            output_dir=output_dir,
            size=size,
            save_html=save_html,
        )
        for template_id in template_ids
    ]


# Backwards-compatible aliases for code that imported the old render functions.
def render_post(payload: PostPayload, template_id: str | int, output_path: str | Path, size: int = 1080) -> Path:
    html = render_html(payload, template_id)
    return html_to_png(html, output_path, size=size)


def render_all(payload: PostPayload, output_dir: str | Path, size: int = 1080) -> list[Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for template_id in TEMPLATE_MAP:
        path = output_dir / f"post_template_{template_id}.png"
        paths.append(render_post(payload, template_id, path, size=size))
        write_caption(payload, image_path=path)
    return paths


post_creation_agent = None
if create_agent is not None and get_llm is not None:
    try:
        post_creation_agent = create_agent(
            model=get_llm(), 
            tools=[make_posts], 
            system_prompt=POST_CREATION_AGENT_PROMPT
        )

    except Exception:
        post_creation_agent = None


@tool
def AskPostCreationAgent(question: str) -> str:
    """
    Ask the social media post creation sub-agent to generate a post.
    Use this for social media post creation, post design, and template-based image generation.
    """
    if post_creation_agent is None:
        return "Post creation agent is not initialized. Make sure langchain is installed, llm.py exists, get_llm() works, and create_agent is available."
    result = post_creation_agent.invoke({"messages": [{"role": "user", "content": question}]})
    return result["messages"][-1].content
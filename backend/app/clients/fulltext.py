"""Open-access full-text retrieval helpers.

Two kinds of source text can be used for claim evidence: the abstract,
or the open-access full text. This module turns a Europe PMC JATS XML
document or an open-access PDF into plain text. The network calls live
in the source clients; the parsing here is pure so it can be tested.
"""

import io
import re
import xml.etree.ElementTree as ET

from ..config import settings


def _local(tag):
    return tag.rsplit("}", 1)[-1] if tag else ""


def jats_to_text(xml):
    """Turn a JATS full-text XML document into plain text.

    Only the abstract and body are kept. The reference list, figures,
    tables and supplementary material are dropped, so the Evidence
    Analyst is not fed the paper's own bibliography.
    """

    if not xml:
        return None

    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None

    parts = []

    for el in root.iter():
        if _local(el.tag) in ("abstract", "body"):
            parts.append(" ".join(el.itertext()))

    if not parts:
        parts = [" ".join(root.itertext())]

    text = re.sub(r"\s+", " ", " ".join(parts)).strip()

    return text or None


def pdf_to_text(data):
    """Extract text from the first pages of an open-access PDF."""

    if not data:
        return None

    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = reader.pages[:settings.max_fulltext_pages]

        text = "\n".join(
            (page.extract_text() or "")
            for page in pages
        )

    except Exception:
        return None

    text = re.sub(r"\s+", " ", text).strip()

    return text or None


def clip(text):
    """Cap stored full text so one paper cannot dominate the report."""

    if text and len(text) > settings.max_full_text_chars:
        return text[:settings.max_full_text_chars]

    return text

"""Dependency-free PDF export for deterministic engineering reports."""
from __future__ import annotations

import re
import textwrap

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
MARGIN = 54
FONT_SIZE = 9
LEADING = 12
LINES_PER_PAGE = 58


def _plain_lines(markdown: str) -> list[str]:
    lines: list[str] = []
    in_code = False
    for raw in markdown.splitlines():
        stripped = raw.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            stripped = re.sub(r"^#{1,6}\s+", "", stripped)
            stripped = re.sub(r"^[-*+]\s+", "- ", stripped)
            stripped = stripped.replace("**", "").replace("__", "").replace("`", "")
            if stripped.startswith("|") and set(stripped.replace("|", "").replace(":", "").replace("-", "").strip()) == set():
                continue
            if stripped.startswith("|"):
                stripped = " | ".join(cell.strip() for cell in stripped.strip("|").split("|"))
        wrapped = textwrap.wrap(stripped, width=92, replace_whitespace=False) if stripped else [""]
        lines.extend(wrapped)
    return lines or ["Engineering report"]


def _pdf_text(value: str) -> bytes:
    value = value.encode("latin-1", errors="replace").decode("latin-1")
    value = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return value.encode("latin-1")


def markdown_report_to_pdf(markdown: str) -> bytes:
    """Render Markdown as a paginated, text-based PDF 1.4 document."""
    if not markdown.strip():
        raise ValueError("Report is empty")

    lines = _plain_lines(markdown)
    pages = [lines[index:index + LINES_PER_PAGE] for index in range(0, len(lines), LINES_PER_PAGE)]
    page_numbers = [4 + 2 * index for index in range(len(pages))]

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Count {len(pages)} /Kids [{' '.join(f'{number} 0 R' for number in page_numbers)}] >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for index, page_lines in enumerate(pages):
        page_number = page_numbers[index]
        content_number = page_number + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_number} 0 R >>".encode()
        )
        commands = [f"BT /F1 {FONT_SIZE} Tf {MARGIN} {PAGE_HEIGHT - MARGIN} Td {LEADING} TL".encode()]
        commands.extend(b"(" + _pdf_text(line) + b") Tj T*" for line in page_lines)
        commands.append(b"ET")
        stream = b"\n".join(commands)
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")

    document = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(document))
        document.extend(f"{number} 0 obj\n".encode())
        document.extend(body)
        document.extend(b"\nendobj\n")

    xref_offset = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode())
    document.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(document)

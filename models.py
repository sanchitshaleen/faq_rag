from dataclasses import dataclass, field
from typing import Optional

@dataclass
class TableData:
    """Represents a table extracted from a document."""
    headers: list[str]
    rows: list[list[str]]
    bbox: tuple  # (x0, y0, x1, y1)
    page_num: int

    def to_text(self) -> str:
        """Convert table to readable text for display."""
        lines = [" | ".join(self.headers)]
        lines.append("-" * len(lines[0]))
        for row in self.rows:
            lines.append(" | ".join(str(cell) for cell in row))
        return "\n".join(lines)

    def to_html(self) -> str:
        """Convert table to HTML for rich display."""
        html = '<table border="1" cellpadding="4" cellspacing="0">'
        html += "<tr>" + "".join(f"<th>{h}</th>" for h in self.headers) + "</tr>"
        for row in self.rows:
            html += "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
        html += "</table>"
        return html


@dataclass
class QAPair:
    """Represents a single question-answer pair extracted from an FAQ."""
    faq_id: str
    question: str
    answer_text: str
    answer_table: Optional[TableData] = None
    source_doc: str = ""
    page_num: int = 0
    section: str = ""
    bbox: tuple = ()  # bounding box of the Q-A region on the page
    
    # Extended DOCX Metadata fields
    product: str = ""
    audience: str = ""
    pi_url: str = ""
    ml_url: str = ""
    delivery_status: str = ""
    active_assets: str = ""
    clinical_terms: str = ""
    
    # Nested Channel specific answers
    channels: dict = field(default_factory=dict)

    def full_answer(self) -> str:
        """Return the complete answer including table text."""
        parts = [self.answer_text]
        if self.answer_table:
            parts.append("\n" + self.answer_table.to_text())
        return "\n".join(parts)

    def full_answer_html(self) -> str:
        """Return the complete answer with table as HTML."""
        parts = [f"<p>{self.answer_text}</p>"]
        if self.answer_table:
            parts.append(self.answer_table.to_html())
        return "\n".join(parts)

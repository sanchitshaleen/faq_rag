import docx
from docx.document import Document as _Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

from models import QAPair

def iter_block_items(parent):
    """
    Yield each paragraph and table child within *parent*, in document order.
    Each returned value is an instance of either Table or Paragraph.
    """
    if isinstance(parent, _Document):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise ValueError("something's not right")

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)

def parse_docx_faq(file_path: str) -> list[QAPair]:
    """
    Parse a DOCX FAQ document containing anchored sections with metadata tables
    and channel-specific responses.
    """
    doc = docx.Document(file_path)
    
    qa_pairs = []
    
    current_anchor = None
    current_metadata = {}
    current_answers = {"voicebot": [], "whatsapp": [], "webchat": [], "email": [], "general": []}
    current_channel = "general"
    in_faq_block = False
    
    for block in iter_block_items(doc):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if not text:
                continue
                
            if text.endswith(":") and text.isupper() and not " " in text and not text.startswith("["):
                # Potential new anchor
                if in_faq_block and current_metadata:
                    # Save the previous block before starting a new one
                    _save_faq(qa_pairs, current_metadata, current_answers, file_path, current_anchor)
                    current_answers = {"voicebot": [], "whatsapp": [], "webchat": [], "email": [], "general": []}
                
                current_anchor = text[:-1]
                current_metadata = {}
                current_channel = "general"
                in_faq_block = True
                continue
                
            if text == "===END===":
                if in_faq_block and current_metadata:
                    _save_faq(qa_pairs, current_metadata, current_answers, file_path, current_anchor)
                
                current_anchor = None
                current_metadata = {}
                current_answers = {"voicebot": [], "whatsapp": [], "webchat": [], "email": [], "general": []}
                current_channel = "general"
                in_faq_block = False
                continue
                
            if in_faq_block:
                if text.startswith("["):
                    # Detect channel switch
                    if ":" in text:
                        tag_part, rest = text.split(":", 1)
                        tag_upper = tag_part.upper()
                        if tag_upper == "[VOICEBOT]":
                            current_channel = "voicebot"
                            text = rest.strip()
                        elif tag_upper == "[WHATSAPP]":
                            current_channel = "whatsapp"
                            text = rest.strip()
                        elif tag_upper == "[WEBCHAT]":
                            current_channel = "webchat"
                            text = rest.strip()
                        elif tag_upper == "[EMAIL]":
                            current_channel = "email"
                            text = rest.strip()
                        elif tag_part.endswith("]"):
                            text = f"**{tag_part}:** {rest.strip()}"
                    else:
                        tag_upper = text.upper()
                        if tag_upper == "[VOICEBOT]":
                            current_channel = "voicebot"
                            text = ""
                        elif tag_upper == "[WHATSAPP]":
                            current_channel = "whatsapp"
                            text = ""
                        elif tag_upper == "[WEBCHAT]":
                            current_channel = "webchat"
                            text = ""
                        elif tag_upper == "[EMAIL]":
                            current_channel = "email"
                            text = ""
                        elif text.endswith("]"):
                            text = f"**{text}**"
                            
                elif text.startswith("·"):
                    text = f"- {text[1:].strip()}"
                
                if text:
                    current_answers[current_channel].append(text)
                
        elif isinstance(block, Table):
            if in_faq_block and not current_metadata:
                # This should be the metadata table right after the anchor
                for row in block.rows:
                    if len(row.cells) == 2:
                        key = row.cells[0].text.strip()
                        val = row.cells[1].text.strip()
                        current_metadata[key] = val
            elif in_faq_block:
                # Inner table in answer? (Not seen in sample, but handled gracefully)
                current_answers[current_channel].append("[TBD: Embedded Table]")
    
    # Catch any dangling block at the end of the document
    if in_faq_block and current_metadata:
        _save_faq(qa_pairs, current_metadata, current_answers, file_path, current_anchor)
        
    return qa_pairs

def _save_faq(qa_pairs_list, metadata, answers_dict, file_path, section_anchor):
    question = metadata.get("Question theme", "")
    base_id = metadata.get("VV_DOC_ID", "")
    
    if base_id and section_anchor:
        faq_id = f"{base_id}_{section_anchor}"
    elif base_id:
        faq_id = base_id
    else:
        faq_id = section_anchor or "UNKNOWN_ID"
        
    channels = {
        "voicebot": "\n\n".join(answers_dict["voicebot"]),
        "whatsapp": "\n\n".join(answers_dict["whatsapp"]),
        "webchat": "\n\n".join(answers_dict["webchat"]),
        "email": "\n\n".join(answers_dict["email"])
    }
    ans_general = "\n\n".join(answers_dict["general"])
    
    # Keep answer_text as a fallback full representation
    answer_text = "\n\n".join(filter(None, [ans_general, channels["voicebot"], channels["whatsapp"], channels["webchat"], channels["email"]]))
    
    if question or answer_text:
        qa_pairs_list.append(QAPair(
            faq_id=faq_id,
            question=question,
            answer_text=answer_text,
            source_doc=file_path.split('/')[-1],
            section=section_anchor or "",
            product=metadata.get("Product", ""),
            audience=metadata.get("Audience", ""),
            pi_url=metadata.get("Prescribing Info URL", ""),
            ml_url=metadata.get("Medical Letter URL", ""),
            delivery_status=metadata.get("Delivery_status", ""),
            active_assets=metadata.get("Active_assets", ""),
            clinical_terms=metadata.get("Key clinical terms", ""),
            channels=channels
        ))

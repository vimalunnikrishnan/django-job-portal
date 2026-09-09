import os
import re

from PyPDF2 import PdfReader
from docx import Document


def extract_text_from_pdf(file):
    reader = PdfReader(file)

    text = []

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text.append(page_text)

    return "\n".join(text)


def extract_text_from_docx(file):
    document = Document(file)

    text = []

    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            text.append(paragraph.text)

    return "\n".join(text)


def clean_text(text):
    # Remove unnecessary spaces around line breaks
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)

    # Join words that are unnecessarily split across lines
    text = re.sub(r"(?<=\w)\n(?=\w)", " ", text)

    # Replace multiple spaces or tabs with one space
    text = re.sub(r"[ \t]+", " ", text)

    # Remove excessive blank lines
    text = re.sub(r"\n{2,}", "\n\n", text)

    # Remove leading and trailing whitespace
    text = text.strip()

    return text


def extract_resume_text(file):
    filename = file.name.lower()

    if filename.endswith(".pdf"):
        text = extract_text_from_pdf(file)

    elif filename.endswith(".docx"):
        text = extract_text_from_docx(file)

    else:
        raise ValueError(
            "Unsupported file format. Only PDF and DOCX files are supported."
        )

    return clean_text(text)
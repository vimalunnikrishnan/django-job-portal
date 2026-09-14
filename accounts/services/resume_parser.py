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
    """
    Clean and normalize extracted resume text.
    """

    # Normalize line endings
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Remove spaces around line breaks
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)

    # Fix hyphenated words split across lines
    # Example:
    # entry-
    # level -> entry-level
    text = re.sub(r"(?<=\w)-\n(?=\w)", "-", text)

    # Fix words broken across lines by PDF extraction
    # Example:
    # Deve
    # loper -> Developer
    split_word_fixes = {
        r"\bDeve\nloper\b": "Developer",
        r"\bComput\ner\b": "Computer",
        r"\bPowerShel\nl\b": "PowerShell",
        r"\bSecon\ndary\b": "Secondary",
        r"\bRelations\nhips\b": "Relationships",
    }

        # Fix common PDF extraction artifacts
    spacing_fixes = {
        r"\bdatabases\b": "databases",
        r"\bdatabase\s+s\b": "databases",
        r"\bRelations\s+hips\b": "Relationships",
        r"\bPowerShel\s+l\b": "PowerShell",
        r"\bSecon\s+dary\b": "Secondary",
        r"\bDev\s+eloper\b": "Developer",
    }

    for pattern, replacement in spacing_fixes.items():
        text = re.sub(
            pattern,
            replacement,
            text,
            flags=re.IGNORECASE,
        )

    for pattern, replacement in split_word_fixes.items():
        text = re.sub(
            pattern,
            replacement,
            text,
            flags=re.IGNORECASE,
        )

    # Fix spaces around hyphens
    text = re.sub(r"\s*-\s*", "-", text)

    # Now join normal line breaks between words
    # Example:
    # Worked with
    # Django -> Worked with Django
    text = re.sub(r"(?<=\w)\n(?=\w)", " ", text)

    # Replace multiple spaces/tabs with one space
    text = re.sub(r"[ \t]+", " ", text)

    # Remove excessive blank lines
    text = re.sub(r"\n{2,}", "\n\n", text)

    # Strip whitespace from each line
    lines = [
        line.strip()
        for line in text.split("\n")
    ]

    text = "\n".join(lines)

    return text.strip()


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
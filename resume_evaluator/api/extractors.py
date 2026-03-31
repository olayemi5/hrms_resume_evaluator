import frappe
import requests
from pathlib import Path
import tempfile
from pdfplumber import open as open_pdf
from docx import Document
from resume_evaluator.api.logger import info, warning, error


# ─────────────────────────────────────────────
# File Download
# ─────────────────────────────────────────────

def download_file(file_url):
    """
    Returns a local Path to the file.
    - Local Frappe files are resolved directly.
    - External URLs are downloaded to a temp file.
    """
    if file_url.startswith("/"):
        return Path(frappe.get_site_path()) / file_url.lstrip("/"), False

    r = requests.get(file_url, timeout=30)
    r.raise_for_status()
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_url).suffix)
    temp_file.write(r.content)
    temp_file.close()
    return Path(temp_file.name), True


# ─────────────────────────────────────────────
# Text Extraction
# ─────────────────────────────────────────────

def extract_text_from_file(file_path):
    """Extract plain text from PDF or DOCX files."""
    file_path = Path(file_path)

    if not file_path.exists():
        error(f"File not found: {file_path}")
        frappe.log_error(f"File not found: {file_path}", "Resume Extraction")
        return ""

    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return _extract_from_pdf(file_path)
    elif suffix == ".docx":
        return _extract_from_docx(file_path)
    else:
        warning(f"Unsupported file type: {suffix} — {file_path}")
        frappe.log_error(f"Unsupported file type: {suffix}", "Resume Extraction")
        return ""


def _extract_from_pdf(file_path):
    try:
        text = ""
        with open_pdf(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text
    except Exception as e:
        error(f"PDF extraction failed: {file_path} — {e}")
        frappe.log_error(f"PDF extraction failed for {file_path}: {e}", "Resume Extraction")
        return ""


def _extract_from_docx(file_path):
    try:
        doc = Document(file_path)
        return "\n".join(para.text for para in doc.paragraphs)
    except Exception as e:
        error(f"DOCX extraction failed: {file_path} — {e}")
        frappe.log_error(f"DOCX extraction failed for {file_path}: {e}", "Resume Extraction")
        return ""


# ─────────────────────────────────────────────
# Collect all file URLs for an applicant
# ─────────────────────────────────────────────

def _get_file_urls(applicant_name):
    """Get all resume file URLs from both the resume_attachment field and File doctype."""
    urls = set()

    # 1. Check the resume_attachment / resume_link field directly on Job Applicant
    doc = frappe.get_doc("Job Applicant", applicant_name)
    for field in ("resume_attachment", "resume_link", "cover_letter"):
        val = getattr(doc, field, None)
        if val and isinstance(val, str) and (val.startswith("/") or val.startswith("http")):
            # cover_letter is usually HTML text, skip if it looks like HTML
            if field == "cover_letter" and "<" in val:
                continue
            urls.add(val)

    # 2. Check File doctype for any attached files
    files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Job Applicant",
            "attached_to_name": applicant_name,
        },
        fields=["file_url"],
    )
    for f in files:
        if f.get("file_url"):
            urls.add(f["file_url"])

    return list(urls)


# ─────────────────────────────────────────────
# Resume Text Aggregator
# ─────────────────────────────────────────────

def get_resume_text(applicant_name):
    """Download and extract text from all resume files for a Job Applicant."""
    file_urls = _get_file_urls(applicant_name)

    if not file_urls:
        warning(f"No files found for {applicant_name} (checked resume_attachment field + File doctype)")
        return ""

    info(f"Found {len(file_urls)} file(s) for {applicant_name}: {file_urls}")

    all_text = ""
    for file_url in file_urls:
        try:
            file_path, is_temp = download_file(file_url)
            text = extract_text_from_file(file_path)
            all_text += text

            if is_temp:
                try:
                    file_path.unlink(missing_ok=True)
                except Exception:
                    pass

            if text:
                info(f"Extracted {len(text)} chars from {file_url}")
            else:
                warning(f"No text extracted from {file_url}")

        except Exception as e:
            error(f"Failed to process {file_url} for {applicant_name}: {e}")
            frappe.log_error(
                f"Failed to process file {file_url} for {applicant_name}: {e}",
                "Resume Extraction",
            )

    return all_text

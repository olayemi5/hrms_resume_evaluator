import frappe
import requests
from pathlib import Path
import tempfile
from pdfplumber import open as open_pdf
from docx import Document


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
        return Path(frappe.get_site_path()) / file_url.lstrip("/"), False  # False = not temp

    r = requests.get(file_url, timeout=30)
    r.raise_for_status()
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_url).suffix)
    temp_file.write(r.content)
    temp_file.close()
    return Path(temp_file.name), True  # True = is temp, should be deleted after


# ─────────────────────────────────────────────
# Text Extraction
# ─────────────────────────────────────────────

def extract_text_from_file(file_path):
    """Extract plain text from PDF or DOCX files."""
    text = ""
    file_path = Path(file_path)

    if not file_path.exists():
        frappe.log_error(f"File not found: {file_path}", "Resume Extraction")
        return text

    if file_path.suffix.lower() == ".pdf":
        text = _extract_from_pdf(file_path)
    elif file_path.suffix.lower() == ".docx":
        text = _extract_from_docx(file_path)
    else:
        frappe.log_error(
            f"Unsupported file type: {file_path.suffix}", "Resume Extraction"
        )

    return text


def _extract_from_pdf(file_path):
    text = ""
    try:
        with open_pdf(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    except Exception as e:
        frappe.log_error(f"PDF extraction failed for {file_path}: {e}", "Resume Extraction")
    return text


def _extract_from_docx(file_path):
    text = ""
    try:
        doc = Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    except Exception as e:
        frappe.log_error(f"DOCX extraction failed for {file_path}: {e}", "Resume Extraction")
    return text


# ─────────────────────────────────────────────
# Resume Text Aggregator
# ─────────────────────────────────────────────

def get_resume_text(applicant_name):
    """Download and extract text from all files attached to a Job Applicant."""
    files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Job Applicant",
            "attached_to_name": applicant_name,
        },
        fields=["file_url", "file_name"],
    )

    if not files:
        print(f"[CV Evaluator] No files attached to {applicant_name}")
        return ""

    all_text = ""
    for f in files:
        file_url = f["file_url"]
        try:
            file_path, is_temp = download_file(file_url)
            all_text += extract_text_from_file(file_path)

            # Clean up temp files (external downloads only)
            if is_temp:
                try:
                    file_path.unlink(missing_ok=True)
                    print(f"[CV Evaluator] Removed temp file: {file_path}")
                except Exception as e:
                    frappe.log_error(
                        f"Failed to remove temp file {file_path}: {e}",
                        "Resume Cleanup",
                    )
        except Exception as e:
            frappe.log_error(
                f"Failed to process file {file_url} for {applicant_name}: {e}",
                "Resume Extraction",
            )

    return all_text

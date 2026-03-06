import frappe
from resume_evaluator.api.fields import ensure_custom_fields, ensure_settings_doctype
from resume_evaluator.api.ai_clients import get_ai_client
from resume_evaluator.api.extractors import get_resume_text
from resume_evaluator.api.score_resume import score_resume_text


# ─────────────────────────────────────────────
# DB Helpers
# ─────────────────────────────────────────────

def get_unprocessed_applicants():
    return frappe.get_all(
        "Job Applicant",
        filters={"custom_evaluation_done": 0},
        fields=["name", "job_title", "applicant_name", "email_id"],
    )


def update_applicant(applicant_name, score, summary):
    doc = frappe.get_doc("Job Applicant", applicant_name)
    doc.custom_match_score = score
    doc.custom_match_summary = summary
    doc.custom_evaluation_done = 1
    doc.save(ignore_permissions=True)
    frappe.db.commit()


# ─────────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────────

def process_all_unprocessed():
    """
    Main task -- run via:
        bench execute resume_evaluator.tasks.process_all_unprocessed
    Or schedule in hooks.py.
    """

    # Step 1 -- Ensure the settings DocType exists
    ensure_settings_doctype()

    # Step 2 -- Ensure custom fields exist on Job Applicant
    ensure_custom_fields()

    # Step 3 -- Get AI client based on configured provider
    client, provider, model = get_ai_client()
    if client is None:
        print("[CV Evaluator] Aborting -- AI client could not be initialized.")
        return

    # Step 4 -- Process unprocessed applicants
    applicants = get_unprocessed_applicants()
    if not applicants:
        print("[CV Evaluator] No unprocessed applicants found.")
        return

    print(f"[CV Evaluator] Found {len(applicants)} applicant(s) to process.")

    for a in applicants:
        applicant_name = a["name"]
        job_opening_name = a["job_title"]
        full_name = a.get("applicant_name") or ""
        email = a.get("email_id") or ""

        print(f"[CV Evaluator] Processing: {applicant_name}")

        job_desc = frappe.get_value("Job Opening", job_opening_name, "description") or ""

        resume_text = get_resume_text(applicant_name)
        if not resume_text.strip():
            frappe.log_error(
                f"No resume text found for {applicant_name}", "Resume Processing"
            )
            print(f"[CV Evaluator] WARNING: Skipping {applicant_name} - no resume text.")
            continue

        score, summary = score_resume_text(
            client, provider, model,
            resume_text, job_desc,
            applicant_name=full_name,
            applicant_email=email
        )
        update_applicant(applicant_name, score, summary)
        print(f"[CV Evaluator] OK: {applicant_name} - Score: {score}")

    print("[CV Evaluator] Done.")

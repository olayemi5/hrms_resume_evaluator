import frappe

# ─────────────────────────────────────────────
# Custom fields to create on Job Applicant
# ─────────────────────────────────────────────

REQUIRED_CUSTOM_FIELDS = [
    {
        "fieldname": "custom_evaluation_done",
        "label": "Evaluation Done",
        "fieldtype": "Check",
        "default": "0",
        "insert_after": "cover_letter",
    },
    {
        "fieldname": "custom_match_score",
        "label": "Match Score",
        "fieldtype": "Int",
        "insert_after": "custom_evaluation_done",
    },
    {
        "fieldname": "custom_match_summary",
        "label": "Match Summary",
        "fieldtype": "Small Text",
        "insert_after": "custom_match_score",
    },
]

REQUIRED_SETTING_FIELDS = [
    "ai_provider", "openai_model", "gemini_model",
    "openai_bot_key", "gemini_bot_key",
    "min_score_threshold", "summary_max_length"
]


def ensure_custom_fields():
    """Create any missing custom fields on Job Applicant."""
    for field_def in REQUIRED_CUSTOM_FIELDS:
        exists = frappe.db.exists(
            "Custom Field",
            {"dt": "Job Applicant", "fieldname": field_def["fieldname"]},
        )
        if not exists:
            cf = frappe.get_doc({
                "doctype": "Custom Field",
                "dt": "Job Applicant",
                **field_def,
            })
            cf.insert(ignore_permissions=True)
            frappe.db.commit()
            print(f"[CV Evaluator] Created custom field: {field_def['fieldname']}")
        else:
            print(f"[CV Evaluator] Field already exists: {field_def['fieldname']}")


def ensure_settings_doctype():
    """
    Create the 'Cv Evaluator Settings' Single DocType with all required fields.
    If it already exists but is missing fields, delete and recreate it.
    """
    if frappe.db.exists("DocType", "Cv Evaluator Settings"):
        # Check if all required fields exist
        existing_fields = frappe.get_all(
            "DocField",
            filters={"parent": "Cv Evaluator Settings"},
            pluck="fieldname"
        )
        missing = [f for f in REQUIRED_SETTING_FIELDS if f not in existing_fields]

        if not missing:
            print("[CV Evaluator] Cv Evaluator Settings DocType already exists with all fields.")
            return

        # Missing fields found — delete and recreate
        print(f"[CV Evaluator] Missing fields {missing} — recreating Cv Evaluator Settings...")
        frappe.delete_doc("DocType", "Cv Evaluator Settings", ignore_missing=True, force=True)
        frappe.db.commit()

    # Create the DocType fresh
    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": "Cv Evaluator Settings",
        "module": "Resume Evaluator",
        "is_single": 1,
        "custom": 1,
        "fields": [
            # ── AI Provider Selection ──────────────────────────
            {
                "fieldname": "ai_provider",
                "label": "AI Provider",
                "fieldtype": "Select",
                "options": "OpenAI\nGemini",
                "default": "OpenAI",
                "reqd": 1,
                "in_list_view": 1,
            },
            # ── Model Selection ────────────────────────────────
            {
                "fieldname": "openai_model",
                "label": "OpenAI Model",
                "fieldtype": "Select",
                "options": "gpt-4\ngpt-4-turbo\ngpt-3.5-turbo",
                "default": "gpt-4",
                "depends_on": "eval:doc.ai_provider=='OpenAI'",
            },
            {
                "fieldname": "gemini_model",
                "label": "Gemini Model",
                "fieldtype": "Select",
                "options": "gemini-1.5-pro\ngemini-1.5-flash\ngemini-pro",
                "default": "gemini-1.5-pro",
                "depends_on": "eval:doc.ai_provider=='Gemini'",
            },
            # ── API Keys ───────────────────────────────────────
            {
                "fieldname": "section_keys",
                "label": "API Keys",
                "fieldtype": "Section Break",
            },
            {
                "fieldname": "openai_bot_key",
                "label": "OpenAI API Key",
                "fieldtype": "Password",
                "depends_on": "eval:doc.ai_provider=='OpenAI'",
		"length": 300,
            },
            {
                "fieldname": "gemini_bot_key",
                "label": "Gemini API Key",
                "fieldtype": "Password",
                "depends_on": "eval:doc.ai_provider=='Gemini'",
		"length": 300,
            },
            # ── Scoring Settings ───────────────────────────────
            {
                "fieldname": "section_scoring",
                "label": "Scoring Settings",
                "fieldtype": "Section Break",
            },
            {
                "fieldname": "min_score_threshold",
                "label": "Minimum Score Threshold",
                "fieldtype": "Int",
                "default": "0",
                "description": "Applicants scoring below this will be flagged in logs",
            },
            {
                "fieldname": "summary_max_length",
                "label": "Summary Max Length (chars)",
                "fieldtype": "Int",
                "default": "1000",
            },
        ],
        "permissions": [
            {
                "role": "System Manager",
                "read": 1,
                "write": 1,
            }
        ],
    })

    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    print("[CV Evaluator] Created 'Cv Evaluator Settings' DocType successfully.")

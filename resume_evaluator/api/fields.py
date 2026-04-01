import frappe

# ─────────────────────────────────────────────
# Custom fields to create on Job Applicant
# ─────────────────────────────────────────────

REQUIRED_CUSTOM_FIELDS = [
    # ── Evaluation Section (permlevel 1 = internal staff only) ──
    {
        "fieldname": "custom_cv_evaluation_section",
        "label": "CV Evaluation",
        "fieldtype": "Section Break",
        "insert_after": "cover_letter",
        "permlevel": 1,
    },
    {
        "fieldname": "custom_evaluation_done",
        "label": "Evaluation Done",
        "fieldtype": "Check",
        "default": "0",
        "insert_after": "custom_cv_evaluation_section",
        "read_only": 1,
        "permlevel": 1,
    },
    {
        "fieldname": "custom_match_score",
        "label": "Match Score",
        "fieldtype": "Int",
        "insert_after": "custom_evaluation_done",
        "read_only": 1,
        "permlevel": 1,
    },
    {
        "fieldname": "custom_match_summary",
        "label": "Match Summary",
        "fieldtype": "Small Text",
        "insert_after": "custom_match_score",
        "read_only": 1,
        "permlevel": 1,
    },
    # ── Security Section ──
    {
        "fieldname": "custom_cv_security_section",
        "label": "CV Security",
        "fieldtype": "Section Break",
        "insert_after": "custom_match_summary",
        "permlevel": 1,
    },
    {
        "fieldname": "custom_security_flag",
        "label": "Security Flag",
        "fieldtype": "Select",
        "options": "\nClean\nInjection Detected\nIdentity Mismatch",
        "insert_after": "custom_cv_security_section",
        "read_only": 1,
        "permlevel": 1,
    },
    {
        "fieldname": "custom_security_note",
        "label": "Security Note",
        "fieldtype": "Small Text",
        "insert_after": "custom_security_flag",
        "read_only": 1,
        "permlevel": 1,
    },
    # ── CV Insights Section ──
    {
        "fieldname": "custom_cv_insights_section",
        "label": "CV Insights",
        "fieldtype": "Section Break",
        "insert_after": "custom_security_note",
        "permlevel": 1,
    },
    {
        "fieldname": "custom_skills",
        "label": "Skills",
        "fieldtype": "Small Text",
        "insert_after": "custom_cv_insights_section",
        "read_only": 1,
        "permlevel": 1,
    },
    {
        "fieldname": "custom_education",
        "label": "Education",
        "fieldtype": "Small Text",
        "insert_after": "custom_skills",
        "read_only": 1,
        "permlevel": 1,
    },
    {
        "fieldname": "custom_years_of_experience",
        "label": "Years of Experience",
        "fieldtype": "Data",
        "insert_after": "custom_education",
        "read_only": 1,
        "permlevel": 1,
    },
    {
        "fieldname": "custom_cv_column_break",
        "fieldtype": "Column Break",
        "insert_after": "custom_years_of_experience",
        "permlevel": 1,
    },
    {
        "fieldname": "custom_previous_employments",
        "label": "Previous Employments",
        "fieldtype": "Text",
        "insert_after": "custom_cv_column_break",
        "read_only": 1,
        "permlevel": 1,
    },
    {
        "fieldname": "custom_referees",
        "label": "Referees",
        "fieldtype": "Text",
        "insert_after": "custom_previous_employments",
        "read_only": 1,
        "permlevel": 1,
    },
    {
        "fieldname": "custom_other_insights",
        "label": "Other Insights",
        "fieldtype": "Small Text",
        "insert_after": "custom_referees",
        "read_only": 1,
        "permlevel": 1,
    },
]

REQUIRED_SETTING_FIELDS = [
    "ai_provider", "openai_model", "gemini_model",
    "openai_bot_key", "gemini_bot_key",
    "min_score_threshold", "summary_max_length",
    "rejection_email_template", "acceptance_email_template",
]

SETTINGS_DOCTYPE_FIELDS = [
    {
        "fieldname": "ai_provider",
        "label": "AI Provider",
        "fieldtype": "Select",
        "options": "OpenAI\nGemini",
        "default": "OpenAI",
        "reqd": 1,
        "in_list_view": 1,
    },
    {
        "fieldname": "openai_model",
        "label": "OpenAI Model",
        "fieldtype": "Select",
        "options": "gpt-4\ngpt-4-turbo\ngpt-3.5-turbo\ngpt-4o\ngpt-4o-mini",
        "default": "gpt-4o-mini",
        "depends_on": "eval:doc.ai_provider=='OpenAI'",
    },
    {
        "fieldname": "gemini_model",
        "label": "Gemini Model",
        "fieldtype": "Select",
        "options": "gemini-1.5-pro\ngemini-1.5-flash\ngemini-pro\ngemini-2.0-flash",
        "default": "gemini-1.5-flash",
        "depends_on": "eval:doc.ai_provider=='Gemini'",
    },
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
        "description": "Below threshold: auto-rejected with email. At or above: welcome email with portal access.",
    },
    {
        "fieldname": "summary_max_length",
        "label": "Summary Max Length (chars)",
        "fieldtype": "Int",
        "default": "1000",
    },
    {
        "fieldname": "section_email_templates",
        "label": "Email Templates",
        "fieldtype": "Section Break",
    },
    {
        "fieldname": "rejection_email_template",
        "label": "Rejection Email Template",
        "fieldtype": "Text Editor",
        "description": "Available variables: {{ applicant_name }}, {{ job_title }}",
        "default": """
<p>Dear {{ applicant_name or 'Applicant' }},</p>
<p>Thank you for your interest in the <strong>{{ job_title }}</strong> position
and for taking the time to submit your application.</p>
<p>After careful review, we regret to inform you that we are unable to
proceed with your application at this time.</p>
<p>We encourage you to apply for future openings that match your profile.
We wish you the very best in your career.</p>
<p>Kind regards</p>
""".strip(),
    },
    {
        "fieldname": "acceptance_email_template",
        "label": "Acceptance Email Template",
        "fieldtype": "Text Editor",
        "description": "Available variables: {{ applicant_name }}, {{ job_title }}, {{ setup_link }}, {{ portal_link }}",
        "default": """
<p>Dear {{ applicant_name or 'Applicant' }},</p>
<p>Thank you for applying for the <strong>{{ job_title }}</strong> position.
We have received your application and it is currently under review.</p>
<p>We have created a portal account for you where you can track the
status of your application(s).</p>
<p><strong>Set up your account:</strong><br>
<a href="{{ setup_link }}">{{ setup_link }}</a></p>
<p>Once your password is set, you can log in anytime to check your
application status at:<br>
<a href="{{ portal_link }}">{{ portal_link }}</a></p>
<p>We will be in touch as the review progresses.</p>
<p>Kind regards</p>
""".strip(),
    },
]


def ensure_custom_fields():
    """Create any missing custom fields on Job Applicant."""
    for field_def in REQUIRED_CUSTOM_FIELDS:
        if frappe.db.exists(
            "Custom Field",
            {"dt": "Job Applicant", "fieldname": field_def["fieldname"]},
        ):
            continue
        cf = frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "Job Applicant",
            **field_def,
        })
        cf.insert(ignore_permissions=True)
    frappe.db.commit()


def ensure_settings_doctype():
    """Create the 'Cv Evaluator Settings' Single DocType if missing or incomplete."""
    if frappe.db.exists("DocType", "Cv Evaluator Settings"):
        existing_fields = frappe.get_all(
            "DocField",
            filters={"parent": "Cv Evaluator Settings"},
            pluck="fieldname",
        )
        missing = [f for f in REQUIRED_SETTING_FIELDS if f not in existing_fields]
        if not missing:
            return
        frappe.delete_doc("DocType", "Cv Evaluator Settings", ignore_missing=True, force=True)
        frappe.db.commit()

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": "Cv Evaluator Settings",
        "module": "Resume Evaluator",
        "is_single": 1,
        "custom": 1,
        "fields": SETTINGS_DOCTYPE_FIELDS,
        "permissions": [{"role": "System Manager", "read": 1, "write": 1}],
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

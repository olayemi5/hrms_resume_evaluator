import frappe
from resume_evaluator.api.fields import ensure_settings_doctype, ensure_custom_fields


def after_install():
    """Auto-setup on app install: create settings doctype, custom fields, and permissions."""
    ensure_settings_doctype()
    ensure_custom_fields()
    _ensure_permlevel_access()
    frappe.db.commit()


def _ensure_permlevel_access():
    """Grant permlevel 1 read on Job Applicant to HR Manager and System Manager.

    This ensures only these desk roles can see the CV evaluation fields.
    Website User (permlevel 0 only) will never see them.
    """
    for role in ("HR Manager", "System Manager"):
        exists = frappe.db.exists("Custom DocPerm", {
            "parent": "Job Applicant",
            "role": role,
            "permlevel": 1,
        })
        if exists:
            continue

        doc = frappe.get_doc("DocType", "Job Applicant")
        doc.append("permissions", {
            "role": role,
            "permlevel": 1,
            "read": 1,
            "write": 0,
        })
        doc.save(ignore_permissions=True)

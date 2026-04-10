import frappe
from resume_evaluator.api.fields import ensure_settings_doctype, ensure_custom_fields


def after_install():
    """Auto-setup on app install: create settings doctype, custom fields, and permissions."""
    ensure_settings_doctype()
    ensure_custom_fields()
    ensure_permlevel_access()
    frappe.db.commit()


def ensure_permlevel_access():
    """Grant permlevel 1 read on Job Applicant to desk roles via direct SQL.

    Frappe validation requires permlevel 0 to exist before level 1.
    Some roles (e.g. HR Manager) may only have level 0 via Custom DocPerm
    or not at all, so we insert directly to bypass that check.
    """
    for role in ("HR Manager", "System Manager", "HR User"):
        has_level_one = frappe.db.sql("""
            SELECT name FROM `tabDocPerm`
            WHERE parent = 'Job Applicant' AND role = %s AND permlevel = 1
        """, (role,))
        if has_level_one:
            continue

        # Also check Custom DocPerm
        has_custom_level_one = frappe.db.exists("Custom DocPerm", {
            "parent": "Job Applicant",
            "role": role,
            "permlevel": 1,
        })
        if has_custom_level_one:
            continue

        # Insert directly to avoid Frappe's permlevel 0 validation
        frappe.db.sql("""
            INSERT INTO `tabDocPerm`
            (name, parent, parenttype, parentfield, role, permlevel, `read`, `write`)
            VALUES (%s, 'Job Applicant', 'DocType', 'permissions', %s, 1, 1, 0)
        """, (frappe.generate_hash(length=10), role))

    frappe.db.commit()

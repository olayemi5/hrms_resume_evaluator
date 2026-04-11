import frappe
from resume_evaluator.api.fields import ensure_settings_doctype, ensure_custom_fields


def after_install():
    """Auto-setup on app install: create settings doctype, custom fields, and permissions."""
    ensure_settings_doctype()
    ensure_custom_fields()
    ensure_permlevel_access()
    frappe.db.commit()


def ensure_permlevel_access():
    """Grant permlevel 1 read on Job Applicant to desk roles.

    If Custom DocPerm entries exist for Job Applicant, Frappe ignores
    tabDocPerm entirely, so we must insert into both tables.
    """
    has_custom = frappe.db.exists("Custom DocPerm", {"parent": "Job Applicant"})

    for role in ("HR Manager", "System Manager", "HR User"):
        # Insert into tabDocPerm
        if not frappe.db.sql("""
            SELECT name FROM `tabDocPerm`
            WHERE parent = 'Job Applicant' AND role = %s AND permlevel = 1
        """, (role,)):
            frappe.db.sql("""
                INSERT INTO `tabDocPerm`
                (name, parent, parenttype, parentfield, role, permlevel, `read`, `write`)
                VALUES (%s, 'Job Applicant', 'DocType', 'permissions', %s, 1, 1, 0)
            """, (frappe.generate_hash(length=10), role))

        # If Custom DocPerm is in use, insert there too
        if has_custom and not frappe.db.exists("Custom DocPerm", {
            "parent": "Job Applicant", "role": role, "permlevel": 1,
        }):
            frappe.db.sql("""
                INSERT INTO `tabCustom DocPerm`
                (name, parent, parenttype, parentfield, role, permlevel, `read`, `write`)
                VALUES (%s, 'Job Applicant', 'DocType', 'permissions', %s, 1, 1, 0)
            """, (frappe.generate_hash(length=10), role))

    frappe.db.commit()

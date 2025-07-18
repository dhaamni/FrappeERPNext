import unittest
import frappe
from frappe.tests import IntegrationTestCase

# Utility functions to create test data
from erpnext.buying.doctype.purchase_order.test_purchase_order import create_purchase_order
from erpnext.buying.doctype.supplier.test_supplier import create_supplier

# Test class for verifying portal access permissions for a custom doctype via webform
class TestWebsite(IntegrationTestCase):
    def test_permission_for_custom_doctype(self):
        # Create two website users with "Supplier" role
        create_user("Supplier 1", "supplier1@gmail.com")
        create_user("Supplier 2", "supplier2@gmail.com")

        # Create two supplier records
        supplier1 = create_supplier(supplier_name="Supplier1")
        supplier2 = create_supplier(supplier_name="Supplier2")

        # Link each user to their respective supplier record
        supplier1.append("portal_users", {"user": "supplier1@gmail.com"})
        supplier1.save()
        supplier2.append("portal_users", {"user": "supplier2@gmail.com"})
        supplier2.save()

        # Create two Purchase Orders, each assigned to a different supplier
        po1 = create_purchase_order(supplier="Supplier1")
        po2 = create_purchase_order(supplier="Supplier2")

        # Setup custom doctype and webform for testing
        create_custom_doctype()
        create_webform()

        # Create Order Assignment records for both suppliers
        create_order_assignment(supplier="Supplier1", po=po1.name)
        create_order_assignment(supplier="Supplier2", po=po2.name)

        # Check that the dataset includes order assignments from both suppliers
        self.assertTrue("Supplier1" and "Supplier2" in [data.supplier for data in get_data()])

        # Switch context to supplier1 and test access restriction
        with self.set_user("supplier1@gmail.com"):
            # Ensure supplier1 can see their own assignments
            self.assertTrue("Supplier1" in [data.supplier for data in get_data()])
            # Ensure no records from other suppliers are visible
            self.assertFalse([data.supplier for data in get_data() if data.supplier != "Supplier1"])

        # Switch context to supplier2 and test access restriction
        with self.set_user("supplier2@gmail.com"):
            # Ensure supplier2 can see their own assignments
            self.assertTrue("Supplier2" in [data.supplier for data in get_data()])
            # Ensure no records from other suppliers are visible
            self.assertFalse([data.supplier for data in get_data() if data.supplier != "Supplier2"])


# Fetches webform list data for "Order Assignment"
def get_data():
    webform_list_contexts = frappe.get_hooks("webform_list_context")
    if webform_list_contexts:
        # Load context for the Buying module webform
        context = frappe._dict(frappe.get_attr(webform_list_contexts[0])("Buying") or {})
    kwargs = dict(doctype="Order Assignment", order_by="creation desc")
    return context.get_list(**kwargs)


# Creates a new website user with Supplier role
def create_user(name, email):
    frappe.get_doc(
        {
            "doctype": "User",
            "send_welcome_email": 0,
            "user_type": "Website User",
            "first_name": name,
            "email": email,
            "roles": [{"doctype": "Has Role", "role": "Supplier"}],
        }
    ).insert(ignore_if_duplicate=True)


# Defines and creates a custom doctype "Order Assignment"
def create_custom_doctype():
    frappe.get_doc(
        {
            "doctype": "DocType",
            "name": "Order Assignment",
            "module": "Buying",
            "custom": 1,
            "autoname": "field:po",
            "fields": [
                {"label": "PO", "fieldname": "po", "fieldtype": "Link", "options": "Purchase Order"},
                {
                    "label": "Supplier",
                    "fieldname": "supplier",
                    "fieldtype": "Data",
                    "fetch_from": "po.supplier",
                },
            ],
            # Permissions: Full for System Manager, Read-only for Supplier role
            "permissions": [
                {
                    "create": 1,
                    "delete": 1,
                    "email": 1,
                    "export": 1,
                    "print": 1,
                    "read": 1,
                    "report": 1,
                    "role": "System Manager",
                    "share": 1,
                    "write": 1,
                },
                {"read": 1, "role": "Supplier"},
            ],
        }
    ).insert(ignore_if_duplicate=True)


# Creates a Web Form for the "Order Assignment" doctype
def create_webform():
    frappe.get_doc(
        {
            "doctype": "Web Form",
            "module": "Buying",
            "title": "SO Schedule",
            "route": "so-schedule",
            "doc_type": "Order Assignment",
            "web_form_fields": [
                {
                    "doctype": "Web Form Field",
                    "fieldname": "po",
                    "fieldtype": "Link",
                    "options": "Purchase Order",
                    "label": "PO",
                },
                {
                    "doctype": "Web Form Field",
                    "fieldname": "supplier",
                    "fieldtype": "Data",
                    "label": "Supplier",
                },
            ],
        }
    ).insert(ignore_if_duplicate=True)


# Inserts a new Order Assignment record linking a supplier with a PO
def create_order_assignment(supplier, po):
    frappe.get_doc(
        {
            "doctype": "Order Assignment",
            "po": po,
            "supplier": supplier,
        }
    ).insert(ignore_if_duplicate=True)

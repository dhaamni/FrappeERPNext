import frappe


def execute():
	for pgc in frappe.get_list("Payment Gateway Account", fields=["name", "payment_account"]):
		company = frappe.db.get_value("Account", pgc.payment_account, "company")
		frappe.db.set_value("Payment Gateway Account", pgc.name, "company", company)

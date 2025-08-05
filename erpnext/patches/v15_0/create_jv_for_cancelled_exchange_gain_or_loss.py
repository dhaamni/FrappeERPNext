import frappe
from frappe.query_builder import DocType
from pypika.terms import ExistsCriterion


def execute():
	companies = frappe.get_all("Company", pluck="name")
	for company in companies:
		last_pcv_date = frappe.db.get_value(
			"Period Closing Voucher", {"docstatus": 1, "company": company}, [{"MAX": "period_end_date"}]
		)
		start_date = (
			frappe.utils.add_days(last_pcv_date, 1)
			if last_pcv_date
			else frappe.db.get_value(
				"GL Entry", {"is_cancelled": 0, "company": company}, [{"MIN": "posting_date"}]
			)
		)

		if not start_date:
			continue

		JournalEntry = DocType("Journal Entry")
		JournalEntryAccount = DocType("Journal Entry Account")
		PaymentEntry = DocType("Payment Entry")
		PaymentEntryReference = DocType("Payment Entry Reference")

		jea2 = DocType("Journal Entry Account").as_("jea2")

		subquery = (
			frappe.qb.from_(jea2)
			.select(jea2.reference_name)
			.where(
				(jea2.parent == JournalEntry.name)
				& (jea2.reference_type != "Payment Entry")
				& (jea2.reference_name == PaymentEntryReference.reference_name)
			)
		)

		query = (
			frappe.qb.from_(JournalEntry)
			.join(JournalEntryAccount)
			.on(JournalEntryAccount.parent == JournalEntry.name)
			.join(PaymentEntry)
			.on(PaymentEntry.name == JournalEntryAccount.reference_name)
			.join(PaymentEntryReference)
			.on(PaymentEntryReference.parent == PaymentEntry.name)
			.select(JournalEntryAccount.reference_name)
			.distinct()
			.where(
				(JournalEntry.is_system_generated == 1)
				& (JournalEntry.voucher_type == "Exchange Gain Or Loss")
				& (JournalEntry.docstatus == 2)
				& (JournalEntry.company == company)
				& (JournalEntry.posting_date >= start_date)
				& (JournalEntryAccount.reference_type == "Payment Entry")
				& (PaymentEntry.docstatus == 1)
				& ExistsCriterion(subquery)
			)
		)

		pe_jv_against_cancelled_exchange_gain_or_loss_jv = query.run(as_dict=True)
		for pe_or_jv in pe_jv_against_cancelled_exchange_gain_or_loss_jv:
			pe_doc = frappe.get_doc("Payment Entry", pe_or_jv.get("reference_name"))
			pe_doc.make_exchange_gain_loss_journal()

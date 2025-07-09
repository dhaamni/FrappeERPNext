import frappe
from frappe import qb
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, getdate, today

from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice
from erpnext.accounts.report.customer_ledger_summary.customer_ledger_summary import execute
from erpnext.accounts.test.accounts_mixin import AccountsTestMixin


class TestCustomerLedgerSummary(FrappeTestCase, AccountsTestMixin):
	def setUp(self):
		self.create_company()
		self.create_customer()
		self.create_item()
		self.clear_old_entries()

	def tearDown(self):
		frappe.db.rollback()

	def create_sales_invoice(self, do_not_submit=False, **args):
		si = create_sales_invoice(
			item=self.item,
			company=self.company,
			customer=self.customer,
			debit_to=self.debit_to,
			posting_date=today(),
			parent_cost_center=self.cost_center,
			cost_center=self.cost_center,
			rate=100,
			qty=10,
			price_list_rate=100,
			do_not_save=1,
			**args,
		)
		si = si.save()
		if not do_not_submit:
			si = si.submit()
		return si

	def create_payment_entry(self, docname, do_not_submit=False):
		pe = get_payment_entry("Sales Invoice", docname, bank_account=self.cash, party_amount=40)
		pe.paid_from = self.debit_to
		pe.insert()
		if not do_not_submit:
			pe.submit()
		return pe

	def create_credit_note(self, docname, do_not_submit=False):
		credit_note = create_sales_invoice(
			company=self.company,
			customer=self.customer,
			item=self.item,
			qty=-1,
			debit_to=self.debit_to,
			cost_center=self.cost_center,
			is_return=1,
			return_against=docname,
			do_not_submit=do_not_submit,
		)

		return credit_note

	def test_ledger_summary_basic_output(self):
		filters = {"company": self.company, "from_date": today(), "to_date": today()}

		si = self.create_sales_invoice(do_not_submit=True)
		si.save().submit()

		expected = {
			"party": "_Test Customer",
			"party_name": "_Test Customer",
			"opening_balance": 0,
			"invoiced_amount": 1000.0,
			"paid_amount": 0,
			"return_amount": 0,
			"closing_balance": 1000.0,
			"currency": "INR",
			"customer_name": "_Test Customer",
		}

		report = execute(filters)[1]
		self.assertEqual(len(report), 1)
		for field in expected:
			with self.subTest(field=field):
				self.assertEqual(report[0].get(field), expected.get(field))

	def test_summary_with_return_and_payment(self):
		filters = {"company": self.company, "from_date": today(), "to_date": today()}

		si = self.create_sales_invoice(do_not_submit=True)
		si.save().submit()

		expected = {
			"party": "_Test Customer",
			"party_name": "_Test Customer",
			"opening_balance": 0,
			"invoiced_amount": 1000.0,
			"paid_amount": 0,
			"return_amount": 0,
			"closing_balance": 1000.0,
			"currency": "INR",
			"customer_name": "_Test Customer",
		}

		report = execute(filters)[1]
		self.assertEqual(len(report), 1)
		for field in expected:
			with self.subTest(field=field):
				self.assertEqual(report[0].get(field), expected.get(field))

		cr_note = self.create_credit_note(si.name, True)
		cr_note.items[0].qty = -2
		cr_note.save().submit()

		expected_after_cr_note = {
			"party": "_Test Customer",
			"party_name": "_Test Customer",
			"opening_balance": 0,
			"invoiced_amount": 1000.0,
			"paid_amount": 0,
			"return_amount": 200.0,
			"closing_balance": 800.0,
			"currency": "INR",
		}
		report = execute(filters)[1]
		self.assertEqual(len(report), 1)
		for field in expected_after_cr_note:
			with self.subTest(field=field):
				self.assertEqual(report[0].get(field), expected_after_cr_note.get(field))

		pe = self.create_payment_entry(si.name, True)
		pe.paid_amount = 500
		pe.save().submit()

		expected_after_cr_and_payment = {
			"party": "_Test Customer",
			"party_name": "_Test Customer",
			"opening_balance": 0,
			"invoiced_amount": 1000.0,
			"paid_amount": 500.0,
			"return_amount": 200.0,
			"closing_balance": 300.0,
			"currency": "INR",
		}

		report = execute(filters)[1]
		self.assertEqual(len(report), 1)
		for field in expected_after_cr_and_payment:
			with self.subTest(field=field):
				self.assertEqual(report[0].get(field), expected_after_cr_and_payment.get(field))

	def test_journal_voucher_against_return_invoice(self):
		filters = {
			"company": self.company,
			"from_date": "2025-01-01",
			"to_date": "2025-12-31",
			"party_type": "Customer",
		}

		# Create first Sales Invoice (1000.0)
		si1 = self.create_sales_invoice(rate=1000, qty=1, posting_date="2025-01-01", do_not_submit=True)
		si1.save().submit()

		# Create Payment Entry (Receive) for first invoice - full payment (1000.0)
		pe1 = get_payment_entry("Sales Invoice", si1.name, bank_account=self.cash, party_amount=1000)
		pe1.paid_from = self.debit_to
		pe1.paid_amount = 1000
		pe1.received_amount = 1000
		pe1.insert()
		pe1.submit()

		# Create Credit Note (return invoice) for first invoice (1000.0)
		cr_note = self.create_credit_note(si1.name, do_not_submit=True)
		cr_note.items[0].qty = -1
		cr_note.items[0].rate = 1000
		cr_note.posting_date = "2025-01-01"
		cr_note.save().submit()

		# Create Payment Entry for the returned amount (1000.0) - Pay the customer back
		pe2 = get_payment_entry("Sales Invoice", cr_note.name, bank_account=self.cash)
		pe2.posting_date = "2025-01-01"
		pe2.insert()
		pe2.submit()

		# Create second Sales Invoice (500.0)
		si2 = self.create_sales_invoice(rate=500, qty=1, posting_date="2025-01-01", do_not_submit=True)
		si2.save().submit()

		# Create Payment Entry (Receive) for second invoice - full payment (500.0)
		pe3 = get_payment_entry("Sales Invoice", si2.name, bank_account=self.cash, party_amount=500)
		pe3.paid_from = self.debit_to
		pe3.paid_amount = 500
		pe3.received_amount = 500
		pe3.insert()
		pe3.submit()

		# Run the report
		report = execute(filters)[1]
		self.assertEqual(len(report), 1, "Report should return exactly one row")

		expected = {
			"party": "_Test Customer",
			"party_name": "_Test Customer",
			"opening_balance": 0.0,
			"invoiced_amount": 1500.0,  # si1 (1000) + si2 (500)
			"paid_amount": 500.0,  # pe3 (500)
			"return_amount": 1000.0,  # Credit note amount
			"closing_balance": 0.0,
			"currency": "INR",
			"customer_name": "_Test Customer",
		}

		for field in expected:
			with self.subTest(field=field):
				actual_value = report[0].get(field)
				expected_value = expected.get(field)
				self.assertEqual(
					actual_value,
					expected_value,
					f"Field {field} does not match expected value. "
					f"Expected: {expected_value}, Got: {actual_value}",
				)

# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe.test_runner import make_test_records
from frappe.tests import IntegrationTestCase

from erpnext.accounts.doctype.financial_report_template.report_engine import (
	AccountResolver,
	DataFormatter,
	DependencyResolver,
	FinancialReportEngine,
	FormulaCalculator,
)
from erpnext.accounts.doctype.financial_report_template.utils import (
	BalanceProcessor,
	FilterExpressionParser,
	PeriodAccountDataCollector,
)

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class TestFinancialReportTemplate(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		"""Set up test data"""
		make_test_records("Company")
		make_test_records("Fiscal Year")
		make_test_records("Sales Invoice")
		make_test_records("Purchase Invoice")
		cls.create_test_template()

	@classmethod
	def create_test_template(cls):
		"""Create a test financial report template"""
		if not frappe.db.exists("Financial Report Template", "Test P&L Template"):
			template = frappe.get_doc(
				{
					"doctype": "Financial Report Template",
					"template_name": "Test P&L Template",
					"report_type": "Profit and Loss Statement",
					"rows": [
						{
							"reference_code": "INC001",
							"display_name": "Income",
							"indentation_level": 0,
							"row_type": "Account Data",
							"data_source": "Closing Balance",
							"bold_text": 1,
							"calculation_formula": '["root_type", "=", "Income"]',
						},
						{
							"reference_code": "EXP001",
							"display_name": "Expenses",
							"indentation_level": 0,
							"row_type": "Account Data",
							"data_source": "Closing Balance",
							"bold_text": 1,
							"calculation_formula": '["root_type", "=", "Expense"]',
						},
						{
							"reference_code": "NET001",
							"display_name": "Net Profit/Loss",
							"indentation_level": 0,
							"row_type": "Formula/Calculation",
							"bold_text": 1,
							"calculation_formula": "INC001 - EXP001",
						},
					],
				}
			)
			template.insert()

		cls.test_template = frappe.get_doc("Financial Report Template", "Test P&L Template")

	def test_dependency_resolver(self):
		"""Test dependency resolution"""
		resolver = DependencyResolver(self.test_template.rows)
		order = resolver.get_processing_order()

		# Should process account rows before formula rows
		account_indices = [i for i, row in enumerate(order) if row.row_type == "Account Data"]
		formula_indices = [i for i, row in enumerate(order) if row.row_type == "Formula/Calculation"]

		self.assertTrue(all(ai < fi for ai in account_indices for fi in formula_indices))

	def test_formula_calculator(self):
		"""Test formula calculation"""
		# Mock row data
		row_data = {"INC001": [1000.0, 1200.0, 1500.0], "EXP001": [800.0, 900.0, 1100.0]}

		period_list = [
			{"key": "2023", "from_date": "2023-01-01", "to_date": "2023-12-31"},
			{"key": "2024", "from_date": "2024-01-01", "to_date": "2024-12-31"},
			{"key": "2025", "from_date": "2025-01-01", "to_date": "2025-12-31"},
		]

		calculator = FormulaCalculator(row_data, period_list)
		result = calculator.evaluate_formula("INC001 - EXP001")

		expected = [200.0, 300.0, 400.0]  # [1000-800, 1200-900, 1500-1100]
		self.assertEqual(result, expected)

	def test_financial_report_engine(self):
		"""Test the main financial report engine"""
		filters = {
			"company": "_Test Company",
			"filter_based_on": "Fiscal Year",
			"from_fiscal_year": "2023-24",
			"to_fiscal_year": "2023-24",
			"periodicity": "Yearly",
			"accumulated_values": 1,
		}

		# This test would require proper test data setup
		# For now, just test that the engine initializes
		engine = FinancialReportEngine("Test P&L Template", filters)
		self.assertEqual(engine.template_name, "Test P&L Template")
		self.assertEqual(engine.filters, filters)

	def test_template_validation(self):
		"""Test template validation"""
		# Test duplicate reference codes
		with self.assertRaises(frappe.ValidationError):
			template = frappe.get_doc(
				{
					"doctype": "Financial Report Template",
					"template_name": "Invalid Template",
					"rows": [
						{"reference_code": "DUP001", "display_name": "Row 1", "row_type": "Account Data"},
						{
							"reference_code": "DUP001",  # Duplicate
							"display_name": "Row 2",
							"row_type": "Account Data",
						},
					],
				}
			)
			template.validate()

	def test_circular_reference_detection(self):
		"""Test circular reference detection"""
		with self.assertRaises(frappe.ValidationError):
			template = frappe.get_doc(
				{
					"doctype": "Financial Report Template",
					"template_name": "Circular Template",
					"rows": [
						{
							"reference_code": "A001",
							"display_name": "Row A",
							"row_type": "Formula/Calculation",
							"calculation_formula": "B001 + 100",
						},
						{
							"reference_code": "B001",
							"display_name": "Row B",
							"row_type": "Formula/Calculation",
							"calculation_formula": "A001 + 200",  # Circular reference
						},
					],
				}
			)
			template.validate()

	@classmethod
	def tearDownClass(cls):
		"""Clean up test data"""
		frappe.db.rollback()

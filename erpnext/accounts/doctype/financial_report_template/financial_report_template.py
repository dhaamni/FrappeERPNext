# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document


class FinancialReportTemplate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from erpnext.accounts.doctype.financial_report_row.financial_report_row import FinancialReportRow

		disabled: DF.Check
		is_standard: DF.Check
		module: DF.Link | None
		report_type: DF.Literal["", "Profit and Loss Statement", "Balance Sheet"]
		rows: DF.Table[FinancialReportRow]
		template_name: DF.Data
	# end: auto-generated types

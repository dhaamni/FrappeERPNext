# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class LandedCostAllocation(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from erpnext.stock.doctype.landed_cost_item.landed_cost_item import LandedCostItem
		from erpnext.stock.doctype.landed_cost_purchase_receipt.landed_cost_purchase_receipt import LandedCostPurchaseReceipt
		from erpnext.stock.doctype.landed_cost_taxes_and_charges.landed_cost_taxes_and_charges import LandedCostTaxesandCharges
		from frappe.types import DF

		amended_from: DF.Link | None
		company: DF.Link
		distribute_charges_based_on: DF.Literal["Qty", "Amount", "Distribute Manually"]
		items: DF.Table[LandedCostItem]
		naming_series: DF.Literal["MAT-LCV-.YYYY.-"]
		posting_date: DF.Date
		purchase_receipts: DF.Table[LandedCostPurchaseReceipt]
		taxes: DF.Table[LandedCostTaxesandCharges]
		total_taxes_and_charges: DF.Currency
	# end: auto-generated types

	pass

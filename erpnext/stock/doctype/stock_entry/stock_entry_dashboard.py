from frappe import _


# Todo: non_standard_fieldnames is to be decided
def get_data():
	return {
		"fieldname": "stock_entry",
		"non_standard_fieldnames": {
			# "DocType Name": "Reference field name",
		},
		"transactions": [
<<<<<<< HEAD
			{
				"label": _("Reference"),
				"items": [
					"Purchase Order",
					"Subcontracting Order",
					"Subcontracting Receipt",
				],
			},
=======
			{"label": _("Stock Reservation"), "items": ["Stock Reservation Entry"]},
>>>>>>> 6d82e3cc28 (fix: remove incorrect references from stock entry dashboard/connections tab)
		],
	}

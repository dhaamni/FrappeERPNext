frappe.listview_settings["Sales Order"] = {
	hide_name_column: true,
	get_indicator: function (doc) {
		if (doc.status === "Closed") {
			// Closed
			return [__("Closed"), "green", "status,=,Closed"];
		} else if (doc.status === "On Hold") {
			// on hold
			return [__("On Hold"), "orange", "status,=,On Hold"];
		} else if (doc.status === "Completed") {
			return [__("Completed"), "green", "status,=,Completed"];
		} else if (!doc.skip_delivery_note && flt(doc.per_delivered) < 100) {
			if (frappe.datetime.get_diff(doc.delivery_date) < 0) {
				// not delivered & overdue
				return [
					__("Overdue"),
					"red",
					"per_delivered,<,100|delivery_date,<,Today|status,!=,Closed|docstatus,=,1",
				];
			} else if (flt(doc.grand_total) === 0) {
				// not delivered (zeroount order)
				return [
					__("To Deliver"),
					"orange",
					"per_delivered,<,100|grand_total,=,0|status,!=,Closed|docstatus,=,1",
				];
			} else if (flt(doc.per_billed) < 100) {
				// not delivered & not billed
				return [
					__("To Deliver and Bill"),
					"orange",
					"per_delivered,<,100|per_billed,<,100|status,!=,Closed",
				];
			} else {
				// not billed
				return [__("To Deliver"), "orange", "per_delivered,<,100|per_billed,=,100|status,!=,Closed"];
			}
		} else if (
			flt(doc.per_delivered) === 100 &&
			flt(doc.grand_total) !== 0 &&
			flt(doc.per_billed) < 100
		) {
			// to bill
			return [__("To Bill"), "orange", "per_delivered,=,100|per_billed,<,100|status,!=,Closed"];
		} else if (doc.skip_delivery_note && flt(doc.per_billed) < 100) {
			return [__("To Bill"), "orange", "per_billed,<,100|status,!=,Closed"];
		}
	},
	onload: function (listview) {
		var method = "erpnext.selling.doctype.sales_order.sales_order.close_or_unclose_sales_orders";

		listview.page.add_menu_item(__("Close"), function () {
			listview.call_for_selected_items(method, { status: "Closed" });
		});

		listview.page.add_menu_item(__("Re-open"), function () {
			listview.call_for_selected_items(method, { status: "Submitted" });
		});

		if (frappe.model.can_create("Sales Invoice")) {
			listview.page.add_action_item(__("Sales Invoice"), () => {
				erpnext.bulk_transaction_processing.create(listview, "Sales Order", "Sales Invoice");
			});
		}

		if (frappe.model.can_create("Delivery Note")) {
			listview.page.add_action_item(__("Delivery Note"), () => {
				erpnext.bulk_transaction_processing.create(listview, "Sales Order", "Delivery Note");
			});
		}

		if (frappe.model.can_create("Payment Entry")) {
			listview.page.add_action_item(__("Advance Payment"), () => {
				erpnext.bulk_transaction_processing.create(listview, "Sales Order", "Payment Entry");
			});
		}
	},

	refresh: function (listview) {
		// Hide the 3rd column (docstatus) in the list view using jQuery
		$(".result .list-header-subject > div:nth-child(3), .result .list-row-container .list-row-col:nth-child(3)").css("display", "none");

		// Observe DOM changes to hide new 3rd columns dynamically
		const observer = new MutationObserver(function(mutations) {
			mutations.forEach(function(mutation) {
				$(mutation.addedNodes).each(function() {
					if ($(this).is('.list-row-container') || $(this).find('.list-row-col:nth-child(3)').length) {
						$('.result .list-row-container .list-row-col:nth-child(3)').css('display', 'none');
					}
				});
			});
		});
		observer.observe(document.querySelector('.result'), { childList: true, subtree: true });
	}
};

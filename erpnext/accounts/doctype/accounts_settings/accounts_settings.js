// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Accounts Settings", {
	refresh: function (frm) {},
<<<<<<< HEAD
=======
	enable_immutable_ledger: function (frm) {
		if (!frm.doc.enable_immutable_ledger) {
			return;
		}

		let msg = __("Enabling this will change the way how cancelled transactions are handled.");
		msg += " ";
		msg += __("Please enable only if the understand the effects of enabling this.");
		msg += "<br>";
		msg += __("Do you still want to enable immutable ledger?");

		frappe.confirm(
			msg,
			() => {},
			() => {
				frm.set_value("enable_immutable_ledger", 0);
			}
		);
	},

	add_taxes_from_taxes_and_charges_template(frm) {
		toggle_tax_settings(frm, "add_taxes_from_taxes_and_charges_template");
	},

	add_taxes_from_item_tax_template(frm) {
		toggle_tax_settings(frm, "add_taxes_from_item_tax_template");
	},

	drop_ar_procedures: function (frm) {
		frm.call({
			doc: frm.doc,
			method: "drop_ar_sql_procedures",
			callback: function (r) {
				frappe.show_alert(__("Procedures dropped"), 5);
			},
		});
	},
>>>>>>> da32bb5f51 (refactor: utility to drop existing procedures and include cost center)
});

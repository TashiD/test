// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Test Bar', {
	refresh: function(frm) {

	},
	item_code: function(frm) {
		frappe.msgprint("this is called")
	}
});

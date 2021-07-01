// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
frappe.require("assets/erpnext/js/financial_statements1.js", function() {

	frappe.query_reports["Expenditure Statement"] = erpnext.financial_statements;
	
	frappe.query_reports["Expenditure Statement"]["filters"].push(
		//Custom filter to query based on "Cost Center"
		{
			"fieldname": "cost_center",
			"label": __("Cost Center"),
			"fieldtype": "Link",
			"options": "Cost Center",
			"get_query": function() {return {'filters': [['Cost Center', 'is_disabled', '!=', '1']]}}
		},
		{
			"fieldname": "accumulated_values",
			"label": __("Accumulated Values"),
			"fieldtype": "Check",
		},
		{
			"fieldname": "show_zero_values",
			"label": __("Show zero values"),
			"fieldtype": "Check"
		},
		);
	});
	

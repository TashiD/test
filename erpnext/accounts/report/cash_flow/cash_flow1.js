// Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Cash Flow"] = {
        "filters": [
                {
                        "fieldname": "cost_center",
                        "label": __("Cost Center"),
                        "fieldtype": "Link",
                        "options": "Cost Center",
                },
                {
                        "fieldname": "from_date",
                        "label": __("From Date"),
                        "fieldtype": "Date"
                },
                {
                        "fieldname": "to_date",
                        "label": __("To Date"),
                        "fieldtype": "Date"
                },
        ]
}

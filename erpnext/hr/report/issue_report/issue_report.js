// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Issue Report"] = {
	"filters": [
                {
                        "fieldname":"from_date",
                        "label": ("From Date"),
                        "fieldtype": "Date",
                        "width": "80",
                        "reqd": 1,
			"default": frappe.datetime.year_start()
                },
                {
                        "fieldname":"to_date",
                        "label": ("To Date"),
                        "fieldtype": "Date",
                        "width": "80",
                        "reqd": 1,
			"default": frappe.datetime.year_end()
		},
		{
                        "fieldname":"module",
                        "label": ("Module"),
                        "fieldtype": "Select",
                        "options": ['', 'Human Resources', 'Accounts', 'Assets Management', 'Budget Management', 'Fleet Management', 'Material Management', 'Projects'],
                        "width": "100"
                },
		{
                        "fieldname":"issue_type",
                        "label": ("Issue Type"),
                        "fieldtype": "Select",
                        "options": ['', 'Bug', 'New Requirement'],
                        "width": "100"
                },
		{
                        "fieldname":"status",
                        "label": ("Status"),
                        "fieldtype": "Select",
                        "options": ['', 'New', 'In-discussion', 'In-development', 'On-Hold', 'Closed'],
                        "width": "100"
                }
		
	]

}

// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.query_reports["Monthly Salary Register"] = {
	"filters": [
		{
			"fieldname":"month",
			"label": __("Month"),
			"fieldtype": "Select",
			"options": "\nJan\nFeb\nMar\nApr\nMay\nJun\nJul\nAug\nSep\nOct\nNov\nDec",
			"default": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", 
				"Dec"][frappe.datetime.str_to_obj(frappe.datetime.get_today()).getMonth()],
		},
		{
			"fieldname":"fiscal_year",
			"label": __("Fiscal Year"),
			"fieldtype": "Link",
			"options": "Fiscal Year",
			"default": sys_defaults.fiscal_year,
		},
		{
			"fieldname":"employee",
			"label": __("Employee"),
			"fieldtype": "Link",
			"options": "Employee"
		},
		{
                        "fieldname":"employment_type",
                        "label": __("Employment Type"),
                        "fieldtype": "Link",
                        "options": "Employment Type"
                },
		{
			"fieldname":"company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company")
		},
		{
			"fieldname": "process_status",
			"label": __("Status"),
			"fieldtype": "Select",
			"options": "All\nSubmitted\nUn-Submitted\nCancelled",
			"default": "Submitted"
		}
	]
}

# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt

def execute(filters=None):
	columns = get_columns();

	data = get_data(filters);
	#data = []
	#for a in datas:
	#	total = flt(a.basic)
	#	frappe.msgprint(str(a))
	#for a in data:
		#frappe.msgprint(str(a))
	return columns, data

def get_columns():
	return [
		("Cost Center") + ":Link/Cost Center:120",
		("Basic Pay") + ":Currency:120",
		("Coporate Allowance")+ ":Currency:120",
		("Contract Allow.") + ":Currency:120",
		("Officiating Allow.") +":Currency:120",
		("Communication Allow.")+":Currency:120",
		("Fuel Allow.") +":Currency:120",
		("Overtime Allow.") +":Currency:=120",
		("PSA Allow.") + ":Currency:120",
		("Transfer Allow.") + ":Currency:120",
		("Housing  Allow.") + ":Currency:120",
		("High Altitude Allow.")+ ":Currency:120",
		("Difficult Allow.") + ":Currency:120",
		("Shift Allow.") + ":Currency:120",
		("Scarcity  Allow.") +":Currency:120",
		("Salary Arrears ") +":Currency:120",
		("PDA Allow.") + ":Currency:120",
                ("Deputation Allow.") + ":Currency:120",
                ("Underground Allow.") +":Currency:120",
                ("Cash Handling Allow. ") +":Currency:120",
                ("Amount") + ":Currency:120"
	]

def get_data(filters):
	if not filters.branch:
		filters.branch = '%'
	from_month = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"].index(filters["from_date"])
	to_month = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"].index(filters["to_date"])
	if from_month <= to_month:
		dates = []
		for a in range (from_month+1, to_month+2):
			if a < 10:
				dates.append('0'+ str(a))
			else:
				dates.append(str(a))
	else:
		frappe.throw("From date cannot be grater than To Date")

	query = ("""select cost_center, SUM(ifnull(basic,0)), SUM(ifnull(corporate,0)), SUM(ifnull(contract,0)), SUM(ifnull(officiating,0)), SUM(ifnull(communication,0)), SUM(ifnull(fuel,0)), SUM(ifnull(overtime,0)), SUM(ifnull(psa,0)), SUM(ifnull(transfer,0)), SUM(ifnull(housing,0)), SUM(ifnull(high,0)), SUM(ifnull(difficult,0)), SUM(ifnull(shift,0)),SUM(ifnull(scarcity,0)),SUM(ifnull(salary,0)), SUM(ifnull(pda,0)), SUM(ifnull(deputation,0)), SUM(ifnull(underground,0)), SUM(ifnull(cash_handling,0)), sum(ifnull(basic,0)+ifnull(corporate,0)+ifnull(contract,0)+ifnull(officiating,0)+ifnull(communication,0)+ifnull(fuel,0)+ifnull(overtime,0)+ifnull(psa,0)+ifnull(transfer,0)+ifnull(housing,0)+ifnull(high,0)+ifnull(difficult,0)+ifnull(shift,0)+ifnull(scarcity,0)+ifnull(salary,0) + ifnull(pda,0)+ ifnull(deputation,0)+ ifnull(underground,0)+ifnull(cash_handling,0)) as Amount FROM

(select (select cost_center from tabEmployee e where e.name = ss.employee) AS cost_center,
(select SUM(sd.amount) FROM `tabSalary Detail` sd WHERE sd.parent = ss.name AND sd.salary_component = 'Basic Pay') AS basic,
(select SUM(sd.amount) FROM `tabSalary Detail` sd WHERE sd.parent = ss.name AND sd.salary_component = 'Corporate Allowance') AS corporate,
(select SUM(sd.amount) FROM `tabSalary Detail` sd WHERE sd.parent = ss.name AND sd.salary_component = 'Contract Allowance') AS contract,
(select SUM(sd.amount) FROM `tabSalary Detail` sd WHERE sd.parent = ss.name AND sd.salary_component = 'Officiating Allowance') AS officiating,
(select SUM(sd.amount) FROM `tabSalary Detail` sd WHERE sd.parent = ss.name AND sd.salary_component = 'Communication Allowance') AS communication,
(select SUM(sd.amount) FROM `tabSalary Detail` sd WHERE sd.parent = ss.name AND sd.salary_component = 'Fuel Allowance') AS fuel,
(select SUM(sd.amount) FROM `tabSalary Detail` sd WHERE sd.parent = ss.name AND sd.salary_component = 'Over Time Allowance') AS overtime,
(select SUM(sd.amount) FROM `tabSalary Detail` sd WHERE sd.parent = ss.name AND sd.salary_component = 'PSA') AS psa,
(select SUM(sd.amount) FROM `tabSalary Detail` sd WHERE sd.parent = ss.name AND sd.salary_component = 'Transfer Allowance') AS transfer,
(select SUM(sd.amount) FROM `tabSalary Detail` sd WHERE sd.parent = ss.name AND sd.salary_component = 'Housing allowance') AS housing,
(select SUM(sd.amount) FROM `tabSalary Detail` sd WHERE sd.parent = ss.name AND sd.salary_component = 'High Altitude allowance') AS high,
(select SUM(sd.amount) FROM `tabSalary Detail` sd WHERE sd.parent = ss.name AND sd.salary_component = 'Difficult area allowance') AS difficult,
(select SUM(sd.amount) FROM `tabSalary Detail` sd WHERE sd.parent = ss.name AND sd.salary_component = 'Shift Allowance') AS shift,
(select SUM(sd.amount) FROM `tabSalary Detail` sd WHERE sd.parent = ss.name AND sd.salary_component = 'Scarcity Allowance') AS scarcity,
(select SUM(sd.amount) FROM `tabSalary Detail` sd WHERE sd.parent = ss.name AND sd.salary_component = 'Salary Arrears') AS salary,
(select SUM(sd.amount) FROM `tabSalary Detail` sd WHERE sd.parent = ss.name AND sd.salary_component = 'PDA') AS pda,
(select SUM(sd.amount) FROM `tabSalary Detail` sd WHERE sd.parent = ss.name AND sd.salary_component = 'Deputation Allowance') AS deputation,
(select SUM(sd.amount) FROM `tabSalary Detail` sd WHERE sd.parent = ss.name AND sd.salary_component = 'Underground Allowance') AS underground,
(select SUM(sd.amount) FROM `tabSalary Detail` sd WHERE sd.parent = ss.name AND sd.salary_component = 'Cash Handling Allowance') AS cash_handling
FROM `tabSalary Slip` ss where ss.docstatus = 1 and ss.branch like %(branch)s and ss.month in %(months)s and ss.fiscal_year = %(fy)s)
AS tab """)

	query += " group by cost_center "
	
	result = frappe.db.sql(query, {"branch":filters.branch, "months": dates, "fy": filters.fiscal_year})
	#frappe.msgprint(type(result))
	#frappe.msgprint("{0}".format(result))
	return result

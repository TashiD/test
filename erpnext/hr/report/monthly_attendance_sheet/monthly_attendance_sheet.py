# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, cint, getdate
from frappe import msgprint, _
from calendar import monthrange
from erpnext.hr.doctype.employee.employee import get_holiday_list_for_employee

def execute(filters=None):
	if not filters: filters = {}

	conditions, filters = get_conditions(filters)
	columns = get_columns(filters)
	att_map = get_attendance_list(conditions, filters)
	emp_map = get_employee_details()

	data = []
	for emp in sorted(att_map):
		emp_det = emp_map.get(emp)
		if not emp_det:
			continue

		row = [emp, emp_det.employee_name, emp_det.branch, emp_det.department, emp_det.designation,
			emp_det.company]

		total_p = total_a = total_t = 0.0
		for day in range(filters["total_days_in_month"]):
			str_date = str(filters.year) + "-" + str(filters.month) + "-" + str(day + 1)
			date = getdate(str_date)
		
			holiday = frappe.db.sql("select 1 from `tabHoliday` where parent = %s and holiday_date = %s", (get_holiday_list_for_employee(emp), str_date))	
			#frappe.msgprint(str(date.weekday()))
			status = att_map.get(emp).get(day + 1, "None")
			status_map = {"Present": "P", "Absent": "A", "Half Day": "H", "Tour": "T", "Leave": "L", "None": ""}
			#frappe.msgprint(str(status))
			if status == "None" and (date.weekday() == 6 or holiday):
				row.append("X")
			else:
				row.append(status_map[status])

			if status == "Present":
				total_p += 1
			elif status == "Absent":
				total_a += 1
			elif status == "Tour":
				total_t += 1
			elif status == "Half Day":
				total_p += 0.5
				total_a += 0.5

		row += [total_p, total_t, total_a]
		data.append(row)

	return columns, data

def get_columns(filters):
	columns = [
		_("Employee") + ":Link/Employee:120", _("Employee Name") + "::140", _("Branch")+ ":Link/Branch:120",
		_("Department") + ":Link/Department:120", _("Designation") + ":Link/Designation:120",
		 _("Company") + ":Link/Company:120"
	]

	for day in range(filters["total_days_in_month"]):
		columns.append(cstr(day+1) +":Data:20")

	columns += [_("Total Present") + ":Float:100", _("Total Tour") + ":Float:100", _("Total Absent") + ":Float:100"]
	return columns

def get_attendance_list(conditions, filters):
	attendance_list = frappe.db.sql("""select employee, day(att_date) as day_of_month,
		status from tabAttendance where docstatus = 1 %s order by employee, att_date""" %
		conditions, filters, as_dict=1)

	att_map = {}
	for d in attendance_list:
		att_map.setdefault(d.employee, frappe._dict()).setdefault(d.day_of_month, "")
		att_map[d.employee][d.day_of_month] = d.status

	return att_map

def get_conditions(filters):
	if not (filters.get("month") and filters.get("year")):
		msgprint(_("Please select month and year"), raise_exception=1)

	filters["month"] = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
		"Dec"].index(filters.month) + 1

	filters["total_days_in_month"] = monthrange(cint(filters.year), filters.month)[1]

	conditions = " and month(att_date) = %(month)s and year(att_date) = %(year)s"

	if filters.get("company"): conditions += " and company = %(company)s"
	if filters.get("employee"): conditions += " and employee = %(employee)s"

	return conditions, filters

def get_employee_details():
	emp_map = frappe._dict()
	for d in frappe.db.sql("""select name, employee_name, designation,
		department, branch, company
		from tabEmployee""", as_dict=1):
		emp_map.setdefault(d.name, d)

	return emp_map

@frappe.whitelist()
def get_attendance_years():
	year_list = frappe.db.sql_list("""select distinct YEAR(att_date) from tabAttendance ORDER BY YEAR(att_date) DESC""")
	if not year_list:
		year_list = [getdate().year]

	return "\n".join(str(year) for year in year_list)

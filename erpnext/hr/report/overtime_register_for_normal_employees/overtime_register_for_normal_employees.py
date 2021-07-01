# # Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# # For license information, please see license.txt

###############Created by Cheten Tshering on 10/09/2020 #############################
from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, cint, getdate, flt
from frappe import msgprint, _
from calendar import monthrange

def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)

	return columns, data

def get_data(filters):
	cond = get_condition(filters)
	data = frappe.db.sql("""
		select 
			oa.name
			,oa.employee
			,oa.employee_name
			,oa.branch
			,oa.posting_date
			,oa.total_hours
			,oa.rate
			,oa.total_amount
			,oa.remarks
		from `tabOvertime Application` oa where 1 = 1 {0} order by oa.posting_date desc""".format(cond))

	return data

def get_condition(filters):
	cond = ""
	if filters.branch:
		cond += " and oa.branch = '{0}'".format(filters.branch)
	# if filters.employee:
	# 	cond += " and oa.employee = '{0}'".format(filters.employee)
	# if filters.from_date and filters.to_date:
		cond += " and oa.posting_date between '{0}' and '{1}'".format(filters.from_date, filters.to_date)
 
	return cond

def get_columns(filters):
        columns = [
                _("OT Name") + ":Link/Overtime Application:100",
                _("Employee") + ":Link/Employee:100",
                _("Employee Name") + "::100",
                _("Branch") + "::150",
				_("Posting Date") + ":Date:100",
                _("Total Hours") + "::100",
                _("Rate") + "::100",
                _("Total Amount") + ":Currency:100",
                _("Remarks") + "::150"
        ]
        return columns



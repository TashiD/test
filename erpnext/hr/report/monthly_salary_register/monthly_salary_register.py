# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
'''
--------------------------------------------------------------------------------------------------------------------------
Version          Author          CreatedOn          ModifiedOn          Remarks
------------ --------------- ------------------ -------------------  -----------------------------------------------------
1.0		  SSK		                   03/08/2016         Taking care of Duplication of columns
--------------------------------------------------------------------------------------------------------------------------                                                                          
'''

from __future__ import unicode_literals
import frappe
from frappe.utils import flt, cstr
from frappe import msgprint, _

def execute(filters=None):
	if not filters: filters = {}
	
	data    = []
        columns = []
        salary_slips = get_salary_slips(filters)
	if not salary_slips:
                return columns, data
        
	columns, earning_types, ded_types = get_columns(salary_slips)
	ss_earning_map = get_ss_earning_map(salary_slips)
	ss_ded_map = get_ss_ded_map(salary_slips)
	
	for ss in salary_slips:
                status = ""
                if ss.docstatus == 1:
                        status = "Submitted"
                elif ss.docstatus == 0:
                        status = "Un-Submitted"
                elif ss.docstatus == 2:
                        status = "Cancelled"
                else:
                        status = str(ss.docstatus)
                        
		row = [ss.employee, ss.employee_name, ss.cid,
			ss.bank_name, ss.bank_account_no, 
			ss.company, ss.branch, ss.department,
                         ss.division, ss.section, ss.employee_grade, ss.designation, ss.employment_type,
			 ss.fiscal_year, ss.month, ss.leave_withut_pay, ss.payment_days,
                         status]
			
		for e in earning_types:
			row.append(ss_earning_map.get(ss.name, {}).get(e))
			
		row += [ss.leave_encashment_amount, ss.gross_pay]
		
		for d in ded_types:
			row.append(ss_ded_map.get(ss.name, {}).get(d))
		
		row += [ss.total_deduction, ss.net_pay]
		
		data.append(row)
	
	return columns, data
	
def get_columns(salary_slips):
	columns = [
		_("Employee") + ":Link/Employee:80", _("Employee Name") + "::140", _("CID") + "::100",
		_("Bank Name")+ "::80", _("Bank A/C#")+"::100", 
		_("Company") + ":Link/Company:120",
                _("Branch") + ":Link/Branch:120", _("Department") + ":Link/Department:120", _("Division") + ":Link/Division:120",
                _("Section") + ":Link/Section:120",_("Grade") + "::80", _("Designation") + ":Link/Designation:120",_("Employment Type") + "::100",
		_("Year") + "::80", _("Month") + "::80", _("Leave Without Pay") + ":Float:130", 
		_("Payment Days") + ":Float:120", _("Status") + "::100"
	]
	earning_types = []
	ded_types     = []

        earning_types = frappe.db.sql_list("""select salary_component from `tabSalary Detail`
                        where amount != 0 and parent in (%s)
                        and parentfield = 'earnings'
                        group by salary_component
                        order by count(*) desc""" % 
                        (', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]))
		
        ded_types = frappe.db.sql_list("""select salary_component from `tabSalary Detail`
                        where amount != 0 and parent in (%s)
                        and parentfield = 'deductions'
                        group by salary_component
                        order by count(*) desc""" % 
                        (', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]))
		
        columns = columns + [(e + ":Currency:120") for e in earning_types] + \
                        ["Leave Encashment Amount:Currency:150", 
                        "Gross Pay:Currency:120"] + [(d + ":Currency:120") for d in ded_types] + \
                        ["Total Deduction:Currency:120", "Net Pay:Currency:120"]

	return columns, earning_types, ded_types
	
def get_salary_slips(filters):
	conditions, filters = get_conditions(filters)
	salary_slips = frappe.db.sql("""select * from `tabSalary Slip` where 1 = 1 %s
		order by employee, month""" % conditions, filters, as_dict=1)

	'''
	if not salary_slips:
		msgprint(_("No salary slip found for month: ") + cstr(filters.get("month")) + 
			_(" and year: ") + cstr(filters.get("fiscal_year")), raise_exception=1)
        '''
	
	return salary_slips
	
def get_conditions(filters):
	conditions = ""
	if filters.get("month"):
		month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", 
			"Dec"].index(filters["month"]) + 1
		filters["month"] = month
		conditions += " and month = %(month)s"
	
	if filters.get("fiscal_year"): conditions += " and fiscal_year = %(fiscal_year)s"
	if filters.get("company"): conditions += " and company = %(company)s"
	if filters.get("employee"): conditions += " and employee = %(employee)s"
	if filters.get("employment_type"): conditions += " and employment_type = %(employment_type)s"	
        if filters.get("process_status") == "All":
                conditions += " and docstatus = docstatus"
        elif filters.get("process_status") == "Submitted":
                conditions += " and docstatus = 1"
        elif filters.get("process_status") == "Un-Submitted":
                conditions += " and docstatus = 0"
        elif filters.get("process_status") == "Cancelled":
                conditions += " and docstatus = 2"

	
	return conditions, filters
	
def get_ss_earning_map(salary_slips):
	ss_earning_map = {}

        ss_earnings = frappe.db.sql("""select parent, salary_component, sum(ifnull(amount,0)) as amount 
                        from `tabSalary Detail` where parent in (%s)
                        and parentfield = 'earnings'
                        group by parent, salary_component
                        """ %
                        (', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]), as_dict=1)
                
        for d in ss_earnings:
                ss_earning_map.setdefault(d.parent, frappe._dict()).setdefault(d.salary_component, [])
                ss_earning_map[d.parent][d.salary_component] = flt(d.amount)
	
	return ss_earning_map

def get_ss_ded_map(salary_slips):
	ss_deductions = frappe.db.sql("""select parent, salary_component, sum(ifnull(amount,0)) as amount 
		from `tabSalary Detail` where parent in (%s)
		and parentfield = 'deductions'
		group by parent, salary_component
		""" %
		(', '.join(['%s']*len(salary_slips))), tuple([d.name for d in salary_slips]), as_dict=1)
	
	ss_ded_map = {}
	for d in ss_deductions:
		ss_ded_map.setdefault(d.parent, frappe._dict()).setdefault(d.salary_component, [])
		ss_ded_map[d.parent][d.salary_component] = flt(d.amount)
	
	return ss_ded_map

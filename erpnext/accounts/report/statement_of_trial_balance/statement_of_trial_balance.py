# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, getdate, formatdate, cstr, rounded
from erpnext.accounts.report.financial_statements_emines \
	import filter_accounts, set_gl_entries_by_account, filter_out_zero_value_rows
from erpnext.accounts.accounts_custom_functions import get_child_cost_centers

value_fields = ("opening_debit", "opening_credit", "debit", "credit", "closing_debit", "closing_credit")

def execute(filters=None):
	validate_filters(filters)
	data = get_data(filters)
	columns = get_columns()
	return columns, data

def validate_filters(filters):

	if not filters.fiscal_year:
		frappe.throw(_("Fiscal Year {0} is required").format(filters.fiscal_year))

	fiscal_year = frappe.db.get_value("Fiscal Year", filters.fiscal_year, ["year_start_date", "year_end_date"], as_dict=True)
	if not fiscal_year:
		frappe.throw(_("Fiscal Year {0} does not exist").format(filters.fiscal_year))
	else:
		filters.year_start_date = getdate(fiscal_year.year_start_date)
		filters.year_end_date = getdate(fiscal_year.year_end_date)

	if not filters.from_date:
		filters.from_date = filters.year_start_date

	if not filters.to_date:
		filters.to_date = filters.year_end_date

	filters.from_date = getdate(filters.from_date)
	filters.to_date = getdate(filters.to_date)

	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date cannot be greater than To Date"))

	if (filters.from_date < filters.year_start_date) or (filters.from_date > filters.year_end_date):
		frappe.msgprint(_("From Date should be within the Fiscal Year. Assuming From Date = {0}")\
			.format(formatdate(filters.year_start_date)))

		filters.from_date = filters.year_start_date

	if (filters.to_date < filters.year_start_date) or (filters.to_date > filters.year_end_date):
		frappe.msgprint(_("To Date should be within the Fiscal Year. Assuming To Date = {0}")\
			.format(formatdate(filters.year_end_date)))
		filters.to_date = filters.year_end_date

def get_data(filters):
	accounts = frappe.db.sql("""select name, account_code, parent_account, account_name, root_type, report_type, lft, rgt
		from `tabAccount` where company=%s order by lft""", filters.company, as_dict=True)

	if not accounts:
		return None

	accounts, accounts_by_name, parent_children_map = filter_accounts(accounts)

	min_lft, max_rgt = frappe.db.sql("""select min(lft), max(rgt) from `tabAccount`
		where company=%s""", (filters.company,))[0]

	gl_entries_by_account = {}

	set_gl_entries_by_account(filters.cost_center, filters.company, filters.from_date,
		filters.to_date, min_lft, max_rgt, gl_entries_by_account, ignore_closing_entries=not flt(filters.with_period_closing_entry))

	opening_balances = get_opening_balances(filters)

	total_row = calculate_values(accounts, gl_entries_by_account, opening_balances, filters)
	accumulate_values_into_parents(accounts, accounts_by_name)

	data = prepare_data(accounts, filters, total_row, parent_children_map)
	data = filter_out_zero_value_rows(data, parent_children_map,
		show_zero_values=filters.get("show_zero_values"))

	return data

def get_opening_balances(filters):
	balance_sheet_opening = get_rootwise_opening_balances(filters, "Balance Sheet")
	pl_opening = get_rootwise_opening_balances(filters, "Profit and Loss")

	balance_sheet_opening.update(pl_opening)
	return balance_sheet_opening


def get_rootwise_opening_balances(filters, report_type):
	additional_conditions = " and posting_date >= %(year_start_date)s" \
		if report_type == "Profit and Loss" else ""

	if not flt(filters.with_period_closing_entry):
		additional_conditions += " and ifnull(voucher_type, '')!='Period Closing Voucher'"

        if filters.cost_center:
		cost_centers = get_child_cost_centers(filters.cost_center)
                additional_conditions += " and cost_center IN %(cost_center)s"
        else:
		cost_centers = filters.cost_center 
	gle = frappe.db.sql("""
		select
			account, sum(debit) as opening_debit, sum(credit) as opening_credit
		from `tabGL Entry`
		where
			company=%(company)s 
			{additional_conditions}
			and (posting_date < %(from_date)s or ifnull(is_opening, 'No') = 'Yes')
			and account in (select name from `tabAccount` where report_type=%(report_type)s)
		group by account""".format(additional_conditions=additional_conditions),
		{
			"company": filters.company,
			"from_date": filters.from_date,
			"report_type": report_type,
			"year_start_date": filters.year_start_date,
                        "cost_center": cost_centers
		},
		as_dict=True)

	opening = frappe._dict()
	for d in gle:
		opening.setdefault(d.account, d)

	return opening

def calculate_values(accounts, gl_entries_by_account, opening_balances, filters):
	init = {
		"opening_debit": 0.0,
		"opening_credit": 0.0,
		"debit": 0.0,
		"credit": 0.0,
		"closing_debit": 0.0,
		"closing_credit": 0.0
	}

	total_row = {
		"account": None,
		"account_name": _("Total"),
		"warn_if_negative": True,
		"opening_debit": 0.0,
		"opening_credit": 0.0,
		"debit": 0.0,
		"credit": 0.0,
		"closing_debit": 0.0,
		"closing_credit": 0.0
	}

	for d in accounts:
		d.update(init.copy())

		# add opening
		d["opening_debit"] = opening_balances.get(d.name, {}).get("opening_debit", 0)
		d["opening_credit"] = opening_balances.get(d.name, {}).get("opening_credit", 0)

		for entry in gl_entries_by_account.get(d.name, []):
			if cstr(entry.is_opening) != "Yes":
				d["debit"] += flt(entry.debit, 3)
				d["credit"] += flt(entry.credit, 3)

		total_row["debit"] += d["debit"]
		total_row["credit"] += d["credit"]


	return total_row

def accumulate_values_into_parents(accounts, accounts_by_name):
	for d in reversed(accounts):
		if d.parent_account:
			for key in value_fields:
				accounts_by_name[d.parent_account][key] += d[key]

def prepare_data(accounts, filters, total_row, parent_children_map):
	data = []
	for d in accounts:
		has_value = False
		row = {
			"account_code": d.account_code,
			"account_name": d.account_name,
			"account": d.name,
			"parent_account": d.parent_account,
			"indent": d.indent,
			"from_date": filters.from_date,
			"to_date": filters.to_date
		}

		prepare_opening_and_closing(d, total_row)

		for key in value_fields:
			row[key] = flt(d.get(key, 0.0), 3)

			if abs(row[key]) >= 0.005:
				# ignore zero values
				has_value = True

		row["has_value"] = has_value
		data.append(row)

	data.extend([{},total_row])

	return data

def get_columns():
	return [
		{
			"fieldname": "account",
			"label": _("Account"),
			"fieldtype": "Link",
			"options": "Account",
			"width": 300
		},
		{
			"fieldname": "account_code",
			"label": _("Account Code"),
			"fieldtype": "Data",
			"width": 100
		},
		{
			"fieldname": "opening_debit",
			"label": _("Opening (Dr)"),
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"fieldname": "opening_credit",
			"label": _("Opening (Cr)"),
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"fieldname": "debit",
			"label": _("Debit"),
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"fieldname": "credit",
			"label": _("Credit"),
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"fieldname": "closing_debit",
			"label": _("Closing (Dr)"),
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"fieldname": "closing_credit",
			"label": _("Closing (Cr)"),
			"fieldtype": "Currency",
			"width": 120
		}
	]

def prepare_opening_and_closing(d, total_row):
	d["closing_debit"] = d["opening_debit"] + d["debit"]
	d["closing_credit"] = d["opening_credit"] + d["credit"]

	if d["closing_debit"] > d["closing_credit"]:
		d["closing_debit"] -= d["closing_credit"]
		d["closing_credit"] = 0.0

	else:
		d["closing_credit"] -= d["closing_debit"]
		d["closing_debit"] = 0.0

	if d["opening_debit"] > d["opening_credit"]:
		d["opening_debit"] -= d["opening_credit"]
		d["opening_credit"] = 0.0

	else:
		d["opening_credit"] -= d["opening_debit"]
		d["opening_debit"] = 0.0

	if str(d.account_name.encode('utf-8')) in ["Asset", "Liabilities", "Equity", "Revenue", "Expense", "Other Comprehensive Income"]:
                total_row['opening_credit'] = total_row['opening_credit'] + d['opening_credit']
                total_row['opening_debit'] = total_row['opening_debit'] + d['opening_debit']
                total_row['closing_credit'] = total_row['closing_credit'] + d['closing_credit']
                total_row['closing_debit'] = total_row['closing_debit'] + d['closing_debit']


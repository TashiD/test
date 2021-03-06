# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
#Modified by Kinley Tshering (kinleytshering@dhi.bt) for cost_center filter

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import (flt, getdate, get_first_day, get_last_day,
	add_months, add_days, formatdate)
from erpnext.accounts.accounts_custom_functions import get_child_cost_centers
from erpnext.accounts.utils import get_fiscal_year


def get_period_list(from_fiscal_year, to_fiscal_year, periodicity, company):
        """Get a list of dict {"from_date": from_date, "to_date": to_date, "key": key, "label": label}
                Periodicity can be (Yearly, Quarterly, Monthly)"""

        fiscal_year = get_fiscal_year_data(from_fiscal_year, to_fiscal_year)
        #validate_fiscal_year(fiscal_year, from_fiscal_year, to_fiscal_year)

        # start with first day, so as to avoid year to_dates like 2-April if ever they occur]
        year_start_date = getdate(fiscal_year.year_start_date)
        year_end_date = getdate(fiscal_year.year_end_date)

	#fy_start_end_date = frappe.db.get_value("Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"])
        #if not fy_start_end_date:
        #        frappe.throw(_("Fiscal Year {0} not found.").format(fiscal_year))
	#
	#year_start_date = get_first_day(getdate('2020-01-01'))
        #year_end_date = getdate(fy_start_end_date[1])

	months_to_add = {
                "Yearly": 12,
                "Half-Yearly": 6,
                "Quarterly": 3,
                "Monthly": 1
        }[periodicity]

        period_list = []

        start_date = year_start_date
        months = get_months(year_start_date, year_end_date)

	for i in range(months // months_to_add):
                period = frappe._dict({
                        "from_date": start_date
                })

                to_date = add_months(start_date, months_to_add)
                start_date = to_date

                if to_date == get_first_day(to_date):
                        # if to_date is the first day, get the last day of previous month
                        to_date = add_days(to_date, -1)

                if to_date <= year_end_date:
                        # the normal case
                        period.to_date = to_date
                else:
                        # if a fiscal year ends before a 12 month period
                        period.to_date = year_end_date

                period.to_date_fiscal_year = get_fiscal_year(period.to_date, company=company)[0]
                period.from_date_fiscal_year_start_date = get_fiscal_year(period.from_date, company=company)[1]

                period_list.append(period)

                if period.to_date == year_end_date:
                        break
	# common processing
        for opts in period_list:
                key = opts["to_date"].strftime("%b_%Y").lower()
                if periodicity == "Monthly":
                        label = formatdate(opts["to_date"], "MMM YYYY")
                else:
                        label = get_label(periodicity, opts["from_date"], opts["to_date"])

                opts.update({
                        "key": key.replace(" ", "_").replace("-", "_"),
                        "label": label,
                        "year_start_date": year_start_date,
                        "year_end_date": year_end_date
                })

        return period_list

def get_fiscal_year_data(from_fiscal_year, to_fiscal_year):
        fiscal_year = frappe.db.sql("""select min(year_start_date) as year_start_date,
                max(year_end_date) as year_end_date from `tabFiscal Year` where
                name between %(from_fiscal_year)s and %(to_fiscal_year)s""",
                {'from_fiscal_year': from_fiscal_year, 'to_fiscal_year': to_fiscal_year}, as_dict=1)

        return fiscal_year[0] if fiscal_year else {}

def get_months(start_date, end_date):
        diff = (12 * end_date.year + end_date.month) - (12 * start_date.year + start_date.month)
        return diff + 1

def get_label(periodicity, from_date, to_date):
	if periodicity=="Yearly":
		if formatdate(from_date, "YYYY") == formatdate(to_date, "YYYY"):
			label = formatdate(from_date, "YYYY")
		else:
			#label = formatdate(from_date, "YYYY") + "-" + formatdate(to_date, "YYYY")
			label = formatdate(to_date, 'YYYY')
	else:
		if formatdate(from_date, "YYYY") == formatdate(to_date, "YYYY"):
			label = formatdate(from_date, "MMM YY") + "-" + formatdate(to_date, "MMM YY")
		else:
			label = formatdate(from_date, "MMM YY") + "-" + formatdate(to_date, "MMM YY")

	return label

def get_data(cost_center, company, root_type, balance_must_be, period_list,
		accumulated_values=1, only_current_fiscal_year=True, ignore_closing_entries=False, show_zero_values=False):
	accounts = get_accounts(company, root_type)
	if not accounts:
		return None

	accounts, accounts_by_name, parent_children_map = filter_accounts(accounts)

	company_currency = frappe.db.get_value("Company", company, "default_currency")

	gl_entries_by_account = {}
	for root in frappe.db.sql("""select lft, rgt from tabAccount
			where root_type=%s and ifnull(parent_account, '') = ''""", root_type, as_dict=1):

		set_gl_entries_by_account(cost_center, company,
			period_list[0]["year_start_date"] if only_current_fiscal_year else None,
			period_list[-1]["to_date"],
			root.lft, root.rgt,
			gl_entries_by_account, ignore_closing_entries=ignore_closing_entries)

	calculate_values(accounts_by_name, gl_entries_by_account, period_list, accumulated_values)
	accumulate_values_into_parents(accounts, accounts_by_name, period_list, accumulated_values)
	out = prepare_data(accounts, balance_must_be, period_list, company_currency)
	out = filter_out_zero_value_rows(out, parent_children_map, show_zero_values)

	if out:
		add_total_row(out, root_type, balance_must_be, period_list, company_currency)

	return out

def calculate_values(accounts_by_name, gl_entries_by_account, period_list, accumulated_values):
	for entries in gl_entries_by_account.values():
		for entry in entries:
			d = accounts_by_name.get(entry.account)
			for period in period_list:
				# check if posting date is within the period
				if entry.posting_date <= period.to_date:
					if accumulated_values or entry.posting_date >= period.from_date:
						d[period.key] = d.get(period.key, 0.0) + flt(entry.debit) - flt(entry.credit)
			if entry.posting_date < period_list[0].year_start_date:
				d["opening_balance"] = d.get("opening_balance", 0.0) + flt(entry.debit) - flt(entry.credit)

def accumulate_values_into_parents(accounts, accounts_by_name, period_list, accumulated_values):
	"""accumulate children's values in parent accounts"""
	for d in reversed(accounts):
		if d.parent_account:
			for period in period_list:
				accounts_by_name[d.parent_account][period.key] = \
					accounts_by_name[d.parent_account].get(period.key, 0.0) + d.get(period.key, 0.0)

			accounts_by_name[d.parent_account]["opening_balance"] = \
				accounts_by_name[d.parent_account].get("opening_balance", 0.0) + d.get("opening_balance", 0.0)

def prepare_data(accounts, balance_must_be, period_list, company_currency):
	data = []
	year_start_date = period_list[0]["year_start_date"].strftime("%Y-%m-%d")
	year_end_date = period_list[-1]["year_end_date"].strftime("%Y-%m-%d")

	for d in accounts:
		# add to output
		has_value = False
		total = 0
		row = frappe._dict({
			"account_name": d.account_name,
			"account_code": d.account_code,
			"account": d.name,
			"is_group": d.is_group,
			"parent_account": d.parent_account,
			"indent": flt(d.indent),
			"year_start_date": year_start_date,
			"year_end_date": year_end_date,
			"currency": company_currency,
			"opening_balance": d.get("opening_balance", 0.0) * (1 if balance_must_be=="Debit" else -1)
		})
		for period in period_list:
			if d.get(period.key) and balance_must_be=="Credit":
				# change sign based on Debit or Credit, since calculation is done using (debit - credit)
				d[period.key] *= -1

			row[period.key] = flt(d.get(period.key, 0.0), 3)

			if abs(row[period.key]) >= 0.005:
				# ignore zero values
				has_value = True
				total += flt(row[period.key])

		row["has_value"] = has_value
		row["total"] = total
		data.append(row)

	return data

def filter_out_zero_value_rows(data, parent_children_map, show_zero_values=False):
	data_with_value = []
	for d in data:
		if show_zero_values or d.get("has_value"):
			data_with_value.append(d)
		else:
			# show group with zero balance, if there are balances against child
			children = [child.name for child in parent_children_map.get(d.get("account")) or []]
			if children:
				for row in data:
					if row.get("account") in children and row.get("has_value"):
						data_with_value.append(d)
						break

	return data_with_value

def add_total_row(out, root_type, balance_must_be, period_list, company_currency):
	total_row = {
		"account_name": "'" + _("Total {0} ({1})").format(root_type, balance_must_be) + "'",
		#"account": "'" + _("Total {0} ({1})").format(root_type, balance_must_be) + "'",
		"account": None,
		"currency": company_currency
	}

	for row in out:
		if not row.get("parent_account"):
			for period in period_list:
				total_row.setdefault(period.key, 0.0)
				total_row[period.key] += row.get(period.key, 0.0)
				row[period.key] = ""

			total_row.setdefault("total", 0.0)
			total_row["total"] += flt(row["total"])
			row["total"] = ""

	if total_row.has_key("total"):
		out.append(total_row)

		# blank row after Total
		out.append({})

def get_accounts(company, root_type):
	return frappe.db.sql("""select is_group, name, account_code, parent_account, lft, rgt, root_type, report_type, account_name from `tabAccount`
		where company=%s and root_type=%s order by lft""", (company, root_type), as_dict=True)

def filter_accounts(accounts, depth=10):
	parent_children_map = {}
	accounts_by_name = {}
	for d in accounts:
		accounts_by_name[d.name] = d
		parent_children_map.setdefault(d.parent_account or None, []).append(d)

	filtered_accounts = []

	def add_to_list(parent, level):
		if level < depth:
			children = parent_children_map.get(parent) or []
			if parent == None:
				sort_root_accounts(children)

			for child in children:
				child.indent = level
				filtered_accounts.append(child)
				add_to_list(child.name, level + 1)

	add_to_list(None, 0)

	return filtered_accounts, accounts_by_name, parent_children_map

def sort_root_accounts(roots):
	"""Sort root types as Asset, Liability, Equity, Income, Expense"""

	def compare_roots(a, b):
		if a.report_type != b.report_type and a.report_type == "Balance Sheet":
			return -1
		if a.root_type != b.root_type and a.root_type == "Asset":
			return -1
		if a.root_type == "Liability" and b.root_type == "Equity":
			return -1
		if a.root_type == "Income" and b.root_type == "Expense":
			return -1
		return 1

	roots.sort(compare_roots)

def set_gl_entries_by_account(cost_center, company, from_date, to_date, root_lft, root_rgt, gl_entries_by_account,
		ignore_closing_entries=False, open_date=None):
	"""Returns a dict like { "account": [gl entries], ... }"""
	additional_conditions = []

	if ignore_closing_entries:
		additional_conditions.append(" and ifnull(voucher_type, '')!='Period Closing Voucher' ")

	#if from_date:
	#	additional_conditions.append("and posting_date >= %(from_date)s")

	if from_date and to_date:
		if open_date:
			#Getting openning balance
			additional_conditions.append(" and posting_date < \'" + str(open_date) + "\' and docstatus = 1 ")
		else:
			additional_conditions.append(" and posting_date BETWEEN %(from_date)s AND %(to_date)s and docstatus = 1 ")

	if not cost_center:
		gl_entries = frappe.db.sql("""select posting_date, account, debit, credit, is_opening from `tabGL Entry`
			where company=%(company)s
			{additional_conditions}
			and account in (select name from `tabAccount`
				where lft >= %(lft)s and rgt <= %(rgt)s)
			order by account, posting_date""".format(additional_conditions="\n".join(additional_conditions)),
			{
				"company": company,
				"from_date": from_date,
				"to_date": to_date,
				"lft": root_lft,
				"rgt": root_rgt
			},
			as_dict=True)
	else:
		cost_centers = get_child_cost_centers(cost_center);
		additional_conditions.append("and cost_center IN %(cost_center)s")
		gl_entries = frappe.db.sql("""select posting_date, account, debit, credit, is_opening from `tabGL Entry`
			where company=%(company)s
			{additional_conditions}
			and account in (select name from `tabAccount`
				where lft >= %(lft)s and rgt <= %(rgt)s)
			order by account, posting_date""".format(additional_conditions="\n".join(additional_conditions)),
			{
				"cost_center": cost_centers,
				"company": company,
				"from_date": from_date,
				"to_date": to_date,
				"lft": root_lft,
				"rgt": root_rgt
			},
			as_dict=True)

	for entry in gl_entries:
		gl_entries_by_account.setdefault(entry.account, []).append(entry)

	return gl_entries_by_account

def get_columns(periodicity, period_list, accumulated_values=1, company=None):
	columns = [{
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
		}]
	if company:
		columns.append({
			"fieldname": "currency",
			"label": _("Currency"),
			"fieldtype": "Link",
			"options": "Currency",
			"hidden": 1
		})
	for period in period_list:
		columns.append({
			"fieldname": period.key,
			"label": period.label,
			"fieldtype": "Currency",
			"options": "currency",
			"width": 150
		})
	if not accumulated_values:
		columns.append({
			"fieldname": "total",
			"label": _("Total"),
			"fieldtype": "Currency",
			"width": 150
		})

	return columns


def set_gl_entries_by_account1(cost_center, company, from_date, to_date, root_lft, root_rgt, gl_entries_by_account,
                ignore_closing_entries=False, open_date=None):
        """Returns a dict like { "account": [gl entries], ... }"""
        additional_conditions = []

        if ignore_closing_entries:
                additional_conditions.append(" and ifnull(voucher_type, '')!='Period Closing Voucher' ")

        #if from_date:
        #       additional_conditions.append("and posting_date >= %(from_date)s")

        if from_date and to_date:
                if open_date:
                        #Getting openning balance
                        additional_conditions.append(" and posting_date < \'" + str(open_date) + "\' and docstatus = 1 ")
                else:
                        additional_conditions.append(" and posting_date BETWEEN %(from_date)s AND %(to_date)s and docstatus = 1 ")

        if not cost_center:
                gl_entries = frappe.db.sql("""select posting_date, account, debit, credit, is_opening from `tabGL Entry`
                        where company=%(company)s
                        {additional_conditions}
                        and account in (select name from `tabAccount`
                                where lft >= %(lft)s and rgt <= %(rgt)s and account_type in ('Bank', 'Cash', 'Income Account', 'Expense Account'))
                        order by account, posting_date""".format(additional_conditions="\n".join(additional_conditions)),
                        {
                                "company": company,
                                "from_date": from_date,
                                "to_date": to_date,
                                "lft": root_lft,
                                "rgt": root_rgt
                        },
                        as_dict=True)

	else:
                cost_centers = get_child_cost_centers(cost_center);
                additional_conditions.append("and cost_center IN %(cost_center)s")
                gl_entries = frappe.db.sql("""select posting_date, account, debit, credit, is_opening from `tabGL Entry`
                        where company=%(company)s
                        {additional_conditions}
                        and account in (select name from `tabAccount`
                                where lft >= %(lft)s and rgt <= %(rgt)s and account_type in ('Bank', 'Cash', 'Income Account', 'Expense Account'))
                        order by account, posting_date""".format(additional_conditions="\n".join(additional_conditions)),
                        {
                                "cost_center": cost_centers,
                                "company": company,
                                "from_date": from_date,
                                "to_date": to_date,
                                "lft": root_lft,
                                "rgt": root_rgt
                        },
                        as_dict=True)

        for entry in gl_entries:
                gl_entries_by_account.setdefault(entry.account, []).append(entry)

        return gl_entries_by_account


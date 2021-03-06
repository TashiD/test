# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
'''
------------------------------------------------------------------------------------------------------------------------------------------
Version          Author         Ticket#           CreatedOn          ModifiedOn          Remarks
------------ --------------- --------------- ------------------ -------------------  -----------------------------------------------------
2.0.190509       SHIV		                                     2019/05/09         Refined process for making SL and GL entries
------------------------------------------------------------------------------------------------------------------------------------------                                                                          
'''

from __future__ import unicode_literals
import frappe
from frappe.utils import cint, flt, cstr
from frappe import msgprint, _
import frappe.defaults
from erpnext.accounts.utils import get_fiscal_year
from erpnext.accounts.general_ledger import make_gl_entries, delete_gl_entries, process_gl_map
from erpnext.controllers.accounts_controller import AccountsController
from erpnext.custom_utils import get_branch_cc

class StockController(AccountsController):
	def make_gl_entries(self, repost_future_gle=True):
		if self.docstatus == 2:
			delete_gl_entries(voucher_type=self.doctype, voucher_no=self.name)

		if cint(frappe.defaults.get_global_default("auto_accounting_for_stock")):
			warehouse_account = get_warehouse_account()

			if self.docstatus==1:
				gl_entries = self.get_gl_entries(warehouse_account)
				make_gl_entries(gl_entries)

			if repost_future_gle:
				items, warehouses = self.get_items_and_warehouses()
				update_gl_entries_after(self.posting_date, self.posting_time, warehouses, items,
					warehouse_account)

        """ ++++++++++ Ver 2.0.190509 Begins ++++++++++ """
        # Ver 2.0.190509, Following method added by SHIV on 2019/05/14
	def get_gl_entries(self, warehouse_account=None, default_expense_account=None,
			default_cost_center=None):

		if not warehouse_account:
			warehouse_account = get_warehouse_account()

		sle_map = self.get_stock_ledger_details()
		voucher_details = self.get_voucher_details(default_expense_account, default_cost_center, sle_map)

		gl_list = []
		warehouse_with_no_account = []
		for detail in voucher_details:
			sle_list = sle_map.get(detail.name)
                        if sle_list:
                                for sle in sle_list:
                                        if warehouse_account.get(sle.warehouse):
                                                self.check_expense_account(detail)
                                        
                                                to_cc = detail.cost_center
                                                if self.doctype == "Stock Entry" and self.purpose == "Material Transfer":
                                                        #to_branch = frappe.db.get_value("Stock Entry", detail.parent, "branch")
                                                        branchdtls = frappe.db.sql("select branch from `tabWarehouse Branch` where parent = '{0}' order by creation desc limit 1".format(detail.t_warehouse), as_dict=1)
                                                        for bra in branchdtls:
                                                                to_branch  = bra.branch
                                                        to_cc = get_branch_cc(to_branch)
                                                if self.doctype == "Stock Entry" and self.purpose == "Material Transfer" and sle.stock_value_difference > 0:
                                                        ic_account = frappe.db.get_single_value("Accounts Settings", "intra_company_account")
                                                        if not ic_account:
                                                                frappe.throw("Setup Intra-Company Account in Accounts Settings")

                                                        # from warehouse account
                                                        gl_list.append(self.get_gl_dict({
                                                                        "account": warehouse_account[sle.warehouse]["name"],
                                                                        "against": detail.expense_account,
                                                                        "cost_center": to_cc,
                                                                        "remarks": self.get("remarks") or "Accounting Entry for Stock",
                                                                        "debit": flt(sle.stock_value_difference, 2),
                                                        }, warehouse_account[sle.warehouse]["account_currency"]))

                                                        # to target warehouse / expense account
                                                        gl_list.append(self.get_gl_dict({
                                                                        "account": detail.expense_account,
                                                                        "against": warehouse_account[sle.warehouse]["name"],
                                                                        "cost_center": detail.cost_center,
                                                                        "remarks": self.get("remarks") or "Accounting Entry for Stock",
                                                                        "credit": flt(sle.stock_value_difference, 2),
                                                                        "project": detail.get("project") or self.get("project")
                                                        }))

                                                        gl_list.append(self.get_gl_dict({
                                                                        "account": ic_account,
                                                                        "cost_center": to_cc,
                                                                        "remarks": self.get("remarks") or "Accounting Entry for Stock",
                                                                        "credit": flt(sle.stock_value_difference, 2),
                                                        }))

                                                        gl_list.append(self.get_gl_dict({
                                                                        "account": ic_account,
                                                                        "cost_center": detail.cost_center,
                                                                        "remarks": self.get("remarks") or "Accounting Entry for Stock",
                                                                        "debit": flt(sle.stock_value_difference, 2),
                                                        }))
                                                else:
                                                        # from warehouse account
                                                        gl_list.append(self.get_gl_dict({
                                                                        "account": warehouse_account[sle.warehouse]["name"],
                                                                        "against": detail.expense_account,
                                                                        "cost_center": detail.cost_center,
                                                                        "remarks": self.get("remarks") or "Accounting Entry for Stock",
                                                                        "debit": flt(sle.stock_value_difference, 2),
                                                        }, warehouse_account[sle.warehouse]["account_currency"]))

                                                        # to target warehouse / expense account
                                                        gl_list.append(self.get_gl_dict({
                                                                        "account": detail.expense_account,
                                                                        "against": warehouse_account[sle.warehouse]["name"],
                                                                        "cost_center": detail.cost_center,
                                                                        "remarks": self.get("remarks") or "Accounting Entry for Stock",
                                                                        "credit": flt(sle.stock_value_difference, 2),
                                                                        "project": detail.get("project") or self.get("project")
                                                        }))
                                        elif sle.warehouse not in warehouse_with_no_account:
                                                warehouse_with_no_account.append(sle.warehouse)

		if warehouse_with_no_account:
			frappe.throw(_("No accounting entries for the following warehouses") + ": \n" +
				"\n".join(warehouse_with_no_account))

		return process_gl_map(gl_list)

        # Ver 2.0.190509, Following method commented by SHIV on 2019/05/14
        '''
	def get_gl_entries(self, warehouse_account=None, default_expense_account=None,
			default_cost_center=None):

		if not warehouse_account:
			warehouse_account = get_warehouse_account()

		sle_map = self.get_stock_ledger_details()
		voucher_details = self.get_voucher_details(default_expense_account, default_cost_center, sle_map)

		gl_list = []
		warehouse_with_no_account = []
		for detail in voucher_details:
			sle_list = sle_map.get(detail.name)
			if self.doctype in ["POL", "Issue POL"]:
				pass
			if sle_list and not self.doctype in ["POL", "Issue POL"]:
				for sle in sle_list:
					if warehouse_account.get(sle.warehouse):
						# from warehouse account

						self.check_expense_account(detail)
				
						to_cc = detail.cost_center
                                                if self.doctype == "Stock Entry" and self.purpose == "Material Transfer":
							#to_branch = frappe.db.get_value("Stock Entry", detail.parent, "branch")
							branchdtls = frappe.db.sql("select branch from `tabWarehouse Branch` where parent = '{0}' order by creation desc limit 1".format(detail.t_warehouse), as_dict=1)
							for bra in branchdtls:
								to_branch  = bra.branch
                                                        to_cc = get_branch_cc(to_branch)
                                                if self.doctype == "Stock Entry" and self.purpose == "Material Transfer" and sle.stock_value_difference > 0:
                                                        ic_account = frappe.db.get_single_value("Accounts Settings", "intra_company_account")
                                                        if not ic_account:
                                                                frappe.throw("Setup Intra-Company Account in Accounts Settings")

                                                        gl_list.append(self.get_gl_dict({
                                                                "account": warehouse_account[sle.warehouse]["name"],
                                                                "against": detail.expense_account,
                                                                "cost_center": to_cc,
                                                                "remarks": self.get("remarks") or "Accounting Entry for Stock",
                                                                "debit": flt(sle.stock_value_difference, 2),
                                                        }, warehouse_account[sle.warehouse]["account_currency"]))

                                                        # to target warehouse / expense account
                                                        gl_list.append(self.get_gl_dict({
                                                                "account": detail.expense_account,
                                                                "against": warehouse_account[sle.warehouse]["name"],
                                                                "cost_center": detail.cost_center,
                                                                "remarks": self.get("remarks") or "Accounting Entry for Stock",
                                                                "credit": flt(sle.stock_value_difference, 2),
                                                                "project": detail.get("project") or self.get("project")
                                                        }))

                                                        gl_list.append(self.get_gl_dict({
                                                                "account": ic_account,
                                                                "cost_center": to_cc,
                                                                "remarks": self.get("remarks") or "Accounting Entry for Stock",
                                                                "credit": flt(sle.stock_value_difference, 2),
                                                        }))

                                                        gl_list.append(self.get_gl_dict({
                                                                "account": ic_account,
                                                                "cost_center": detail.cost_center,
                                                                "remarks": self.get("remarks") or "Accounting Entry for Stock",
                                                                "debit": flt(sle.stock_value_difference, 2),
                                                        }))
						else:
							gl_list.append(self.get_gl_dict({
								"account": warehouse_account[sle.warehouse]["name"],
								"against": detail.expense_account,
								"cost_center": detail.cost_center,
								"remarks": self.get("remarks") or "Accounting Entry for Stock",
								"debit": flt(sle.stock_value_difference, 2),
							}, warehouse_account[sle.warehouse]["account_currency"]))

							# to target warehouse / expense account
							gl_list.append(self.get_gl_dict({
								"account": detail.expense_account,
								"against": warehouse_account[sle.warehouse]["name"],
								"cost_center": detail.cost_center,
								"remarks": self.get("remarks") or "Accounting Entry for Stock",
								"credit": flt(sle.stock_value_difference, 2),
								"project": detail.get("project") or self.get("project")
							}))
					elif sle.warehouse not in warehouse_with_no_account:
						warehouse_with_no_account.append(sle.warehouse)

		if warehouse_with_no_account:
			frappe.throw(_("No accounting entries for the following warehouses") + ": \n" +
				"\n".join(warehouse_with_no_account))

		return process_gl_map(gl_list)
        '''

        # Ver 2.0.190509, Following method added by SHIV on 2019/05/14
        def get_voucher_details(self, default_expense_account, default_cost_center, sle_map):
                details = []
                
		if self.doctype == "Stock Reconciliation":
			return [frappe._dict({ "name": voucher_detail_no, "expense_account": default_expense_account,
				"cost_center": default_cost_center }) for voucher_detail_no, sle in sle_map.items()]
		else:
			details = self.get("items")
			if details:
                                if default_expense_account or default_cost_center:
                                        for d in details:
                                                if default_expense_account and not d.get("expense_account"):
                                                        d.expense_account = default_expense_account
                                                if default_cost_center and not d.get("cost_center"):
                                                        d.cost_center = default_cost_center
                        else:
                                details.append(self)
                                
			return details

        # Ver 2.0.190509, Following method commented by SHIV on 2019/05/14
	'''	
	def get_voucher_details(self, default_expense_account, default_cost_center, sle_map):
		if self.doctype == "Stock Reconciliation":
			return [frappe._dict({ "name": voucher_detail_no, "expense_account": default_expense_account,
				"cost_center": default_cost_center }) for voucher_detail_no, sle in sle_map.items()]
		elif self.doctype in ["Issue POL", "POL"]:
                        gl_map_pol = []
                        for voucher_detail_no, sle in sle_map.items():
                                gl_map_pol.append(frappe._dict({ "name": voucher_detail_no, "expense_account": "", "cost_center": "" }))
                        return gl_map_pol
		else:
			details = self.get("items")
			if default_expense_account or default_cost_center:
				for d in details:
					if default_expense_account and not d.get("expense_account"):
						d.expense_account = default_expense_account
					if default_cost_center and not d.get("cost_center"):
						d.cost_center = default_cost_center
			return details
	'''
	""" ++++++++++ Ver 2.0.190509 Ends ++++++++++++ """

	def get_items_and_warehouses(self):
		items, warehouses = [], []

                """ ++++++++++ Ver 2.0.190509 Begins ++++++++++ """
                # Ver 2.0.190509, following code added by SHIV on 2019/05/21
                item_doclist = []
                """ ++++++++++ Ver 2.0.190509 Ends ++++++++++++ """
                
		if hasattr(self, "items"):
			item_doclist = self.get("items")
		elif self.doctype == "POL":
                        if self.hiring_warehouse:
                                wh = self.hiring_warehouse
                        else:
                                wh = self.equipment_warehouse

                        items.append(self.pol_type)
                        warehouses.append(wh)
		elif self.doctype == "Stock Reconciliation":
			import json
			item_doclist = []
			data = json.loads(self.reconciliation_json)
			for row in data[data.index(self.head_row)+1:]:
				d = frappe._dict(zip(["item_code", "warehouse", "qty", "valuation_rate"], row))
				item_doclist.append(d)

		if item_doclist:
			for d in item_doclist:
				if d.item_code and d.item_code not in items:
					items.append(d.item_code)

				if d.get("warehouse") and d.warehouse not in warehouses:
					warehouses.append(d.warehouse)

				if self.doctype == "Stock Entry":
					if d.get("s_warehouse") and d.s_warehouse not in warehouses:
						warehouses.append(d.s_warehouse)
					if d.get("t_warehouse") and d.t_warehouse not in warehouses:
						warehouses.append(d.t_warehouse)

		return items, warehouses

	def get_stock_ledger_details(self):
		stock_ledger = {}
		for sle in frappe.db.sql("""select warehouse, stock_value_difference,
			voucher_detail_no, item_code, posting_date, actual_qty
			from `tabStock Ledger Entry` where voucher_type=%s and voucher_no=%s""",
			(self.doctype, self.name), as_dict=True):
				stock_ledger.setdefault(sle.voucher_detail_no, []).append(sle)
		return stock_ledger

	def make_adjustment_entry(self, expected_gle, voucher_obj):
		from erpnext.accounts.utils import get_stock_and_account_difference
		account_list = [d.account for d in expected_gle]
		acc_diff = get_stock_and_account_difference(account_list, expected_gle[0].posting_date)

		cost_center = self.get_company_default("cost_center")
		stock_adjustment_account = self.get_company_default("stock_adjustment_account")

		gl_entries = []
		for account, diff in acc_diff.items():
			if diff:
				gl_entries.append([
					# stock in hand account
					voucher_obj.get_gl_dict({
						"account": account,
						"against": stock_adjustment_account,
						"debit": diff,
						"remarks": "Adjustment Accounting Entry for Stock",
					}),

					# account against stock in hand
					voucher_obj.get_gl_dict({
						"account": stock_adjustment_account,
						"against": account,
						"credit": diff,
						"cost_center": cost_center or None,
						"remarks": "Adjustment Accounting Entry for Stock",
					}),
				])

		if gl_entries:
			from erpnext.accounts.general_ledger import make_gl_entries
			make_gl_entries(gl_entries)

	def check_expense_account(self, item):
                """ ++++++++++ Ver 2.0.190509 Begins ++++++++++ """
		#if self.doctype in ["POL", "Issue POL"]:
		#	return

		if self.doctype in ["POL"]:
			return
		""" ++++++++++ Ver 2.0.190509 Ends ++++++++++++ """

		if not item.get("expense_account"):
			frappe.throw(_("Expense or Difference account is mandatory for Item {0} as it impacts overall stock value").format(item.item_code))

		else:
			is_expense_account = frappe.db.get_value("Account",
				item.get("expense_account"), "report_type")=="Profit and Loss"
			if self.doctype not in ("Purchase Receipt", "Purchase Invoice", "Stock Reconciliation", "Stock Entry") and not is_expense_account:
				frappe.throw(_("Expense / Difference account ({0}) must be a 'Profit or Loss' account")
					.format(item.get("expense_account")))
			if is_expense_account and not item.get("cost_center"):
				frappe.throw(_("{0} {1}: Cost Center is mandatory for Item {2}").format(
					_(self.doctype), self.name, item.get("item_code")))

	def get_sl_entries(self, d, args):
		sl_dict = frappe._dict({
			"item_code": d.get("item_code", None),
			"warehouse": d.get("warehouse", None),
			"posting_date": self.posting_date,
			"posting_time": self.posting_time,
			'fiscal_year': get_fiscal_year(self.posting_date, company=self.company)[0],
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"voucher_detail_no": d.name,
			"actual_qty": (self.docstatus==1 and 1 or -1)*flt(d.get("stock_qty")),
			"stock_uom": frappe.db.get_value("Item", args.get("item_code") or d.get("item_code"), "stock_uom"),
			"incoming_rate": 0,
			"company": self.company,
			"batch_no": cstr(d.get("batch_no")).strip(),
			"serial_no": d.get("serial_no"),
			"project": d.get("project"),
			"is_cancelled": self.docstatus==2 and "Yes" or "No"
		})

		sl_dict.update(args)
		return sl_dict

	def make_sl_entries(self, sl_entries, is_amended=None, allow_negative_stock=False,
			via_landed_cost_voucher=False):
		from erpnext.stock.stock_ledger import make_sl_entries
		make_sl_entries(sl_entries, is_amended, allow_negative_stock, via_landed_cost_voucher)

	def make_gl_entries_on_cancel(self, repost_future_gle=True):
		if frappe.db.sql("""select name from `tabGL Entry` where voucher_type=%s
			and voucher_no=%s""", (self.doctype, self.name)):
				self.make_gl_entries(repost_future_gle)

	def get_serialized_items(self):
		serialized_items = []
		item_codes = list(set([d.item_code for d in self.get("items")]))
		if item_codes:
			serialized_items = frappe.db.sql_list("""select name from `tabItem`
				where has_serial_no=1 and name in ({})""".format(", ".join(["%s"]*len(item_codes))),
				tuple(item_codes))

		return serialized_items

	def get_incoming_rate_for_sales_return(self, item_code, against_document):
		incoming_rate = 0.0
		if against_document and item_code:
			incoming_rate = frappe.db.sql("""select abs(stock_value_difference / actual_qty)
				from `tabStock Ledger Entry`
				where voucher_type = %s and voucher_no = %s
					and item_code = %s limit 1""",
				(self.doctype, against_document, item_code))
			incoming_rate = incoming_rate[0][0] if incoming_rate else 0.0

		return incoming_rate
		
	def validate_warehouse(self):
		from erpnext.stock.utils import validate_warehouse_company

		warehouses = list(set([d.warehouse for d in
			self.get("items") if getattr(d, "warehouse", None)]))

		for w in warehouses:
			validate_warehouse_company(w, self.company)
	
	def validate_warehouse_branch(self, warehouse, branch):
                if not branch:
                        frappe.throw("Branch is Mandatory")
                if not warehouse:
                        frappe.throw("Warehouse is Mandatory")
                branches = frappe.db.sql("select parent from `tabWarehouse Branch` where branch = %s", branch, as_dict=1)
                for a in branches:
                        if a.parent == warehouse:
                                return
                frappe.throw("Warehouse <b>" + str(warehouse) + "</b> doesn't belong to <b>" + str(branch) + "</b>")
		
	
	def update_billing_percentage(self, update_modified=True):
		self._update_percent_field({
			"target_dt": self.doctype + " Item",
			"target_parent_dt": self.doctype,
			"target_parent_field": "per_billed",
			"target_ref_field": "amount",
			"target_field": "billed_amt",
			"name": self.name,
		}, update_modified)

def update_gl_entries_after(posting_date, posting_time, for_warehouses=None, for_items=None,
		warehouse_account=None):
	def _delete_gl_entries(voucher_type, voucher_no):
                """ ++++++++++ Ver 2.0.190509 Begins ++++++++++ """
                # Ver 2.0.190509, following code commented by SHIV on 2019/05/21
		#if voucher_type in ["POL", "Issue POL"]:
                #        return
                """ ++++++++++ Ver 2.0.190509 Ends ++++++++++++ """
                
		frappe.db.sql("""delete from `tabGL Entry`
			where voucher_type=%s and voucher_no=%s""", (voucher_type, voucher_no))

	if not warehouse_account:
		warehouse_account = get_warehouse_account()

	future_stock_vouchers = get_future_stock_vouchers(posting_date, posting_time, for_warehouses, for_items)
	gle = get_voucherwise_gl_entries(future_stock_vouchers, posting_date)
	
	for voucher_type, voucher_no in future_stock_vouchers:
		existing_gle = gle.get((voucher_type, voucher_no), [])
		voucher_obj = frappe.get_doc(voucher_type, voucher_no)
		expected_gle = voucher_obj.get_gl_entries(warehouse_account)
		if expected_gle:
			if not existing_gle or not compare_existing_and_expected_gle(existing_gle, expected_gle):
				_delete_gl_entries(voucher_type, voucher_no)
				voucher_obj.make_gl_entries(repost_future_gle=False)
		else:
			_delete_gl_entries(voucher_type, voucher_no)

def compare_existing_and_expected_gle(existing_gle, expected_gle):
	matched = True
	for entry in expected_gle:
		for e in existing_gle:
			if entry.account==e.account and entry.against_account==e.against_account \
				and (not entry.cost_center or not e.cost_center or entry.cost_center==e.cost_center) \
				and (entry.debit != e.debit or entry.credit != e.credit):
					matched = False
					break
	return matched

def get_future_stock_vouchers(posting_date, posting_time, for_warehouses=None, for_items=None):
	future_stock_vouchers = []

	values = []
	condition = ""
	if for_items:
		condition += " and item_code in ({})".format(", ".join(["%s"] * len(for_items)))
		values += for_items

	if for_warehouses:
		condition += " and warehouse in ({})".format(", ".join(["%s"] * len(for_warehouses)))
		values += for_warehouses

	for d in frappe.db.sql("""select distinct sle.voucher_type, sle.voucher_no
		from `tabStock Ledger Entry` sle
		where timestamp(sle.posting_date, sle.posting_time) >= timestamp(%s, %s) {condition}
		order by timestamp(sle.posting_date, sle.posting_time) asc, name asc""".format(condition=condition),
		tuple([posting_date, posting_time] + values), as_dict=True):
			future_stock_vouchers.append([d.voucher_type, d.voucher_no])

	return future_stock_vouchers

def get_voucherwise_gl_entries(future_stock_vouchers, posting_date):
	gl_entries = {}
	if future_stock_vouchers:
		for d in frappe.db.sql("""select * from `tabGL Entry`
			where posting_date >= %s and voucher_no in (%s)""" %
			('%s', ', '.join(['%s']*len(future_stock_vouchers))),
			tuple([posting_date] + [d[1] for d in future_stock_vouchers]), as_dict=1):
				gl_entries.setdefault((d.voucher_type, d.voucher_no), []).append(d)

	return gl_entries

def get_warehouse_account():
	warehouse_account = frappe._dict()

	for d in frappe.db.sql("""select warehouse, name, account_currency from tabAccount
		where account_type = 'Stock' and (warehouse is not null and warehouse != ''
		and is_group != 1) and is_group=0 """, as_dict=1):
			warehouse_account.setdefault(d.warehouse, d)
	return warehouse_account

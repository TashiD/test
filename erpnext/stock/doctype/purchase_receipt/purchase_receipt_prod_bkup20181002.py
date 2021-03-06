# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.utils import flt, cint

from frappe import _
import frappe.defaults

from erpnext.controllers.buying_controller import BuyingController
from erpnext.accounts.utils import get_account_currency
from frappe.desk.notifications import clear_doctype_notifications
from frappe.model.naming import make_autoname
from erpnext.custom_autoname import get_auto_name
from erpnext.custom_utils import check_uncancelled_linked_doc, check_future_date

form_grid_templates = {
	"items": "templates/form_grid/item_grid.html"
}

class PurchaseReceipt(BuyingController):
	def __init__(self, arg1, arg2=None):
		super(PurchaseReceipt, self).__init__(arg1, arg2)
		self.status_updater = [{
			'source_dt': 'Purchase Receipt Item',
			'target_dt': 'Purchase Order Item',
			'join_field': 'purchase_order_item',
			'target_field': 'received_qty',
			'target_parent_dt': 'Purchase Order',
			'target_parent_field': 'per_received',
			'target_ref_field': 'qty',
			'source_field': 'qty',
			'percent_join_field': 'purchase_order',
			'overflow_type': 'receipt'
		},
		{
			'source_dt': 'Purchase Receipt Item',
			'target_dt': 'Purchase Order Item',
			'join_field': 'purchase_order_item',
			'target_field': 'returned_qty',
			'target_parent_dt': 'Purchase Order',
			# 'target_parent_field': 'per_received',
			# 'target_ref_field': 'qty',
			'source_field': '-1 * qty',
			# 'overflow_type': 'receipt',
			'extra_cond': """ and exists (select name from `tabPurchase Receipt` where name=`tabPurchase Receipt Item`.parent and is_return=1)"""
		}]

	def autoname(self):
		self.name = make_autoname(get_auto_name(self, self.naming_series) + ".####")

	def validate(self):
		check_future_date(self.posting_date)
		super(PurchaseReceipt, self).validate()
		self.set_status()
		self.po_required()
		self.validate_with_previous_doc()
		self.validate_inspection()
		self.validate_uom_is_integer("uom", ["qty", "received_qty"])
		self.validate_uom_is_integer("stock_uom", "stock_qty")

		pc_obj = frappe.get_doc('Purchase Common')
		self.check_for_closed_status(pc_obj)

	def validate_with_previous_doc(self):
		super(PurchaseReceipt, self).validate_with_previous_doc({
			"Purchase Order": {
				"ref_dn_field": "purchase_order",
				"compare_fields": [["supplier", "="], ["company", "="],	["currency", "="]],
			},
			"Purchase Order Item": {
				"ref_dn_field": "purchase_order_item",
				"compare_fields": [["project", "="], ["uom", "="], ["item_code", "="]],
				"is_child_table": True
			}
		})

		if cint(frappe.db.get_single_value('Buying Settings', 'maintain_same_rate')) and not self.is_return:
			self.validate_rate_with_reference_doc([["Purchase Order", "purchase_order", "purchase_order_item"]])

	def po_required(self):
		if frappe.db.get_value("Buying Settings", None, "po_required") == 'Yes':
			 for d in self.get('items'):
				 if not d.purchase_order:
					 frappe.throw(_("Purchase Order number required for Item {0}").format(d.item_code))

	def get_already_received_qty(self, po, po_detail):
		qty = frappe.db.sql("""select sum(qty) from `tabPurchase Receipt Item`
			where purchase_order_item = %s and docstatus = 1
			and purchase_order=%s
			and parent != %s""", (po_detail, po, self.name))
		return qty and flt(qty[0][0]) or 0.0

	def get_po_qty_and_warehouse(self, po_detail):
		po_qty, po_warehouse = frappe.db.get_value("Purchase Order Item", po_detail,
			["qty", "warehouse"])
		return po_qty, po_warehouse

	def validate_inspection(self):
		for d in self.get('items'):		 #Enter inspection date for all items that require inspection
			if frappe.db.get_value("Item", d.item_code, "inspection_required") and not d.qa_no:
				frappe.msgprint(_("Quality Inspection required for Item {0}").format(d.item_code))
				if self.docstatus==1:
					raise frappe.ValidationError

	# Check for Closed status
	def check_for_closed_status(self, pc_obj):
		check_list =[]
		for d in self.get('items'):
			if d.meta.get_field('purchase_order') and d.purchase_order and d.purchase_order not in check_list:
				check_list.append(d.purchase_order)
				pc_obj.check_for_closed_status('Purchase Order', d.purchase_order)

	# on submit
	def on_submit(self):
		purchase_controller = frappe.get_doc("Purchase Common")

		# Check for Approving Authority
		frappe.get_doc('Authorization Control').validate_approving_authority(self.doctype,
			self.company, self.base_grand_total)

		# Set status as Submitted
		frappe.db.set(self, 'status', 'Submitted')

		self.update_prevdoc_status()
		self.update_billing_status()

		if not self.is_return:
			purchase_controller.update_last_purchase_rate(self, 1)

		# Updating stock ledger should always be called after updating prevdoc status,
		# because updating ordered qty in bin depends upon updated ordered qty in PO
		self.update_stock_ledger()

		from erpnext.stock.doctype.serial_no.serial_no import update_serial_nos_after_submit
		update_serial_nos_after_submit(self, "items")

		self.make_gl_entries()
		#self.consume_budget()
		self.update_asset()

	def check_next_docstatus(self):
		submit_rv = frappe.db.sql("""select t1.name
			from `tabPurchase Invoice` t1,`tabPurchase Invoice Item` t2
			where t1.name = t2.parent and t2.purchase_receipt = %s and t1.docstatus = 1""",
			(self.name))
		if submit_rv:
			frappe.throw(_("Purchase Invoice {0} is already submitted").format(self.submit_rv[0][0]))

	def on_cancel(self):
		check_uncancelled_linked_doc(self.doctype, self.name)
		pc_obj = frappe.get_doc('Purchase Common')

		self.check_for_closed_status(pc_obj)
		# Check if Purchase Invoice has been submitted against current Purchase Order
		submitted = frappe.db.sql("""select t1.name
			from `tabPurchase Invoice` t1,`tabPurchase Invoice Item` t2
			where t1.name = t2.parent and t2.purchase_receipt = %s and t1.docstatus = 1""",
			self.name)
		if submitted:
			frappe.throw(_("Purchase Invoice {0} is already submitted").format(submitted[0][0]))

		frappe.db.set(self,'status','Cancelled')

		self.update_prevdoc_status()
		self.update_billing_status()

		if not self.is_return:
			pc_obj.update_last_purchase_rate(self, 0)

		# Updating stock ledger should always be called after updating prevdoc status,
		# because updating ordered qty in bin depends upon updated ordered qty in PO
		self.update_stock_ledger()
		self.make_gl_entries_on_cancel()
		self.delete_asset()

	##
	# Update sonsumed budget with the amount
	##
	def consume_budget(self):
		for a in self.items:
			idx = frappe.db.sql("select name from `tabCommitted Budget` where cost_center = %s and po_no = %s and item_code = %s", (a.cost_center, a.purchase_order, a.item_code), as_dict=True)
			if idx:
				ref_doc = frappe.get_doc("Committed Budget", idx[0].name)
				if a.base_net_amount:
					amount = a.base_net_amount
				else:
					amount = a.base_amount
				ref_doc.db_set("amount", amount)

	##
	# Update asset entries if asset
	##
	def update_asset(self):
		for a in self.items:
			item_group = frappe.db.get_value("Item", a.item_code, "item_group")
			if item_group and item_group == "Fixed Asset":
				ae = frappe.new_doc("Asset Received Entries")
				ae.item_code = a.item_code
				ae.item_name = a.item_name
				ae.qty = a.qty
				ae.received_date = self.posting_date
				ae.ref_doc = self.name
				ae.branch = frappe.db.get_value("Cost Center", a.cost_center, "branch")
				ae.submit()

	##
	#  Delete asset entries
	##
	def delete_asset(self):
		frappe.db.sql("delete from `tabAsset Received Entries` where ref_doc = %s", self.name)


	def get_current_stock(self):
		for d in self.get('supplied_items'):
			if self.supplier_warehouse:
				bin = frappe.db.sql("select actual_qty from `tabBin` where item_code = %s and warehouse = %s", (d.rm_item_code, self.supplier_warehouse), as_dict = 1)
				d.current_stock = bin and flt(bin[0]['actual_qty']) or 0

	def get_rate(self,arg):
		return frappe.get_doc('Purchase Common').get_rate(arg,self)

	def get_gl_entries(self, warehouse_account=None):
		from erpnext.accounts.general_ledger import process_gl_map

		stock_rbnb = self.get_company_default("stock_received_but_not_billed")
		expenses_included_in_valuation = self.get_company_default("expenses_included_in_valuation")

		gl_entries = []
		warehouse_with_no_account = []
		negative_expense_to_be_booked = 0.0
		stock_items = self.get_stock_items()
		for d in self.get("items"):
			if d.item_code in stock_items and flt(d.valuation_rate) and flt(d.qty):
				if warehouse_account.get(d.warehouse):
					stock_value_diff = frappe.db.get_value("Stock Ledger Entry",
						{"voucher_type": "Purchase Receipt", "voucher_no": self.name,
						"voucher_detail_no": d.name}, "stock_value_difference")
					if not stock_value_diff:
						continue
					gl_entries.append(self.get_gl_dict({
						"account": warehouse_account[d.warehouse]["name"],
						"against": stock_rbnb,
						"cost_center": d.cost_center,
						"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
						"debit": stock_value_diff
					}, warehouse_account[d.warehouse]["account_currency"]))

					# stock received but not billed
					stock_rbnb_currency = get_account_currency(stock_rbnb)
					gl_entries.append(self.get_gl_dict({
						"account": stock_rbnb,
						"against": warehouse_account[d.warehouse]["name"],
						"cost_center": d.cost_center,
						"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
						"credit": flt(d.base_net_amount, d.precision("base_net_amount")),
						"credit_in_account_currency": flt(d.base_net_amount, d.precision("base_net_amount")) \
							if stock_rbnb_currency==self.company_currency else flt(d.net_amount, d.precision("net_amount"))
					}, stock_rbnb_currency))

					negative_expense_to_be_booked += flt(d.item_tax_amount)

					# Amount added through landed-cost-voucher
					if flt(d.landed_cost_voucher_amount):
						gl_entries.append(self.get_gl_dict({
							"account": expenses_included_in_valuation,
							"against": warehouse_account[d.warehouse]["name"],
							"cost_center": d.cost_center,
							"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
							"credit": flt(d.landed_cost_voucher_amount),
							"project": d.project
						}))

					# sub-contracting warehouse
					if flt(d.rm_supp_cost) and warehouse_account.get(self.supplier_warehouse):
						gl_entries.append(self.get_gl_dict({
							"account": warehouse_account[self.supplier_warehouse]["name"],
							"against": warehouse_account[d.warehouse]["name"],
							"cost_center": d.cost_center,
							"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
							"credit": flt(d.rm_supp_cost)
						}, warehouse_account[self.supplier_warehouse]["account_currency"]))

					# divisional loss adjustment
					valuation_amount_as_per_doc = flt(d.base_net_amount, d.precision("base_net_amount")) + \
						flt(d.landed_cost_voucher_amount) + flt(d.rm_supp_cost) + flt(d.item_tax_amount)

					divisional_loss = flt(valuation_amount_as_per_doc - stock_value_diff,
						d.precision("base_net_amount"))

					if divisional_loss:
						if self.is_return or flt(d.item_tax_amount):
							loss_account = expenses_included_in_valuation
						else:
							loss_account = stock_rbnb

						gl_entries.append(self.get_gl_dict({
							"account": loss_account,
							"against": warehouse_account[d.warehouse]["name"],
							"cost_center": d.cost_center,
							"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
							"debit": divisional_loss,
							"project": d.project
						}, stock_rbnb_currency))

				elif d.warehouse not in warehouse_with_no_account or \
					d.rejected_warehouse not in warehouse_with_no_account:
						warehouse_with_no_account.append(d.warehouse)

		# Cost center-wise amount breakup for other charges included for valuation
		valuation_tax = {}
		for tax in self.get("taxes"):
			if tax.category in ("Valuation", "Valuation and Total") and flt(tax.base_tax_amount_after_discount_amount):
				if not tax.cost_center:
					frappe.throw(_("Cost Center is required in row {0} in Taxes table for type {1}").format(tax.idx, _(tax.category)))
				valuation_tax.setdefault(tax.cost_center, 0)
				valuation_tax[tax.cost_center] += \
					(tax.add_deduct_tax == "Add" and 1 or -1) * flt(tax.base_tax_amount_after_discount_amount)

		if negative_expense_to_be_booked and valuation_tax:
			# Backward compatibility:
			# If expenses_included_in_valuation account has been credited in against PI
			# and charges added via Landed Cost Voucher,
			# post valuation related charges on "Stock Received But Not Billed"

			negative_expense_booked_in_pi = frappe.db.sql("""select name from `tabPurchase Invoice Item` pi
				where docstatus = 1 and purchase_receipt=%s
				and exists(select name from `tabGL Entry` where voucher_type='Purchase Invoice'
					and voucher_no=pi.parent and account=%s)""", (self.name, expenses_included_in_valuation))

			if negative_expense_booked_in_pi:
				expenses_included_in_valuation = stock_rbnb

			against_account = ", ".join([d.account for d in gl_entries if flt(d.debit) > 0])
			total_valuation_amount = sum(valuation_tax.values())
			amount_including_divisional_loss = negative_expense_to_be_booked
			i = 1
			for cost_center, amount in valuation_tax.items():
				if i == len(valuation_tax):
					applicable_amount = amount_including_divisional_loss
				else:
					applicable_amount = negative_expense_to_be_booked * (amount / total_valuation_amount)
					amount_including_divisional_loss -= applicable_amount

				gl_entries.append(
					self.get_gl_dict({
						"account": expenses_included_in_valuation,
						"cost_center": cost_center,
						"credit": applicable_amount,
						"remarks": self.remarks or _("Accounting Entry for Stock"),
						"against": against_account
					})
				)

				i += 1

		if warehouse_with_no_account:
			frappe.msgprint(_("No accounting entries for the following warehouses") + ": \n" +
				"\n".join(warehouse_with_no_account))

		return process_gl_map(gl_entries)

	def update_status(self, status):
		self.set_status(update=True, status = status)
		self.notify_update()
		clear_doctype_notifications(self)

	def update_billing_status(self, update_modified=True):
		updated_pr = [self.name]
		for d in self.get("items"):
			if d.purchase_order_item:
				updated_pr += update_billed_amount_based_on_po(d.purchase_order_item, update_modified)

		for pr in set(updated_pr):
			pr_doc = self if (pr == self.name) else frappe.get_doc("Purchase Receipt", pr)
			pr_doc.update_billing_percentage(update_modified=update_modified)

		self.load_from_db()

def update_billed_amount_based_on_po(po_detail, update_modified=True):
	# Billed against Sales Order directly
	billed_against_po = frappe.db.sql("""select sum(amount) from `tabPurchase Invoice Item`
		where po_detail=%s and (pr_detail is null or pr_detail = '') and docstatus=1""", po_detail)
	billed_against_po = billed_against_po and billed_against_po[0][0] or 0

	# Get all Delivery Note Item rows against the Sales Order Item row
	pr_details = frappe.db.sql("""select pr_item.name, pr_item.amount, pr_item.parent
		from `tabPurchase Receipt Item` pr_item, `tabPurchase Receipt` pr
		where pr.name=pr_item.parent and pr_item.purchase_order_item=%s
			and pr.docstatus=1 and pr.is_return = 0
		order by pr.posting_date asc, pr.posting_time asc, pr.name asc""", po_detail, as_dict=1)

	updated_pr = []
	for pr_item in pr_details:
		# Get billed amount directly against Purchase Receipt
		billed_amt_agianst_pr = frappe.db.sql("""select sum(amount) from `tabPurchase Invoice Item`
			where pr_detail=%s and docstatus=1""", pr_item.name)
		billed_amt_agianst_pr = billed_amt_agianst_pr and billed_amt_agianst_pr[0][0] or 0

		# Distribute billed amount directly against PO between PRs based on FIFO
		if billed_against_po and billed_amt_agianst_pr < pr_item.amount:
			pending_to_bill = flt(pr_item.amount) - billed_amt_agianst_pr
			if pending_to_bill <= billed_against_po:
				billed_amt_agianst_pr += pending_to_bill
				billed_against_po -= pending_to_bill
			else:
				billed_amt_agianst_pr += billed_against_po
				billed_against_po = 0

		frappe.db.set_value("Purchase Receipt Item", pr_item.name, "billed_amt", billed_amt_agianst_pr, update_modified=update_modified)

		updated_pr.append(pr_item.parent)

	return updated_pr

@frappe.whitelist()
def make_purchase_invoice(source_name, target_doc=None):
	from frappe.model.mapper import get_mapped_doc
	invoiced_qty_map = get_invoiced_qty_map(source_name)

	def set_missing_values(source, target):
		if len(target.get("items")) == 0:
			frappe.throw(_("All items have already been invoiced"))

		doc = frappe.get_doc(target)
		doc.ignore_pricing_rule = 1
		doc.run_method("set_missing_values")
		doc.run_method("calculate_taxes_and_totals")

	def update_item(source_doc, target_doc, source_parent):
		target_doc.qty = source_doc.qty - invoiced_qty_map.get(source_doc.name, 0)
		cat = frappe.db.get_value("Item", source_doc.item_code, "item_group")
		if cat == 'Fixed Asset':
			expense_account = source_parent.get_company_default("stock_asset_received_but_not_billed")
			if not expense_account:
				frappe.throw("Setup Stock Asset Received But Not Billed in Company Setting")
			target_doc.expense_account = expense_account

	doclist = get_mapped_doc("Purchase Receipt", source_name,	{
		"Purchase Receipt": {
			"doctype": "Purchase Invoice",
			"field_map": {
				"naming_series": "naming_series",
			},
			"validation": {
				"docstatus": ["=", 1],
			},
		},
		"Purchase Receipt Item": {
			"doctype": "Purchase Invoice Item",
			"field_map": {
				"name": "pr_detail",
				"parent": "purchase_receipt",
				"purchase_order_item": "po_detail",
				"purchase_order": "purchase_order",
			},
			"postprocess": update_item,
			"filter": lambda d: abs(d.qty) - abs(invoiced_qty_map.get(d.name, 0))<=0
		},
		"Purchase Taxes and Charges": {
			"doctype": "Purchase Taxes and Charges",
			"add_if_empty": True
		}
	}, target_doc, set_missing_values)
	
	return doclist

def get_invoiced_qty_map(purchase_receipt):
	"""returns a map: {pr_detail: invoiced_qty}"""
	invoiced_qty_map = {}

	for pr_detail, qty in frappe.db.sql("""select pr_detail, qty from `tabPurchase Invoice Item`
		where purchase_receipt=%s and docstatus=1""", purchase_receipt):
			if not invoiced_qty_map.get(pr_detail):
				invoiced_qty_map[pr_detail] = 0
			invoiced_qty_map[pr_detail] += qty

	return invoiced_qty_map

@frappe.whitelist()
def make_purchase_return(source_name, target_doc=None):
	from erpnext.controllers.sales_and_purchase_return import make_return_doc
	return make_return_doc("Purchase Receipt", source_name, target_doc)


@frappe.whitelist()
def update_purchase_receipt_status(docname, status):
	pr = frappe.get_doc("Purchase Receipt", docname)
	pr.update_status(status)

@frappe.whitelist()
def get_item_group(item_code=None):
	grp = ""
	if item_code:
		grp = frappe.db.get_value("Item", item_code, "item_group")

	return grp

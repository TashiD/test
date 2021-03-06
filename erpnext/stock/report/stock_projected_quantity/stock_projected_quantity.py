# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, today

def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)

def get_columns():
	return [_("Material Code") + ":Link/Item:100", _("Material Name") + "::140", 
		_("Material Group") + ":Link/Item Group:100", _("Material Sub Group") + ":Link/Item Sub Group:100",_("Warehouse") + ":Link/Warehouse:140",
		_("UOM") + ":Link/UOM:100", _("Actual Qty") + ":Float:100", 
		_("Requested Qty") + ":Float:110", _("Ordered Qty") + ":Float:100", 
		_("Reserved Qty") + ":Float:100", _("Projected Qty") + ":Float:100", 
		_("Shortage Qty") + ":Float:100"]

def get_data(filters):
	bin_list = get_bin_list(filters)
	item_map = get_item_map(filters.get("item_code"))
	warehouse_company = {}
	data = []

	for bin in bin_list:
		item = item_map.get(bin.item_code)

		if not item:
			# likely an item that has reached its end of life
			continue

		# item = item_map.setdefault(bin.item_code, get_item(bin.item_code))
		company = warehouse_company.setdefault(bin.warehouse, frappe.db.get_value("Warehouse", bin.warehouse, "company"))

		if filters.brand and filters.brand != item.brand:
			continue

		elif filters.company and filters.company != company:
			continue

		re_order_level = re_order_qty = 0

		for d in item.get("reorder_levels"):
			if d.warehouse == bin.warehouse:
				re_order_level = d.warehouse_reorder_level
				re_order_qty = d.warehouse_reorder_qty

		shortage_qty = re_order_level - flt(bin.projected_qty) if (re_order_level or re_order_qty) else 0

		data.append([item.name, item.item_name, item.item_group, item.item_sub_group, bin.warehouse,
			item.stock_uom, bin.actual_qty, bin.indented_qty, bin.ordered_qty,
			bin.reserved_qty, bin.projected_qty, shortage_qty])

	return data

def get_bin_list(filters):
	bin_filters = frappe._dict()
	if filters.item_code:
		bin_filters.item_code = filters.item_code
	if filters.warehouse:
		bin_filters.warehouse = filters.warehouse

	bin_list = frappe.get_all("Bin", fields=["item_code", "warehouse",
		"actual_qty", "planned_qty", "indented_qty", "ordered_qty", "reserved_qty", "projected_qty"],
		filters=bin_filters, order_by="item_code, warehouse")

	return bin_list

def get_item_map(item_code):
	"""Optimization: get only the item doc and re_order_levels table"""

	condition = ""
	if item_code:
		condition = 'and item_code = "{0}"'.format(frappe.db.escape(item_code, percent=False))

	items = frappe.db.sql("""select * from `tabItem` item
		where is_stock_item = 1
		and disabled=0
		{condition}
		and (end_of_life > %(today)s or end_of_life is null or end_of_life='0000-00-00')
		and exists (select name from `tabBin` bin where bin.item_code=item.name)"""\
		.format(condition=condition), {"today": today()}, as_dict=True)

	condition = ""
	if item_code:
		condition = 'where parent="{0}"'.format(frappe.db.escape(item_code, percent=False))

	reorder_levels = frappe._dict()
	for ir in frappe.db.sql("""select * from `tabItem Reorder` {condition}""".format(condition=condition), as_dict=1):
		if ir.parent not in reorder_levels:
			reorder_levels[ir.parent] = []

		reorder_levels[ir.parent].append(ir)

	item_map = frappe._dict()
	for item in items:
		item["reorder_levels"] = reorder_levels.get(item.name) or []
		item_map[item.name] = item

	return item_map

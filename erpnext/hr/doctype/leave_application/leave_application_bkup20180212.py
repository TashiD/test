# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
'''
--------------------------------------------------------------------------------------------------------------------------
Version          Author          CreatedOn          ModifiedOn          Remarks
------------ --------------- ------------------ -------------------  -----------------------------------------------------
1.0		  SSK		                   20/08/2016         Introducing Leave Encashment Logic
--------------------------------------------------------------------------------------------------------------------------                                                                          
'''
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import nowdate, cint, cstr, date_diff, flt, formatdate, getdate, get_link_to_form, \
	comma_or, get_fullname
from erpnext.hr.utils import set_employee_name
from erpnext.hr.doctype.leave_block_list.leave_block_list import get_applicable_block_dates
from erpnext.hr.doctype.employee.employee import get_holiday_list_for_employee
from erpnext.hr.doctype.employee_leave_approver.employee_leave_approver import get_approver_list
# Ver 1.0 Begins added by SSK on 20/08/2016, Following line is added
#from datetime import date as mod_date
from erpnext.hr.doctype.leave_encashment.leave_encashment import get_le_settings
# Ver 1.0 Ends
from erpnext.custom_utils import get_year_start_date, get_year_end_date
from datetime import timedelta, date

class LeaveDayBlockedError(frappe.ValidationError): pass
class OverlapError(frappe.ValidationError): pass
class InvalidLeaveApproverError(frappe.ValidationError): pass
class LeaveApproverIdentityError(frappe.ValidationError): pass

from frappe.model.document import Document
class LeaveApplication(Document):
	def get_feed(self):
		return _("{0}: From {0} of type {1}").format(self.status, self.employee_name, self.leave_type)

	def validate(self):
		self.validate_dates_ta()
		self.validate_fiscal_year()
		if not getattr(self, "__islocal", None) and frappe.db.exists(self.doctype, self.name):
			self.previous_doc = frappe.db.get_value(self.doctype, self.name, "*", as_dict=True)
		else:
			self.previous_doc = None

		if self.status == "Approved":
			set_employee_name(self)

		self.validate_dates()
		self.validate_balance_leaves()
		self.validate_leave_overlap()
		self.validate_max_days()
		self.show_block_day_warning()
		self.validate_block_days()
		self.validate_salary_processed_days()
		self.validate_leave_approver()

	def on_update(self):
		self.validate_fiscal_year()
		if (not self.previous_doc and self.leave_approver) or (self.previous_doc and \
				self.status == "Open" and self.previous_doc.leave_approver != self.leave_approver):
			# notify leave approver about creation
			self.notify_leave_approver()
		elif self.previous_doc and \
				self.previous_doc.status == "Open" and self.status == "Rejected":
			# notify employee about rejection
			self.notify_employee(self.status)

	def on_submit(self):
		self.validate_dates_ta()
		self.validate_fiscal_year()
		if self.status == "Open":
			frappe.throw(_("Only Leave Applications with status 'Approved' or 'Rejected' can be submitted"))

		if self.status == "Approved":
			#self.validate_back_dated_application()
			# notify leave applier about approval
			self.create_attendance()
			self.notify_employee(self.status)
			immediate_sp = frappe.db.get_value("Employee", frappe.db.get_value("Employee", self.employee, "reports_to"), "user_id")
			if str(immediate_sp) != str(self.leave_approver):
				self.notify_supervisor()

	def on_cancel(self):
		# notify leave applier about cancellation
		self.notify_employee("cancelled")
		self.cancel_attendance()

	def create_attendance(self):
		d = getdate(self.from_date)
		e = getdate(self.to_date)
		days = date_diff(e, d) + 1
		for a in (d + timedelta(n) for n in range(days)):
			if getdate(a).weekday() != 6:
				#create attendance
				attendance = frappe.new_doc("Attendance")
				attendance.flags.ignore_permissions = 1
				attendance.employee = self.employee
				attendance.employee_name = self.employee_name 
				attendance.att_date = a
				attendance.status = "Leave"
				attendance.branch = self.branch
				attendance.company = self.company
				attendance.reference_name = self.name
				attendance.submit()

	def cancel_attendance(self):
		frappe.db.sql("update tabAttendance set docstatus = 2 where reference_name = %s", (self.name))
		frappe.db.commit()	
	
	def validate_dates(self):
		if self.from_date and self.to_date and (getdate(self.to_date) < getdate(self.from_date)):
			frappe.throw(_("To date cannot be before from date"))

		if is_lwp(self.leave_type):
			self.validate_dates_acorss_allocation()
			self.validate_back_dated_application()

	def validate_dates_ta(self):
		start_date = self.from_date
		end_date = self.to_date

		tas = frappe.db.sql("select a.name from `tabTravel Authorization` a, `tabTravel Authorization Item` b where a.employee = %s and a.docstatus = 1 and a.name = b.parent and (b.date between %s and %s or %s between b.date and b.till_date or %s between b.date and b.till_date)", (str(self.employee), str(start_date), str(end_date), str(start_date), str(end_date)), as_dict=True)
		if tas:
			frappe.throw("The dates in your current Travel Authorization has already been used in " + str(tas[0].name))

	def validate_dates_acorss_allocation(self):
		def _get_leave_alloction_record(date):
			allocation = frappe.db.sql("""select name from `tabLeave Allocation`
				where employee=%s and leave_type=%s and docstatus=1
				and %s between from_date and to_date""", (self.employee, self.leave_type, date))

			return allocation and allocation[0][0]

		allocation_based_on_from_date = _get_leave_alloction_record(self.from_date)
		allocation_based_on_to_date = _get_leave_alloction_record(self.to_date)

		if not (allocation_based_on_from_date or allocation_based_on_to_date):
			frappe.throw(_("Application period cannot be outside leave allocation period"))

		elif allocation_based_on_from_date != allocation_based_on_to_date:
			frappe.throw(_("Application period cannot be across two alocation records"))

	def validate_back_dated_application(self):
		future_allocation = frappe.db.sql("""select name, from_date from `tabLeave Allocation`
			where employee=%s and leave_type=%s and docstatus=1 and from_date > %s
			and carry_forward=1""", (self.employee, self.leave_type, self.to_date), as_dict=1)

		if future_allocation:
			frappe.throw(_("Leave cannot be applied/cancelled before {0}, as leave balance has already been carry-forwarded in the future leave allocation record {1}")
				.format(formatdate(future_allocation[0].from_date), future_allocation[0].name))

	def validate_salary_processed_days(self):
		last_processed_pay_slip = frappe.db.sql("""select start_date, end_date from `tabSalary Slip`
						where docstatus != 2 and employee = %s and ((%s between start_date and end_date) or (%s between start_date and end_date)) order by modified desc limit 1""",(self.employee, self.to_date, self.from_date))
                # Ver 1.0 Begins added by SSK, Following validation is commented
                '''
		if last_processed_pay_slip:
			frappe.throw(_("Salary already processed for period between {0} and {1}, Leave application period cannot be between this date range.").
					format(formatdate(last_processed_pay_slip[0][0]), formatdate(last_processed_pay_slip[0][1])))
		'''
                # Ver 1.0 Ends

	def show_block_day_warning(self):
		block_dates = get_applicable_block_dates(self.from_date, self.to_date,
			self.employee, self.company, all_lists=True)

		if block_dates:
			frappe.msgprint(_("Warning: Leave application contains following block dates") + ":")
			for d in block_dates:
				frappe.msgprint(formatdate(d.block_date) + ": " + d.reason)

	def validate_block_days(self):
		block_dates = get_applicable_block_dates(self.from_date, self.to_date,
			self.employee, self.company)

		if block_dates and self.status == "Approved":
			frappe.throw(_("You are not authorized to approve leaves on Block Dates"), LeaveDayBlockedError)

	def validate_balance_leaves(self):
		if self.from_date and self.to_date:
			self.total_leave_days = get_number_of_leave_days(self.employee, self.leave_type,
				self.from_date, self.to_date, self.half_day)

			if self.total_leave_days == 0:
				frappe.throw(_("The day(s) on which you are applying for leave are holidays. You need not apply for leave."))

			if not is_lwp(self.leave_type):
				self.leave_balance = get_leave_balance_on(self.employee, self.leave_type, self.from_date,
					consider_all_leaves_in_the_allocation_period=True)

				if self.status != "Rejected" and self.leave_balance < self.total_leave_days:
					if frappe.db.get_value("Leave Type", self.leave_type, "allow_negative"):
						frappe.msgprint(_("Note: There is not enough leave balance for Leave Type {0}")
							.format(self.leave_type))
					else:
						frappe.throw(_("There is not enough leave balance for Leave Type {0}")
							.format(self.leave_type))

	def validate_leave_overlap(self):
		if not self.name:
			# hack! if name is null, it could cause problems with !=
			self.name = "New Leave Application"

		for d in frappe.db.sql("""select name, leave_type, posting_date, from_date, to_date, total_leave_days
			from `tabLeave Application`
			where employee = %(employee)s and docstatus < 2 and status in ("Open", "Approved")
			and to_date >= %(from_date)s and from_date <= %(to_date)s
			and name != %(name)s""", {
				"employee": self.employee,
				"from_date": self.from_date,
				"to_date": self.to_date,
				"name": self.name
			}, as_dict = 1):

			if d['total_leave_days']==0.5 and cint(self.half_day)==1:
				sum_leave_days = self.get_total_leaves_on_half_day()
				if sum_leave_days==1:
					self.throw_overlap_error(d)
			else:
				self.throw_overlap_error(d)

	def throw_overlap_error(self, d):
		msg = _("Employee {0} has already applied for {1} between {2} and {3}").format(self.employee,
			d['leave_type'], formatdate(d['from_date']), formatdate(d['to_date'])) \
			+ """ <br><b><a href="#Form/Leave Application/{0}">{0}</a></b>""".format(d["name"])
		frappe.throw(msg, OverlapError)

	def get_total_leaves_on_half_day(self):
		return frappe.db.sql("""select sum(total_leave_days) from `tabLeave Application`
			where employee = %(employee)s
			and docstatus < 2
			and status in ("Open", "Approved")
			and from_date = %(from_date)s
			and to_date = %(to_date)s
			and name != %(name)s""", {
				"employee": self.employee,
				"from_date": self.from_date,
				"to_date": self.to_date,
				"name": self.name
			})[0][0]

	def validate_max_days(self):
		max_days = frappe.db.get_value("Leave Type", self.leave_type, "max_days_allowed")
		if max_days and flt(self.total_leave_days) > flt(max_days):
			frappe.throw(_("Leave of type {0} cannot be longer than {1} days").format(self.leave_type, max_days))

	def validate_leave_approver(self):
		employee = frappe.get_doc("Employee", self.employee)
		all_app = get_approvers("User", "", "", "", "", {"employee": self.employee})
		leave_approvers = []
		for a in all_app:
			leave_approvers.append(a[0])

		if len(leave_approvers) and self.leave_approver not in leave_approvers:
			frappe.throw(_("Leave approver must be one of {0}")
				.format(comma_or(leave_approvers)), InvalidLeaveApproverError)

		elif self.leave_approver and not frappe.db.sql("""select name from `tabUserRole`
			where parent=%s and role='Approver'""", self.leave_approver):
			frappe.throw(_("{0} ({1}) must have role 'Leave Approver'")\
				.format(get_fullname(self.leave_approver), self.leave_approver), InvalidLeaveApproverError)

		elif self.docstatus==1 and len(leave_approvers) and self.leave_approver != frappe.session.user:
			frappe.throw(_("Only the selected Leave Approver can submit this Leave Application"),
				LeaveApproverIdentityError)

	def notify_employee(self, status):
		employee = frappe.get_doc("Employee", self.employee)
		if not employee.user_id:
			return

		def _get_message(url=False):
			if url:
				name = get_link_to_form(self.doctype, self.name)
			else:
				name = self.name

			return (_("Leave Application") + ": %s - %s") % (name, _(status))

		self.notify({
			# for post in messages
			"message": _get_message(url=True),
			"message_to": employee.user_id,
			"subject": _get_message(),
		})

	def notify_leave_approver(self):
		employee = frappe.get_doc("Employee", self.employee)

		def _get_message(url=False):
			name = self.name
			employee_name = cstr(employee.employee_name)
			if url:
				name = get_link_to_form(self.doctype, self.name)
				employee_name = get_link_to_form("Employee", self.employee, label=employee_name)

			return (_("New Leave Application") + ": %s - " + _("Employee") + ": %s") % (name, employee_name)

		self.notify({
			# for post in messages
			"message": _get_message(url=True),
			"message_to": self.leave_approver,

			# for email
			"subject": _get_message()
		})

	def notify_supervisor(self):
		employee = frappe.get_doc("Employee", self.employee)
		supervisor = frappe.db.get_value("Employee", employee.reports_to, "user_id")

		def _get_message(url=False):
			name = self.name
			employee_name = cstr(employee.employee_name)
			if url:
				name = get_link_to_form(self.doctype, self.name)
				employee_name = get_link_to_form("Employee", self.employee, label=employee_name)

			return (_("New Leave Application") + ": %s - " + _("Employee") + ": %s") % (name, employee_name)

		self.notify({
			# for post in messages
			"message": _get_message(url=True),
			"message_to": supervisor,

			# for email
			"subject": _get_message()
		})

	def notify(self, args):
		args = frappe._dict(args)
		from frappe.desk.page.chat.chat import post
		post(**{"txt": args.message, "contact": args.message_to, "subject": args.subject,
			"notify": cint(self.follow_via_email)})

	def validate_fiscal_year(self):
		if str(self.from_date)[0:4] != str(self.to_date)[0:4]:
			frappe.throw("Leave Application cannot overlap fiscal years")

def daterange(start_date, end_date):
    for n in range(int ((date(end_date) - date(start_date)).days)):
	yield date(start_date) + timedelta(n)


@frappe.whitelist()
def get_approvers(doctype, txt, searchfield, start, page_len, filters):
	app_list = []
	if not filters.get("employee"):
		frappe.throw(_("Please select Employee Record first."))

	employee_user = frappe.get_value("Employee", filters.get("employee"), "user_id")

	approver = frappe.get_value("Employee", filters.get("employee"), "reports_to")
	approver_id = frappe.get_value("Employee", approver, "user_id")
	if not approver:
		frappe.throw("Set Reports To Field in Employee")
	app_list.append(str(approver_id))

	d = frappe.db.get_value("DepartmentDirector", {"department": frappe.get_value("Employee", filters.get("employee"), "department")}, "director")
	if d:
		app_list.append(str(d))
	"""ceo = frappe.db.get_value("Employee", {"employee_subgroup": "CEO", "status": "Active"}, "user_id")
	if ceo:
		app_list.append(str(ceo))
	"""
	#Check for Officiating Employeee, if so, replace
	for a, b in enumerate(app_list):
		off = frappe.db.sql("select officiate from `tabOfficiating Employee` where docstatus = 1 and revoked != 1 and %(today)s between from_date and to_date and employee = %(employee)s", {"today": nowdate(), "employee": frappe.db.get_value("Employee", {"user_id": app_list[a]}, "name")}, as_dict=True)
		if off:
			app_list[a] = str(frappe.db.get_value("Employee", off[0].officiate, "user_id"))
	
	approvers = ""
	for a in app_list:
		approvers += "\'"+str(a)+"\',"
	approvers += "\'dshfghasfgqyegfheqkhjf\'"

	query = "select emp.user_id, emp.employee_name, emp.designation from tabEmployee emp where emp.user_id in (" + str(approvers) + ")"
	lists = frappe.db.sql(query)

	if lists:
		return lists
	else:
		frappe.throw("Set \'Reports To\' field for employee " + str(filters.get("employee")))

@frappe.whitelist()
def get_number_of_leave_days(employee, leave_type, from_date, to_date, half_day=0):
	if half_day == 1:
		return 0.5

	number_of_days = date_diff(to_date, from_date) + 1
	if not frappe.db.get_value("Leave Type", leave_type, "include_holiday"):
		number_of_days = flt(number_of_days) - flt(get_holidays(employee, from_date, to_date))

	d = from_date
	while(d <= to_date):
		#For Saturday half day work time
		if getdate(d).weekday() == 5 and flt(get_holidays(employee, d, d)) == 0:
			number_of_days-=0.5
		d = frappe.utils.data.add_days(d, 1)
	
	return number_of_days

	

@frappe.whitelist()
def get_leave_balance_on(employee, leave_type, date, allocation_records=None,
		consider_all_leaves_in_the_allocation_period=False):
	if allocation_records == None:
		allocation_records = get_leave_allocation_records(date, employee).get(employee, frappe._dict())

	allocation = allocation_records.get(leave_type, frappe._dict())
        #frappe.msgprint(_("Employee: {0} Leave Type{1} Total Leaves Allocated: {2}").format(employee,allocation.leave_type,flt(allocation.total_leaves_allocated)))

	if consider_all_leaves_in_the_allocation_period:
		date = allocation.to_date
	leaves_taken = get_approved_leaves_for_period(employee, leave_type, get_year_start_date(str(date)), date)
	# Ver 1.0 Begins added by SSK on 20/08/2016, following line is added
	#leaves_encashed = get_leaves_encashed(employee, leave_type, date)
	# Ver 1.0 Ends

        le = get_le_settings()
        if leave_type == 'Earned Leave' and \
           flt(flt(allocation.total_leaves_allocated) - flt(leaves_taken)) > flt(le.encashment_lapse):
           #flt(flt(allocation.total_leaves_allocated) - flt(leaves_taken) - flt(leaves_encashed)) > flt(le.encashment_lapse):
                return flt(le.encashment_lapse)
	
	#reseting earned leave taken to 0 since it is already minused in the allocation
        if leave_type == 'Earned Leave':
		leaves_taken = 0
        
	return flt(allocation.total_leaves_allocated) - flt(leaves_taken)
	#return flt(allocation.total_leaves_allocated) - flt(leaves_taken) - flt(leaves_encashed)

# Ver 1.0 Begins added by SSK on 20/08/2016, following function is added
def get_leaves_encashed(employee=None, leave_type=None, from_date=None):
        from datetime import date

        from_date = getdate(date(getdate(from_date).year,1,1))
        to_date = getdate(date(getdate(from_date).year,12,31))

        leaves_encashed = frappe.db.sql("""
                select sum(ifnull(encashed_days,0)) from `tabLeave Encashment`
                where employee = %s and leave_type = %s and docstatus = 1
                and application_date between %s and %s
                """,(employee, leave_type, from_date, to_date))

        return leaves_encashed[0][0] if leaves_encashed[0][0] else 0
# Ver 1.0 Ends

def get_approved_leaves_for_period(employee, leave_type, from_date, to_date):
	leave_applications = frappe.db.sql("""
		select employee, leave_type, from_date, to_date, total_leave_days
		from `tabLeave Application`
		where employee=%(employee)s and leave_type=%(leave_type)s
			and status="Approved" and docstatus=1
			and (from_date between %(from_date)s and %(to_date)s
				or to_date between %(from_date)s and %(to_date)s
				or (from_date < %(from_date)s and to_date > %(to_date)s))
	""", {
		"from_date": from_date,
		"to_date": to_date,
		"employee": employee,
		"leave_type": leave_type
	}, as_dict=1)

	leave_days = 0
	for leave_app in leave_applications:
		if leave_app.from_date >= getdate(from_date) and leave_app.to_date <= getdate(to_date):
			leave_days += leave_app.total_leave_days
		else:
			if leave_app.from_date < getdate(from_date):
				leave_app.from_date = from_date
			if leave_app.to_date > getdate(to_date):
				leave_app.to_date = to_date

			leave_days += get_number_of_leave_days(employee, leave_type,
				leave_app.from_date, leave_app.to_date)

	return leave_days

def get_leave_allocation_records(date, employee=None):
        from datetime import date as mod_date
	conditions = (" and employee='%s'" % employee) if employee else ""
	from_date = date
        from_date = getdate(mod_date(getdate(from_date).year,1,1))

	leave_allocation_records = frappe.db.sql("""
		select employee, leave_type, total_leaves_allocated, from_date, to_date
		from `tabLeave Allocation`
		where %s between from_date and to_date and docstatus=1 {0}""".format(conditions), (date), as_dict=1)

	allocated_leaves = frappe._dict()
	for d in leave_allocation_records:
                # Ver 1.0 Begins added by SSK on 20/08/2016, Latest allocation record for Earned Leave is handled later
                if d.leave_type != 'Earned Leave':
                        allocated_leaves.setdefault(d.employee, frappe._dict()).setdefault(d.leave_type, frappe._dict({
                                "from_date": d.from_date,
                                "to_date": d.to_date,
                                "total_leaves_allocated": d.total_leaves_allocated
                        }))
        
        # Ver 1.0 Begins added by SSK on 20/08/2016, Earned Leave
        if employee:
                leave_allocation_records = frappe.db.sql("""
                        select employee, leave_type, total_leaves_allocated, from_date, to_date
                        from `tabLeave Allocation`
                        where from_date <= %s
                        and docstatus=1 and leave_type = 'Earned Leave'
                        {0}
                        order by to_date desc limit 1""".format(conditions), (date), as_dict=1)

                for d in leave_allocation_records:
                        if d.leave_type == 'Earned Leave':
                                allocated_leaves.setdefault(d.employee, frappe._dict()).setdefault(d.leave_type, frappe._dict({
                                        "from_date": d.from_date,
                                        "to_date": d.to_date,
                                        "total_leaves_allocated": d.total_leaves_allocated
                                }))
        else:
                employee_list = frappe.db.sql("""
                        select distinct employee
                        from `tabLeave Allocation`
                        where from_date <= %s
                        and docstatus=1 and leave_type = 'Earned Leave'
                        """, (date), as_dict=1)
                for e in employee_list:
                        leave_allocation_records = frappe.db.sql("""
                                select employee, leave_type, total_leaves_allocated, from_date, to_date
                                from `tabLeave Allocation`
                                where employee = %s
                                and from_date <= %s
                                and docstatus=1 and leave_type = 'Earned Leave'
                                order by to_date desc limit 1""", (e.employee, date), as_dict=1)
                        
                        for d in leave_allocation_records:
                                if d.leave_type == 'Earned Leave':
                                        allocated_leaves.setdefault(d.employee, frappe._dict()).setdefault(d.leave_type, frappe._dict({
                                                "from_date": d.from_date,
                                                "to_date": d.to_date,
                                                "total_leaves_allocated": d.total_leaves_allocated
                                        }))
        # Ver 1.0 Ends
	return allocated_leaves


def get_holidays(employee, from_date, to_date):
	'''get holidays between two dates for the given employee'''
	holiday_list = get_holiday_list_for_employee(employee)

	holidays = frappe.db.sql("""select count(distinct holiday_date) from `tabHoliday` h1, `tabHoliday List` h2
		where h1.parent = h2.name and h1.holiday_date between %s and %s
		and h2.name = %s""", (from_date, to_date, holiday_list))[0][0]

	return holidays

def is_lwp(leave_type):
	lwp = frappe.db.sql("select is_lwp from `tabLeave Type` where name = %s", leave_type)
	return lwp and cint(lwp[0][0]) or 0

@frappe.whitelist()
def get_events(start, end):
	events = []

	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, ["name", "company"],
		as_dict=True)
	if not employee:
		return events

	employee, company = employee.name, employee.company

	from frappe.desk.reportview import build_match_conditions
	match_conditions = build_match_conditions("Leave Application")

	# show department leaves for employee
	if "Employee" in frappe.get_roles():
		add_department_leaves(events, start, end, employee, company)

	add_leaves(events, start, end, match_conditions)

	add_block_dates(events, start, end, employee, company)
	add_holidays(events, start, end, employee, company)

	return events

def add_department_leaves(events, start, end, employee, company):
	department = frappe.db.get_value("Employee", employee, "department")

	if not department:
		return

	# department leaves
	department_employees = frappe.db.sql_list("""select name from tabEmployee where department=%s
		and company=%s""", (department, company))

	match_conditions = "employee in (\"%s\")" % '", "'.join(department_employees)
	add_leaves(events, start, end, match_conditions=match_conditions)

def add_leaves(events, start, end, match_conditions=None):
	query = """select name, from_date, to_date, employee_name, half_day,
		status, employee, docstatus
		from `tabLeave Application` where
		(from_date between %s and %s or to_date between %s and %s)
		and docstatus < 2
		and status!="Rejected" """
	if match_conditions:
		query += " and " + match_conditions

	for d in frappe.db.sql(query, (start, end, start, end), as_dict=True):
		e = {
			"name": d.name,
			"doctype": "Leave Application",
			"from_date": d.from_date,
			"to_date": d.to_date,
			"status": d.status,
			"title": cstr(d.employee_name) + \
				(d.half_day and _(" (Half Day)") or ""),
			"docstatus": d.docstatus
		}
		if e not in events:
			events.append(e)

def add_block_dates(events, start, end, employee, company):
	# block days
	from erpnext.hr.doctype.leave_block_list.leave_block_list import get_applicable_block_dates

	cnt = 0
	block_dates = get_applicable_block_dates(start, end, employee, company, all_lists=True)

	for block_date in block_dates:
		events.append({
			"doctype": "Leave Block List Date",
			"from_date": block_date.block_date,
			"to_date": block_date.block_date,
			"title": _("Leave Blocked") + ": " + block_date.reason,
			"name": "_" + str(cnt),
		})
		cnt+=1

def add_holidays(events, start, end, employee, company):
	applicable_holiday_list = get_holiday_list_for_employee(employee, company)
	if not applicable_holiday_list:
		return

	for holiday in frappe.db.sql("""select name, holiday_date, description
		from `tabHoliday` where parent=%s and holiday_date between %s and %s""",
		(applicable_holiday_list, start, end), as_dict=True):
			events.append({
				"doctype": "Holiday",
				"from_date": holiday.holiday_date,
				"to_date":  holiday.holiday_date,
				"title": _("Holiday") + ": " + cstr(holiday.description),
				"name": holiday.name
			})

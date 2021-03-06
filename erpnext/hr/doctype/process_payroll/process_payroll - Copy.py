# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
'''
--------------------------------------------------------------------------------------------------------------------------
Version          Author          CreatedOn          ModifiedOn          Remarks
------------ --------------- ------------------ -------------------  -----------------------------------------------------
1.0		  SHIV		                   03/08/2016         Remove Button is added.
2.0               SHIV                             03/04/2018         Code refined to accomodate following requirements.
                                                                        1) Post remittance entries dynamically via is_remittable
                                                                                setting under salary component.
                                                                        2) Clubbing components and posting accumulated entry.
                                                                        3) Party wise entries if required.
--------------------------------------------------------------------------------------------------------------------------                                                                          
'''
from __future__ import unicode_literals
import frappe
from frappe import _
from frappe import msgprint
from frappe.model.document import Document
from frappe.utils import cint, flt, nowdate, money_in_words
from erpnext.hr.hr_custom_functions import get_month_details

class ProcessPayroll(Document):

	def get_emp_list(self):
		"""
			Returns list of active employees based on selected criteria
			and for which salary structure exists
		"""
		cond = self.get_filter_condition()
		cond += self.get_joining_releiving_condition()

		emp_list = frappe.db.sql("""
			select t1.name, t1.cost_center
			from `tabEmployee` t1, `tabSalary Structure` t2
			where t1.docstatus!=2 and t2.docstatus != 2 and 
			ifnull(t2.salary_slip_based_on_timesheet,0) = 0 and t1.name = t2.employee
		%s """% cond, as_dict=True)

		return emp_list

	def get_filter_condition(self):
		self.check_mandatory()

		cond = ''
		for f in ['company', 'employee']:
			if self.get(f):
				cond += " and t1." + f + " = '" + self.get(f).replace("'", "\'") + "'"

		return cond


	def get_joining_releiving_condition(self):
		m = get_month_details(self.fiscal_year, self.month)
		cond = """
			and ifnull(t1.date_of_joining, '0000-00-00') <= '%(month_end_date)s'
			and ifnull(t1.relieving_date, '%(month_end_date)s') >= '%(month_start_date)s'
		""" % m
		return cond

	def check_mandatory(self):
		for f in ['company', 'month', 'fiscal_year']:
			if not self.get(f):
				frappe.throw(_("Please set {0}").format(f))

	def create_sal_slip(self):
		"""
			Creates salary slip for selected employees if already not created
		"""

		self.check_permission('write')

		emp_list = self.get_emp_list()
		ss_list = []
		for emp in emp_list:
			if not frappe.db.sql("""select name from `tabSalary Slip`
					where docstatus!= 2 and employee = %s and month = %s and fiscal_year = %s and company = %s
					""", (emp.name, self.month, self.fiscal_year, self.company)):
				ss = frappe.get_doc({
					"doctype": "Salary Slip",
					"salary_slip_based_on_timesheet": 0,
					"fiscal_year": self.fiscal_year,
					"cost_center": emp.cost_center,
					"employee": emp.name,
					"month": self.month,
					"company": self.company,
				})
				ss.insert()
				ss_list.append(ss.name)

		return self.create_log(ss_list)

        def remove_sal_slip(self):
		cond = ''
		#for f in ['company', 'branch', 'department', 'division', 'designation', 'employee']:
		for f in ['company', 'employee']:
			if self.get(f):
				cond += " and t1." + f + " = '" + self.get(f).replace("'", "\'") + "'"
                
                ss_list = frappe.db.sql_list("""
                                select t1.name from `tabSalary Slip` as t1
                                where t1.fiscal_year = '%s'
                                and t1.month = '%s'
                                and t1.docstatus = 0
                                %s
                                """ % (self.fiscal_year, self.month, cond))
                                
                if ss_list:
                        frappe.delete_doc("Salary Slip", frappe.db.sql_list("""
                                select t1.name from `tabSalary Slip` as t1
                                where t1.fiscal_year = '%s'
                                and t1.month = '%s'
                                and t1.docstatus = 0
                                %s
                                """ % (self.fiscal_year, self.month, cond)), for_reload=True)
                        frappe.msgprint(_("Un-submitted Salary Slip(s) for the Month:{0} and Year:{1} removed successfully.")\
                                        .format(self.month, self.fiscal_year))
                else:
                        frappe.msgprint(_("No Un-submitted Salary Slip(s) Found."))
                

	def create_log(self, ss_list):
		log = "<p>" + _("No employee for the above selected criteria OR salary slip already created") + "</p>"
		if ss_list:
			log = "<b>" + _("Salary Slip Created") + "</b>\
			<br><br>%s" % '<br>'.join(self.format_as_links(ss_list))
		return log


	def get_sal_slip_list(self):
		"""
			Returns list of salary slips based on selected criteria
			which are not submitted
		"""
		cond = self.get_filter_condition()
		ss_list = frappe.db.sql("""
			select t1.name from `tabSalary Slip` t1
			where t1.docstatus = 0 and month = %s and fiscal_year = %s %s
		""" % ('%s', '%s', cond), (self.month, self.fiscal_year))
		return ss_list


	def submit_salary_slip(self):
		"""
			Submit all salary slips based on selected criteria
		"""
		self.check_permission('write')

		ss_list = self.get_sal_slip_list()
		not_submitted_ss = []
		for ss in ss_list:
			ss_obj = frappe.get_doc("Salary Slip",ss[0])
			try:
				ss_obj.submit()
			except Exception,e:
				not_submitted_ss.append(ss[0])
				frappe.msgprint(str(e))
				continue

		return self.create_submit_log(ss_list, not_submitted_ss)


	def create_submit_log(self, all_ss, not_submitted_ss):
		log = ''
		if not all_ss:
			log = "No salary slip found to submit for the above selected criteria"
		else:
			all_ss = [d[0] for d in all_ss]

		submitted_ss = self.format_as_links(list(set(all_ss) - set(not_submitted_ss)))
		if submitted_ss:
			log = """
				<b>Salary Slips Submitted:</b> <br><br>%s
				""" % ('<br>'.join(submitted_ss))

		if not_submitted_ss:
			log += """
				<b>Not Submitted Salary Slips: </b>\
				<br><br> %s <br><br> \
				Reason: <br>\
				May be company email id specified in employee master is not valid. <br> \
				Please mention correct email id in employee master or if you don't want to \
				send mail, uncheck 'Send Email' checkbox. <br>\
				Then try to submit Salary Slip again.
			"""% ('<br>'.join(not_submitted_ss))
		return log

	def format_as_links(self, ss_list):
		return ['<a href="#Form/Salary Slip/{0}">{1}</a>'.format(s, frappe.db.get_value("Salary Slip", s, "employee_name")) for s in ss_list]


	def get_total_salary(self):
		"""
			Get total salary amount from submitted salary slip based on selected criteria
		"""
		cond = self.get_filter_condition()
		tot = frappe.db.sql("""
			select sum(rounded_total) from `tabSalary Slip` t1
			where t1.docstatus = 1 and month = %s and fiscal_year = %s %s
		""" % ('%s', '%s', cond), (self.month, self.fiscal_year))

		return flt(tot[0][0])

        #
        # Ver20180403 added by SSK, account rules
        #
        def get_account_rules(self):
                # Default Accounts
                default_bank_account    = frappe.db.get_value("Branch", self.branch,"expense_bank_account")
                default_payable_account = frappe.db.get_single_value("HR Accounts Settings", "salary_payable_account")
                default_gpf_account     = frappe.db.get_single_value("HR Accounts Settings", "employee_contribution_pf")
                salary_component_pf     = "PF"

                # Filters
                cond = self.get_filter_condition()
                
                # Salary Details
                cc = frappe.db.sql("""
                        select
                                t1.cost_center             as cost_center,
                                (case
                                        when sc.type = 'Earning' then sc.type
                                        else ifnull(sc.clubbed_component,sc.name)
                                end)                       as salary_component,
                                sc.type                    as component_type,
                                (case
                                        when sc.type = 'Earning' then 0
                                        else ifnull(sc.is_remittable,0)
                                end)                       as is_remittable,
                                sc.gl_head                 as gl_head,
                                sum(ifnull(sd.amount,0))   as amount,
                                (case
                                        when ifnull(sc.make_party_entry,0) = 1 then 'Payable'
                                        else 'Other'
                                end) as account_type,
                                (case
                                        when ifnull(sc.make_party_entry,0) = 1 then 'Employee'
                                        else 'Other'
                                end) as party_type,
                                (case
                                        when ifnull(sc.make_party_entry,0) = 1 then t1.employee
                                        else 'Other'
                                end) as party
                         from
                                `tabSalary Detail` sd,
                                `tabSalary Slip` t1,
                                `tabSalary Component` sc
                        where t1.fiscal_year = '{0}'
                          and t1.month       = '{1}'
                          and t1.docstatus   = 1
                          {2}
                          and sd.parent      = t1.name
                          and sc.name        = sd.salary_component
                        group by t1.cost_center,
                                (case when sc.type = 'Earning' then sc.type else ifnull(sc.clubbed_component,sc.name) end),
                                sc.type,
                                (case when sc.type = 'Earning' then 0 else ifnull(sc.is_remittable,0) end),
                                sc.gl_head,
                                (case when ifnull(sc.make_party_entry,0) = 1 then 'Payable' else 'Other' end),
                                (case when ifnull(sc.make_party_entry,0) = 1 then 'Employee' else 'Other' end),
                                (case when ifnull(sc.make_party_entry,0) = 1 then t1.employee else 'Other' end)
                        order by t1.cost_center, sc.type, sc.name
                """.format(self.fiscal_year, self.month, cond),as_dict=1)

                posting        = frappe._dict()
                cc_wise_totals = frappe._dict()
                for rec in cc:
                        # Cost Center wise net payables
                        amount = (-1*flt(rec.amount) if rec.component_type == 'Deduction' else flt(rec.amount))
                        if cc_wise_totals.has_key(rec.cost_center):
                                cc_wise_totals[rec.cost_center] += amount
                        else:
                                cc_wise_totals[rec.cost_center]  = amount

                        # To Payables
                        posting.setdefault("to_payables",[]).append({
                                "account"        : rec.gl_head,
                                "credit_in_account_currency" if rec.component_type == 'Deduction' else "debit_in_account_currency": flt(rec.amount),
                                "against_account": default_payable_account,
                                "cost_center"    : rec.cost_center,
                                "party_check"    : 0,
                                "account_type"   : rec.account_type if rec.party_type == "Employee" else "",
                                "party_type"     : rec.party_type if rec.party_type == "Employee" else "",
                                "party"          : rec.party if rec.party_type == "Employee" else "" 
                        }) 
                                
                        # Remittance
                        if rec.is_remittable and rec.component_type == 'Deduction':
                                remit_amount    = 0
                                remit_gl_list   = [rec.gl_head,default_gpf_account] if rec.salary_component == salary_component_pf else [rec.gl_head]

                                for r in remit_gl_list:
                                        remit_amount += flt(rec.amount)
                                        posting.setdefault(rec.salary_component,[]).append({
                                                "account"       : r,
                                                "debit_in_account_currency" : flt(rec.amount),
                                                "cost_center"   : rec.cost_center,
                                                "party_check"   : 0,
                                                "account_type"   : rec.account_type if rec.party_type == "Employee" else "",
                                                "party_type"     : rec.party_type if rec.party_type == "Employee" else "",
                                                "party"          : rec.party if rec.party_type == "Employee" else "" 
                                        })
                                        
                                posting.setdefault(rec.salary_component,[]).append({
                                        "account"       : default_bank_account,
                                        "credit_in_account_currency" : flt(remit_amount),
                                        "cost_center"   : rec.cost_center,
                                        "party_check"   : 0
                                })

                # To Bank
                for key,value in cc_wise_totals.iteritems():
                        posting.setdefault("to_bank",[]).append({
                                "account"       : default_payable_account,
                                "debit_in_account_currency": value,
                                "cost_center"   : key,
                                "party_check"   : 0
                        })
                        posting.setdefault("to_bank",[]).append({
                                "account"       : default_bank_account,
                                "credit_in_account_currency": value,
                                "cost_center"   : key,
                                "party_check"   : 0
                        })
                        posting.setdefault("to_payables",[]).append({
                                "account"       : default_payable_account,
                                "credit_in_account_currency" : value,
                                "cost_center"   : key,
                                "party_check"   : 0
                        })

                # Final Posting to accounts
                if posting:
                        for i in posting:
                                if i == "to_payables":
                                        v_title         = "To Payables"
                                        v_voucher_type  = "Journal Entry"
                                        v_naming_series = "Journal Voucher"
                                else:
                                        v_title         = "To Bank" if i == "to_bank" else i
                                        v_voucher_type  = "Bank Entry"
                                        v_naming_series = "Bank Payment Voucher"
                                        
                                doc = frappe.get_doc({
                                                "doctype": "Journal Entry",
                                                "voucher_type": v_voucher_type,
                                                "naming_series": v_naming_series,
                                                "title": "Salary ["+str(self.fiscal_year)+str(self.month)+"] - "+str(v_title),
                                                "fiscal_year": self.fiscal_year,
                                                "user_remark": "Salary ["+str(self.fiscal_year)+str(self.month)+"] - "+str(v_title),
                                                "posting_date": nowdate(),                     
                                                "company": self.company,
                                                "accounts": sorted(posting[i], key=lambda item: item['cost_center']),
                                                "branch": self.branch
                                        })
                                doc.flags.ignore_permissions = 1 
                                doc.insert()
                        frappe.msgprint(_("Salary posting to accounts is successful."),title="Posting Successful")
                else:
                        frappe.throw(_("No data found"),title="Posting failed")

        # 20180403 by SSK, Following method is replaced by 
        def get_account_rules_x(self):
                items = []
                cond = self.get_filter_condition()
                cond1 = ''
                
		for f in ['company', 'employee']:
			if self.get(f):
				cond1 += " and ss." + f + " = '" + self.get(f).replace("'", "\'") + "'"
		
                items.extend(frappe.db.sql("""select t1.cost_center,
                        sum(ifnull(t1.rounded_total,0)) as total_amt
                         from `tabSalary Slip` t1
                        where t1.month = %s
                          and t1.fiscal_year = %s
                          and t1.docstatus = 1 
                          %s
                        group by t1.cost_center
                """ % (self.month, self.fiscal_year, cond),as_dict=1))
		
                #
                # GL Mapping
                #
                accounts = []
                tot_deductions = 0
                tot_earnings = 0
                default_payable_account = frappe.db.get_single_value("HR Accounts Settings", "salary_payable_account")
                default_gpf_account = frappe.db.get_single_value("HR Accounts Settings", "employee_contribution_pf")
                default_gis_account = frappe.db.get_value("Salary Component", 'Group Insurance Scheme',"gl_head")
                default_pf_account = frappe.db.get_value("Salary Component", 'PF',"gl_head")
                default_loan_account = frappe.db.get_value("Salary Component", 'Financial Institution Loan',"gl_head")
                default_saving_account = frappe.db.get_value("Salary Component", 'Salary Saving Scheme',"gl_head")
                default_tax_account = frappe.db.get_value("Salary Component", 'Salary Tax',"gl_head")
                default_health_account = frappe.db.get_value("Salary Component", 'Health Contribution',"gl_head")
                default_saladv_account = frappe.db.get_value("Salary Component", 'Salary Advance Deductions',"gl_head")

                # Mandatory GL Checking
                if not default_payable_account:
                        frappe.throw("Setup Default Salary Payable Account in `HR Accounts Settings`")

                for item in items:
                        deductions = []
                        earnings = []
                        item_deductions = 0
                        item_earnings = 0

                        #
                        # Deductions
                        #
                        query = """select dt.gl_head as account,
                                sum(ifnull(amount,0)) as credit_in_account_currency,
                                '%s' as against_account,
                                '%s' as cost_center,
                                0 as party_check
                                from `tabSalary Detail` sd, `tabSalary Slip` ss, `tabSalary Component` dt
                               where ss.name = sd.parent
                                 and sd.amount > 0
                                 and dt.name = sd.salary_component
                                 and ss.month = '%s'
                                 and ss.fiscal_year = %s
                                 and ss.docstatus = 1
                                 and ss.cost_center = '%s'
                                 and dt.gl_head <> '%s'
                                 and dt.type = 'Deduction'
                                 %s
                               group by dt.gl_head
                                """ % (default_payable_account,item['cost_center'],self.month, self.fiscal_year, item['cost_center'], default_saladv_account, cond1)
                        deductions.extend(frappe.db.sql(query, as_dict=1))

                        # Salary Advance
                        query2 = """select dt.gl_head as account,
                                sum(ifnull(amount,0)) as credit_in_account_currency,
                                '%s' as against_account,
                                '%s' as cost_center,
                                0 as party_check,
                                'Payable' as account_type,
                                'Employee' as party_type,
                                ss.employee as party
                                from `tabSalary Detail` sd, `tabSalary Slip` ss, `tabSalary Component` dt
                               where ss.name = sd.parent
                                 and sd.amount > 0
                                 and dt.name = sd.salary_component
                                 and ss.month = '%s'
                                 and ss.fiscal_year = %s
                                 and ss.docstatus = 1
                                 and ss.cost_center = '%s'
                                 and dt.gl_head = '%s'
                                 and dt.type = 'Deduction'
                                 %s
                               group by dt.gl_head, ss.employee
                                """ % (default_payable_account,item['cost_center'],self.month, self.fiscal_year, item['cost_center'], default_saladv_account, cond1)
                        deductions.extend(frappe.db.sql(query2, as_dict=1))                        
                        accounts.extend(deductions)

                        # Total Deductions
                        for deduction in deductions:
                                item_deductions += deduction['credit_in_account_currency']
                                tot_deductions += deduction['credit_in_account_currency']

                        #
                        # Earnings
                        #
                        query = """select et.gl_head as account,
                                sum(ifnull(amount,0)) as debit_in_account_currency,
                                '%s' as against_account,
                                '%s' as cost_center,
                                0 as party_check, se.salary_component
                                from `tabSalary Detail` se, `tabSalary Slip` ss, `tabSalary Component` et
                               where ss.name = se.parent
                                 and se.amount > 0
                                 and et.name = se.salary_component
                                 and et.type = 'Earning'
                                 and ss.month = '%s'
                                 and ss.fiscal_year = %s
                                 and ss.docstatus = 1
                                 and ss.cost_center = '%s'
                                 %s
                               group by et.gl_head
                                """ % (default_payable_account,item['cost_center'],self.month, self.fiscal_year, item['cost_center'], cond1)
                        earnings.extend(frappe.db.sql(query, as_dict=1))
                        accounts.extend(earnings)

                        # Total Earnings
                        for earning in earnings:
                                item_earnings += earning['debit_in_account_currency']
                                tot_earnings += earning['debit_in_account_currency']

                        if item_deductions <= item_earnings:
                                accounts.append({"account": default_payable_account,
                                                 "credit_in_account_currency": (item_earnings-item_deductions),
                                                 "cost_center": item['cost_center'],
                                                 "party_check": 0})
                                
                # Remittance
                bank = []
                gis = []                
                pf = []
                loan = []
                saving = []                
                tax = []
                health = []
                temp = []

                tot_bank = 0
                tot_gis = 0
                tot_pf = 0
                tot_loan = 0
                tot_saving = 0
                tot_tax = 0
                tot_health = 0
                
                for list_item in accounts:
                        #msgprint(_("{0}").format(list_item['account']))
                        if default_payable_account == list_item['account']:
                                bank.append({"account": list_item['account'],
                                                 "debit_in_account_currency": list_item['credit_in_account_currency'],
                                                 "cost_center": list_item['cost_center'],
                                                 "party_check": 0})
                                tot_bank += list_item['credit_in_account_currency']
                        elif default_gis_account == list_item['account']:
                                gis.append({"account": list_item['account'],
                                                 "debit_in_account_currency": list_item['credit_in_account_currency'],
                                                 "cost_center": list_item['cost_center'],
                                                 "party_check": 0})
                                tot_gis += list_item['credit_in_account_currency']
                        elif default_pf_account == list_item['account']:
                                # Employee PF
                                pf.append({"account": list_item['account'],
                                                 "debit_in_account_currency": list_item['credit_in_account_currency'],
                                                 "cost_center": list_item['cost_center'],
                                                 "party_check": 0})
                                tot_pf += list_item['credit_in_account_currency']

                                # Employer PF
                                pf.append({"account": default_gpf_account,
                                                 "debit_in_account_currency": list_item['credit_in_account_currency'],
                                                 "cost_center": list_item['cost_center'],
                                                 "party_check": 0})
                                tot_pf += list_item['credit_in_account_currency']                                
                        elif default_loan_account == list_item['account']:
                                loan.append({"account": list_item['account'],
                                                 "debit_in_account_currency": list_item['credit_in_account_currency'],
                                                 "cost_center": list_item['cost_center'],
                                                 "party_check": 0})
                                tot_loan += list_item['credit_in_account_currency']
                        elif default_saving_account == list_item['account']:
                                saving.append({"account": list_item['account'],
                                                 "debit_in_account_currency": list_item['credit_in_account_currency'],
                                                 "cost_center": list_item['cost_center'],
                                                 "party_check": 0})
                                tot_saving += list_item['credit_in_account_currency']
                        elif default_tax_account == list_item['account']:
                                tax.append({"account": list_item['account'],
                                                 "debit_in_account_currency": list_item['credit_in_account_currency'],
                                                 "cost_center": list_item['cost_center'],
                                                 "party_check": 0})
                                temp.append({"account": list_item['account'],
                                                 "debit_in_account_currency": list_item['credit_in_account_currency'],
                                                 "cost_center": list_item['cost_center'],
                                                 "party_check": 0})                                
                                tot_tax += list_item['credit_in_account_currency']
                        elif default_health_account == list_item['account']:
                                health.append({"account": list_item['account'],
                                                 "debit_in_account_currency": list_item['credit_in_account_currency'],
                                                 "cost_center": list_item['cost_center'],
                                                 "party_check": 0})
                                temp.append({"account": list_item['account'],
                                                 "debit_in_account_currency": list_item['credit_in_account_currency'],
                                                 "cost_center": list_item['cost_center'],
                                                 "party_check": 0})                                
                                tot_health += list_item['credit_in_account_currency']

                if tot_bank:
                        # To Salary Payable
                        title = _('Salary {0}{1} - To Payables').format(self.month, self.fiscal_year)
                        user_remark = _('Salary {0}{1} - To Payables').format(self.month, self.fiscal_year)
                        self.post_journal_entry(title, user_remark, accounts, 0, tot_earnings, tot_deductions)

                        # To Bank
                        title = _('Salary {0}{1} - To Bank').format(self.month, self.fiscal_year)
                        user_remark = _('Salary {0}{1} - To Bank').format(self.month, self.fiscal_year)
                        self.post_journal_entry(title, user_remark, bank, 1, tot_bank, 0)

                if tot_gis:
                        # GIS
                        title = _('Salary {0}{1} - GIS Remittance').format(self.month, self.fiscal_year)
                        user_remark = _('Salary {0}{1} - GIS Remittance').format(self.month, self.fiscal_year)
                        self.post_journal_entry(title, user_remark, gis, 1, tot_gis, 0)                        

                if tot_pf:
                        # PF
                        title = _('Salary {0}{1} - PF Remittance').format(self.month, self.fiscal_year)
                        user_remark = _('Salary {0}{1} - PF Remittance').format(self.month, self.fiscal_year)
                        self.post_journal_entry(title, user_remark, pf, 1, tot_pf, 0)                        

                if tot_loan:
                        # LOAN
                        title = _('Salary {0}{1} - LOAN Remittance').format(self.month, self.fiscal_year)
                        user_remark = _('Salary {0}{1} - LOAN Remittance').format(self.month, self.fiscal_year)
                        self.post_journal_entry(title, user_remark, loan, 1, tot_loan, 0)                        

                if tot_saving:
                        # SAVINGS
                        title = _('Salary {0}{1} - SAVINGS Remittance').format(self.month, self.fiscal_year)
                        user_remark = _('Salary {0}{1} - SAVINGS Remittance').format(self.month, self.fiscal_year)
                        self.post_journal_entry(title, user_remark, saving, 1, tot_saving, 0)                        

                if (tot_tax or tot_health):
                        # TAX & HEALTH
                        title = _('Salary {0}{1} - TAX & HEALTH Remittance').format(self.month, self.fiscal_year)
                        user_remark = _('Salary {0}{1} - TAX & HEALTH Remittance').format(self.month, self.fiscal_year)
                        self.post_journal_entry(title, user_remark, temp, 1, (tot_tax+tot_health), 0)
                        
        # Ver 20160706.1 added by SSK
        def post_journal_entry(self, title, user_remark, accounts, bank_entry_req, tot_earnings, tot_deductions):
                from frappe.utils import money_in_words
                ss_list = []

                if bank_entry_req == 0:
                        ss = frappe.get_doc({
                                "doctype": "Journal Entry",
                                "voucher_type": 'Journal Entry',
                                "naming_series": 'Journal Voucher',
                                "title": title,
                                "fiscal_year": self.fiscal_year,
                                "user_remark": user_remark,
                                "posting_date": nowdate(),                     
                                "company": self.company,
                                "total_amount_in_words": money_in_words((tot_earnings-tot_deductions)),
                                "accounts": accounts,
				"branch": self.branch
                        })
			ss.flags.ignore_permissions = 1 

                        if (tot_deductions or tot_earnings):
                                ss.insert()
                                #ss.submit()
                        ss_list.append('Direct posting Journal Entry...')
                else:
			default_bank_account = frappe.db.get_value("Branch", self.branch,"expense_bank_account")
			if not default_bank_account:
				frappe.throw("Setup Expense bank Account in Branch " + str(self.branch)) 
			new_accounts = []
			for a in accounts:
				if 'credit_in_account_currency' in a:
					amount = a['credit_in_account_currency']
				else:
					amount = a['debit_in_account_currency']
				new_accounts.append({"account": default_bank_account,
						"credit_in_account_currency": flt(amount),
						"cost_center": str(a['cost_center']),
						"party_check": 0})                        
                       
			for a in new_accounts:
				accounts.append(a)
 
                        ss = frappe.get_doc({
                                "doctype": "Journal Entry",
                                "voucher_type": 'Bank Entry',
                                "naming_series": 'Bank Payment Voucher',
                                "title": title,
                                "fiscal_year": self.fiscal_year,
                                "user_remark": user_remark,
                                "posting_date": nowdate(),                     
                                "company": self.company,
                                "total_amount_in_words": money_in_words((tot_earnings-tot_deductions)),
                                "accounts": accounts,
				"branch": self.branch
                        })
			ss.flags.ignore_permissions = 1 

                        if (tot_deductions or tot_earnings):
                                ss.insert()
                                #ss.submit()
                        ss_list.append('Direct posting Journal Entry...')
                       
        def make_journal_entry1(self, salary_account = None):
		if not self.branch:
			return "<a style='color: red; font-weight: bold; '>Processing Branch is Mandatory!</a>"
                self.get_account_rules()
		return "<a style='color: green; font-weight: bold; '>Salary Journal Entry has been posted to Accounts.</a>"

	def make_journal_entry(self, salary_account = None):
		amount = self.get_total_salary()
		default_bank_account = frappe.db.get_value("Company", self.company,
			"default_bank_account")

		journal_entry = frappe.new_doc('Journal Entry')
		journal_entry.flags.ignore_permissions = 1 
		journal_entry.voucher_type = 'Bank Entry'
		journal_entry.user_remark = _('Payment of salary for the month {0} and year {1}').format(self.month,
			self.fiscal_year)
		journal_entry.fiscal_year = self.fiscal_year
		journal_entry.company = self.company
		journal_entry.posting_date = nowdate()
		journal_entry.set("accounts", [
			{
				"account": salary_account,
				"debit_in_account_currency": amount
			},
			{
				"account": default_bank_account,
				"credit_in_account_currency": amount
			},
		])
		return journal_entry.as_dict()
	
		


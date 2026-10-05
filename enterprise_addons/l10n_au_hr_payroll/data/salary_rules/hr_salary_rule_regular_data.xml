<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Sources
        https://www.ato.gov.au/
        https://oac.chris21.com/OAC_ichrisp/Help/ichrisUG/646250.htm
    -->

    <record id="input_leave_loading_lump" model="hr.salary.rule">
        <field name="name">Leave Loading Lump Sum</field>
        <field name="code">BACKPAY.INPUT</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">leave</field>
        <field name="l10n_au_superannuation_treatment">ote</field>
        <field name="l10n_au_payroll_code">O</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(5, 0, 0)]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <!-- BASIC SALARY, sequence 1 -->
    <record id="l10n_au_hr_payroll_structure_au_regular_basic_salary_rule" model="hr.salary.rule">
        <field name="category_ids" eval="[(5, 0, 0)]"/>
        <field name="name">Basic Salary</field>
        <field name="sequence">1</field>
        <field name="code">BASIC</field>
        <field name="condition_select">none</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = categories['BASIC'] + (sum(payslip.input_line_ids.filtered(lambda x: x.code.startswith('BASIC.CORRECTION')).mapped('amount')) if any(payslip.input_line_ids.filtered(lambda l: l.code.startswith('BASIC.CORRECTION'))) else 0)
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_ote_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_ote')])]"/>
        <field name="name">Ordinary Time Earnings</field>
        <field name="code">OTE</field>
        <field name="sequence">20</field>
        <field name="condition_select">none</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
ote_inputs = payslip.input_line_ids.filtered(lambda i: i.salary_rule_id.l10n_au_superannuation_treatment == 'ote')
ote_worked_day = payslip.worked_days_line_ids.filtered(lambda l: l.work_entry_type_id.l10n_au_is_ote)
result = sum(ote_inputs.mapped('amount')) + sum(ote_worked_day.mapped('amount'))
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="appears_on_payslip">never</field>
        <field name="country_id" ref="base.au"/>
    </record>

    <!-- Extra Pay Rule for inputs -->
    <record id="l10n_au_extra_pay_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_extra_payments')])]"/>  <!-- Change to Extra Pay categ -->
        <field name="name">Additional Payments</field>
        <field name="code">EXTRA</field>
        <field name="sequence">40</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = any(payslip.input_line_ids.filtered(lambda l: l.code.startswith('EXTRA.INPUT')))</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = sum(payslip.input_line_ids.filtered(lambda i: i.code.startswith('EXTRA.INPUT')).mapped('amount'))
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_salary_sacrifice_total_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_salary_sacrifice_total')])]"/>
        <field name="name">Salary Sacrifice Total</field>
        <field name="code">SALARY.SACRIFICE.TOTAL</field>
        <field name="sequence">60</field>
        <field name="condition_select">python</field>
        <field name="condition_python">
sacrifice_other = "SS.O" in inputs and inputs["SS.O"].amount or 0
result = -payslip.l10n_au_salary_sacrifice_other - version.l10n_au_workplace_giving_employer - version.l10n_au_salary_sacrifice_superannuation - sacrifice_other
        </field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
sacrifice_other = "SS.O" in inputs and inputs["SS.O"].amount or 0
result = -payslip.l10n_au_salary_sacrifice_other - version.l10n_au_workplace_giving_employer - version.l10n_au_salary_sacrifice_superannuation - sacrifice_other
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_allowance_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="name">Taxable Allowance Payments</field>
        <field name="sequence">69</field>
        <field name="code">ALW</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = payslip.input_line_ids.filtered(lambda x: x.salary_rule_id.l10n_au_payment_type == 'allowance')</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
taxable_allowances = payslip.input_line_ids.filtered(
    lambda x: x.salary_rule_id.l10n_au_payment_type == "allowance"
        and x.salary_rule_id.l10n_au_paygw_treatment == "regular"
)
# special_tax_free_amount is used in ALW.TAXFREE so the sequence is important
special_taxable_amount, special_tax_free_amount = payslip._l10n_au_compute_special_allowance_amounts()
result = sum(taxable_allowances.mapped('amount')) + special_taxable_amount
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_non_tax_allowance_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="name">Tax Free Allowance Payments</field>
        <field name="sequence">70</field>
        <field name="code">ALW.TAXFREE</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = payslip.input_line_ids.filtered(lambda x: x.salary_rule_id.l10n_au_payment_type == 'allowance')</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
allowances = payslip.input_line_ids.filtered(
    lambda x: x.salary_rule_id.l10n_au_payment_type == "allowance"
    and x.salary_rule_id.l10n_au_paygw_treatment == "no_paygw"
)
# Depends on the ALW Rule for special_tax_free_amount
result = sum(allowances.mapped('amount')) + special_tax_free_amount
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_return_to_work_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_return_to_work')])]"/>
        <field name="name">Return To Work Payment</field>
        <field name="code">RTW</field>
        <field name="sequence">70</field>
        <field name="condition_select">python</field>
        <field name="condition_python">
b2work_type = payslip.env.ref('l10n_au_hr_payroll.input_b2work')
result = payslip.input_line_ids.filtered(lambda l: l.salary_rule_id == b2work_type)
        </field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
b2work_type = payslip.env.ref('l10n_au_hr_payroll.input_b2work')
result = sum(payslip.input_line_ids.filtered(lambda l: l.salary_rule_id == b2work_type).mapped('amount'))
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_back_payments_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.BASIC')])]"/>
        <field name="name">Back Payments</field>
        <field name="code">BACKPAY</field>
        <field name="sequence">70</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = 'BACKPAY.INPUT' in inputs</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = sum(payslip.input_line_ids.filtered(lambda x: x.code == 'BACKPAY.INPUT').mapped('amount'))

        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_salary_sacrifice_other_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_salary_sacrifice')])]"/>
        <field name="name">Salary Sacrifice Other Benefit</field>
        <field name="code">SALARY.SACRIFICE.OTHER</field>
        <field name="sequence">75</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = (-payslip.l10n_au_salary_sacrifice_other - version.l10n_au_workplace_giving_employer) or "SS.O" in inputs</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
sacrifice_other = "SS.O" in inputs and inputs["SS.O"].amount or 0
result = -payslip.l10n_au_salary_sacrifice_other - version.l10n_au_workplace_giving_employer - sacrifice_other
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_workplace_giving_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_workplace_giving')])]"/>
        <field name="name">Workplace Giving</field>
        <field name="code">WORKPLACE.GIVING</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = version.l10n_au_workplace_giving</field>
        <field name="sequence">80</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = -version.l10n_au_workplace_giving
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>
    <record id="l10n_au_fees_and_deductions_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_deductible_expense')])]"/>
        <field name="name">Fees and Deductions</field>
        <field name="code">FEES</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = "DED.UPF" in inputs</field>
        <field name="sequence">80</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = -inputs['DED.UPF'].amount
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <!-- Update Gross to include Salary Sacrifice -->
    <!-- Taxable Salary, Sequence 100 -->
    <record id="l10n_au_hr_payroll_structure_au_regular_gross_salary_rule" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.GROSS')])]"/>
        <field name="name">Taxable Salary</field>
        <field name="sequence">100</field>
        <field name="code">GROSS</field>
        <field name="condition_select">none</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = categories['BASIC'] + categories['ALW'] + categories['SALARY.SACRIFICE.TOTAL'] + categories['WORK.GIVING'] + categories['RTW'] + categories['EXTRA'] - result_rules['ALW.TAXFREE']['total']
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <!-- Sources
        https://www.ato.gov.au/
        https://oac.chris21.com/OAC_ichrisp/Help/ichrisUG/646250.htm
    -->
    <!-- the 3 following rules take advantage of the fact that any variable declared in the compute function
    is added to the global dictionnary. Because we need to separate taxable and non-taxable components of the
    ETP payment, the variables are calculated once but used in different rules.-->
    <record id="l10n_au_termination_etp_gross_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.BASIC')])]"/>
        <field name="name">Gross Termination Payments</field>
        <field name="code">ETP.GROSS</field>
        <field name="sequence">101</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = payslip.l10n_au_termination_type and any(payslip.input_line_ids.filtered(lambda l: l.salary_rule_id.l10n_au_payment_type == 'etp'))</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
etp_withholding, tax_free_component = payslip._l10n_au_compute_termination_withhold(ytd_total)
result = sum(payslip.input_line_ids.filtered(lambda l: l.salary_rule_id.l10n_au_payment_type == 'etp').mapped('amount'))
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_termination_etp_tax_free_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_tax_free_component')])]"/>
        <field name="name">Tax Free Termination Payments</field>
        <field name="code">ETP.TAXFREE</field>
        <field name="sequence">102</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = payslip.l10n_au_termination_type and any(payslip.input_line_ids.filtered(lambda l: l.salary_rule_id.l10n_au_payment_type == 'etp'))</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = tax_free_component
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="appears_on_payslip">never</field>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_termination_etp_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_etp_base')])]"/>
        <field name="name">Taxable Termination Payments</field>
        <field name="code">ETP.TAXABLE</field>
        <field name="sequence">103</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = payslip.l10n_au_termination_type and any(payslip.input_line_ids.filtered(lambda l: l.salary_rule_id.l10n_au_payment_type == 'etp'))</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = sum(payslip.input_line_ids.filtered(lambda l: l.salary_rule_id.l10n_au_payment_type == 'etp').mapped('amount')) - tax_free_component
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="appears_on_payslip">never</field>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_termination_leave_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.BASIC')])]"/>
        <field name="name">Unused Leaves Gross</field>
        <field name="code">ETP.LEAVE.GROSS</field>
        <field name="sequence">105</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = payslip.l10n_au_termination_type</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = (inputs.get("LSL", 0) and inputs.get("LSL").amount) + (inputs.get("AL", 0) and inputs.get("AL").amount)
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_qe_salary_rule" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_qualifying_earnings')])]"/>
        <field name="name">Qualifying Earnings</field>
        <field name="code">QE</field>
        <field name="sequence">107</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = payslip.date_from &gt;= date(2026, 7, 1)</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = categories['OTE'] + sum(payslip.input_line_ids.filtered(lambda l: l.salary_rule_id == payslip.env.ref('l10n_au_hr_payroll.input_bonus_commissions_overtime')).mapped('amount'))
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
        <field name="appears_on_payslip" eval="False"/>
    </record>

    <!-- Schedule 1 - Statement of formulas for calculating amounts to be withheld -->
    <record id="l10n_au_withholding_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_withholding')])]"/>
        <field name="name">Salary Withholding</field>
        <field name="code">WITHHOLD</field>
        <field name="sequence">108</field>
        <field name="condition_select">none</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
coefficients = payslip._l10n_au_tax_schedule_parameters()
if version.l10n_au_tax_treatment_category == 'H' and payslip.company_id.l10n_au_registered_for_whm:
    if isinstance(coefficients, int):
        result_rate = -coefficients
    else:
        for rate in coefficients:
            if rate[0] &lt;= ytd_gross &lt; float(rate[1]):
                result_rate = -rate[3]
                break
    result = categories['GROSS']
elif version.l10n_au_tax_treatment_category in ["W", "H", "V"]:
    gross = categories['GROSS']
    result = -payslip._l10n_au_compute_withholding_amount(categories['GROSS'], version.schedule_pay, coefficients)
else:
    gross = categories['GROSS'] - categories['RTW'] - result_rules['BACKPAY']['total']
    result = -payslip._l10n_au_compute_withholding_amount(gross, version.schedule_pay, coefficients)
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <!-- Schedule 14 withhold -->
    <record id="l10n_au_additional_withholding_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_withholding')])]"/>
        <field name="name">Additional Withholding</field>
        <field name="code">WITHHOLD.ADDITIONAL</field>
        <field name="sequence">108</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = version.l10n_au_additional_withholding_amount</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = -version.l10n_au_additional_withholding_amount
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_withholding_backpay_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_withholding')])]"/>
        <field name="name">Back Payments Withholding</field>
        <field name="code">BACKPAY.WITHHOLD</field>
        <field name="sequence">109</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = 'BACKPAY.INPUT' in inputs</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
net_salary = categories['BASIC'] + categories['ALW'] + categories['DED'] + categories['RTW'] + categories['EXTRA'] - result_rules['BACKPAY']['total']
result, backpay_stsl = payslip._l10n_au_compute_backpay_withhold(net_salary, result_rules['BACKPAY']['total'], WITHHOLD)
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_withholding_extra_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_withholding')])]"/>
        <field name="name">Extra Withholding (53 pays)</field>
        <field name="code">EXTRA.WITHHOLD</field>
        <field name="sequence">109</field>
        <field name="condition_select">python</field>
        <field name="condition_python">
if version.schedule_pay not in ["weekly", "fortnightly"] or not version.l10n_au_extra_pay or not payslip._l10n_au_has_extra_pay():
    result = False
else:
    weekly_min_amount = payslip._rule_parameter("l10n_au_extra_withholding")[version.schedule_pay][0][0]
    weekly_earnings = payslip._l10n_au_compute_weekly_earning(categories['GROSS'], version.schedule_pay)
    result = weekly_earnings &gt; weekly_min_amount
        </field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
weekly_earnings = payslip._l10n_au_compute_weekly_earning(categories['GROSS'], version.schedule_pay)
brackets = payslip._rule_parameter("l10n_au_extra_withholding")[version.schedule_pay]
for bracket in brackets:
    if bracket[0] &lt;= weekly_earnings &lt;= float(bracket[1]):
        result = -bracket[2]
        break
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_withholding_return_to_work_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_withholding')])]"/>
        <field name="name">Return to Work Withholding</field>
        <field name="code">RTW.WITHHOLD</field>
        <field name="sequence">109</field>
        <field name="condition_select">python</field>
        <field name="condition_python">
categories_to_ignore = version.l10n_au_tax_treatment_category in ["W", "V", "H"]
b2work_type = payslip.env.ref('l10n_au_hr_payroll.input_b2work')
b2work = bool(payslip.input_line_ids.filtered(lambda l: l.salary_rule_id == b2work_type))
result = b2work and not categories_to_ignore
        </field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
# Withhold for RTW with Salary Withhold in case of Tax Treatment Category H, W, and V
rates = payslip._rule_parameter("l10n_au_withholding_rtw")
if version.l10n_au_tfn_declaration != "000000000":
    result_rate = -rates['tfn']
else:
    result_rate = -rates["foreign"] if employee.is_non_resident else -rates["resident"]
result = RTW
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_leave_loading_lump_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_withholding')])]"/>
        <field name="name">Leave Loading Withholding</field>
        <field name="code">LEAVE.LOAD</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="sequence">116</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = inputs.get("LEAVE.LOAD") and inputs.get("LEAVE.LOAD").amount</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = compute_leave_loading_withhold(payslip, employee, inputs["LEAVE.LOAD"].amount, version.schedule_pay)
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_loan_withholding_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_withholding')])]"/>
        <field name="name">Withholding for study and training support loans</field>
        <field name="code">WITHHOLD.STUDY</field>
        <field name="sequence">140</field>
        <field name="condition_select">python</field>
        <field name="condition_python">
tax_treatment = version.l10n_au_tax_treatment_category in ['R', 'S', 'F'] and version.l10n_au_medicare_reduction == 'X' and version.l10n_au_employment_basis_code != 'C'
result = version.l10n_au_training_loan and tax_treatment
        </field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
if version.l10n_au_tax_treatment_category in ['R', 'S', 'F'] and version.l10n_au_medicare_reduction == 'X' and version.l10n_au_employment_basis_code != 'C':
    coefficients = payslip._rule_parameter("l10n_au_stsl")["tax-free" if version.l10n_au_tax_free_threshold or employee.is_non_resident else "no-tax-free"]
    gross = categories['GROSS'] - result_rules['BACKPAY']['total']
    result = -payslip._l10n_au_compute_loan_withhold(gross, version.schedule_pay, coefficients)
if "BACKPAY.INPUT" in inputs:
    result += backpay_stsl
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_tax_offset_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_withholding_offsets')])]"/>
        <field name="name">Tax Offsets</field>
        <field name="code">TAX.OFFSET</field>
        <field name="sequence">148</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = version.l10n_au_nat_3093_amount</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
if version.schedule_pay == "weekly":
    result = round(0.019 * version.l10n_au_nat_3093_amount)
elif version.schedule_pay == "bi-weekly":
    result = round(0.038 * version.l10n_au_nat_3093_amount)
elif version.schedule_pay == "monthly":
    result = round(0.083 * version.l10n_au_nat_3093_amount)
elif version.schedule_pay == "quarterly":
    result = round(0.25 * version.l10n_au_nat_3093_amount)
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_medicare_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_withholding_offsets')])]"/>
        <field name="name">Medicare Adjustment</field>
        <field name="code">MEDICARE</field>
        <field name="sequence">156</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = version.l10n_au_medicare_exemption != 'X' or version.l10n_au_tax_free_threshold</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
if version.l10n_au_tax_treatment_category == "S" and version.l10n_au_medicare_exemption != "F":
    rates = payslip._rule_parameter("l10n_au_withholding_schedule_9")
    # Backward compatibility with pre-2024 structure
    if payslip.date_from &lt;= date(2024, 7, 1):
        params = rates["medicare"]
    # Post July 2024
    params = rates["medicare"]["half-exemption"] if version.l10n_au_medicare_exemption == "H" else rates["medicare"]["full"]
else:
    # Schedule 1
    rates = payslip._rule_parameter("l10n_au_withholding_schedule_1")["medicare"]
    if version.l10n_au_medicare_exemption == "H":
        params = rates["half-exemption"]
    elif version.l10n_au_tax_free_threshold:
        params = rates["tax-free"]

if params:
    result = payslip._l10n_au_compute_medicare_adjustment(categories['GROSS'], version.schedule_pay, params)
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="appears_on_payslip">non_zero</field>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_termination_etp_withholding_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_withholding')])]"/>
        <field name="name">Termination Withholding</field>
        <field name="code">ETP.WITHHOLD</field>
        <field name="sequence">160</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = payslip.l10n_au_termination_type and any(payslip.input_line_ids.filtered(lambda l: l.salary_rule_id.l10n_au_payment_type == 'etp'))</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = -etp_withholding
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_termination_leave_withholding_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_withholding')])]"/>
        <field name="name">Unused Leaves Withholding</field>
        <field name="code">ETP.LEAVE.WITHHOLD</field>
        <field name="sequence">162</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = payslip.l10n_au_termination_type</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
leave_withholding = payslip._l10n_au_compute_unused_leaves_withhold()
result = -leave_withholding
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_withholding_net_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_net_withholding')])]"/>
        <field name="name">Total Withholding</field>
        <field name="code">WITHHOLD.TOTAL</field>
        <field name="sequence">164</field>
        <field name="condition_select">none</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = categories['WITHHOLD'] + min(-categories['WITHHOLD'], categories["WITHHOLD.OFFSET"])
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <!-- Attachment of Salary, Sequence 174 -->
    <record id="l10n_au_hr_payroll_structure_au_regular_attachment_of_salary_rule" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.DED')])]"/>
        <field name="name">Attachment of Salary</field>
        <field name="sequence">174</field>
        <field name="code">ATTACH_SALARY</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="condition_select">python</field>
        <field name="condition_python">result = 'ATTACH_SALARY' in inputs</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = -inputs['ATTACH_SALARY'].amount
result_name = inputs['ATTACH_SALARY'].name
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <!-- Assignment of Salary, Sequence 174 -->
    <record id="l10n_au_hr_payroll_structure_au_regular_assignment_of_salary_rule" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.DED')])]"/>
        <field name="name">Assignment of Salary</field>
        <field name="sequence">174</field>
        <field name="code">ASSIG_SALARY</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="condition_select">python</field>
        <field name="condition_python">result = 'ASSIG_SALARY' in inputs</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = -inputs['ASSIG_SALARY'].amount
result_name = inputs['ASSIG_SALARY'].name
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <!-- Child Support (Standard), Sequence 174 -->
    <record id="l10n_au_hr_payroll_structure_au_regular_child_support" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.DED')])]"/>
        <field name="name">Child Support</field>
        <field name="code">CHILD_SUPPORT</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="amount_select">code</field>
        <field name="sequence">174</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = 'CHILD_SUPPORT' in inputs</field>
        <field name="amount_python_compute">
result = -inputs['CHILD_SUPPORT'].amount
result_name = inputs['CHILD_SUPPORT'].name
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_child_support_garnishee_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_child_support_garnishee')])]"/>
        <field name="name">Child Support Garnishee</field>
        <field name="code">CHILD.SUPPORT.GARNISHEE</field>
        <field name="sequence">183</field>
        <field name="condition_select">python</field>
        <field name="condition_python">
result = version.l10n_au_child_support_garnishee_amount or any(payslip.input_line_ids.filtered(lambda l: l.code.startswith('CHILD_SUPPORT_GARNISHEE')))
        </field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
net_salary = categories['BASIC'] + categories['ALW'] + categories['DED'] + categories['RTW'] + categories['EXTRA']
lumpsum_child_support = sum(payslip.input_line_ids.filtered(lambda x: x.code.startswith('CHILD_SUPPORT_GARNISHEE')).mapped("amount"))
net_earnings = net_salary - lumpsum_child_support
lumpsum_child_support += net_earnings * version.l10n_au_child_support_garnishee_amount
result = -round(min(net_salary, lumpsum_child_support), 2)
        </field>
        <field name="appears_on_payslip">never</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_child_support_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_child_support')])]"/>
        <field name="name">Child Support Total</field>
        <field name="code">CHILD.SUPPORT</field>
        <field name="sequence">185</field>
        <field name="condition_select">python</field>
        <field name="condition_python">
result = version.l10n_au_child_support_deduction or version.l10n_au_child_support_garnishee_amount or any(payslip.input_line_ids.filtered(lambda l: l.code.startswith('CHILD_SUPPORT_GARNISHEE')))
        </field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
net_salary = categories['BASIC'] + categories['ALW'] + categories['DED'] + categories['RTW'] + categories['EXTRA']
result = -payslip._l10n_au_compute_child_support(net_salary) + result_rules['CHILD.SUPPORT.GARNISHEE']['total']
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <!-- Post-tax Deduction -->
    <record id="l10n_au_hr_payroll_structure_au_regular_post_tax_deduction" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.DED')])]"/>
        <field name="name">Post-tax Deductions</field>
        <field name="sequence">198</field>
        <field name="code">DED.POST</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">deduction</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = 'DED.POST' in inputs</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = inputs['DED.POST'].amount
result_name = inputs['DED.POST'].name
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <!-- Deduction, Sequence 198 -->
    <record id="l10n_au_hr_payroll_structure_au_regular_deduction_salary_rule" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.DED')])]"/>
        <field name="name">Deduction</field>
        <field name="sequence">198</field>
        <field name="code">DEDUCTION</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="condition_select">python</field>
        <field name="condition_python">result = 'DEDUCTION' in inputs</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = -inputs['DEDUCTION'].amount
result_name = inputs['DEDUCTION'].name
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <!-- Reimbursement, Sequence 199 -->
    <record id="l10n_au_hr_payroll_structure_au_regular_reimbursement_salary_rule" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="name">Reimbursement</field>
        <field name="sequence">199</field>
        <field name="code">REIMBURSEMENT</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="condition_select">python</field>
        <field name="condition_python">result = 'REIMBURSEMENT' in inputs</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = inputs['REIMBURSEMENT'].amount
result_name = inputs['REIMBURSEMENT'].name
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <!-- Include Extra Pay in NET -->
    <!-- Net Salary, Sequence 200 -->
    <record id="l10n_au_hr_payroll_structure_au_regular_net_salary" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.NET')])]"/>
        <field name="name">Net Salary</field>
        <field name="sequence">200</field>
        <field name="code">NET</field>
        <field name="appears_on_employee_cost_dashboard" eval="True"/>
        <field name="condition_select">none</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = categories['BASIC'] + categories['ALW'] + categories['DED'] + categories['RTW'] + categories['EXTRA']
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_salary_sacrifice_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_salary_sacrifice')])]"/>
        <field name="name">Concessional Super Contribution</field>
        <field name="code">SUPER.CONTRIBUTION</field>
        <field name="sequence">220</field>
        <field name="condition_select">python</field>
        <field name="condition_python">
result = version.l10n_au_salary_sacrifice_superannuation or version.l10n_au_extra_negotiated_super \
    or version.l10n_au_extra_compulsory_super or "SS.S" in inputs or "VSC" in inputs
        </field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
sacrifice = "SS.S" in inputs and inputs["SS.S"].amount or 0
sacrifice += "VSC" in inputs and inputs["VSC"].amount or 0
extra_super = categories['OTE'] * (payslip.l10n_au_extra_negotiated_super + payslip.l10n_au_extra_compulsory_super)
result = version.l10n_au_salary_sacrifice_superannuation + extra_super + sacrifice
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_super_contribution_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_super_contribution')])]"/>
        <field name="name">Super Guarantee</field>
        <field name="code">SUPER</field>
        <field name="sequence">230</field>
        <field name="condition_select">none</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
rule = payslip._rule_parameter("l10n_au_withholding_super")
if payslip.date_from &gt;= date(2026, 7, 1):
    prior_slips = payslip._l10n_au_get_year_to_date_slips()
    prior_ote = prior_slips._get_line_values(['QE'], compute_sum=True)['QE']['sum']['total']
    remaining = max(rule['cap'] - prior_ote, 0)
    result = min(categories['QE'], remaining) * rule['rate'] / 100
else:
    result = categories['OTE'] * (rule / 100)
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="l10n_au_reportable_fringe_benefits_structure_1" model="hr.salary.rule">
        <field name="category_ids" eval="[(6, 0, [ref('l10n_au_hr_payroll.rule_category_benefits')])]"/>
        <field name="name">Reportable Fringe Benefits</field>
        <field name="code">RFBA</field>
        <field name="sequence">240</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = any(payslip.input_line_ids.filtered(lambda l: l.code.startswith('FBT')))</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">
result = sum(payslip.input_line_ids.filtered(lambda l: l.salary_rule_id.code.startswith('FBT')).mapped('amount'))
        </field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="country_id" ref="base.au"/>
    </record>


    <record id="input_bonus_commissions" model="hr.salary.rule">
        <field name="name">Bonus/Commissions</field>
        <field name="code">EXTRA.INPUT.bonus_commissions</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_superannuation_treatment">ote</field>
        <field name="l10n_au_paygw_treatment">no_paygw</field>
        <field name="l10n_au_payment_type">other</field>
        <field name="l10n_au_payroll_code">Bonus and Commissions</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_bonus_commissions_overtime" model="hr.salary.rule">
        <field name="name">Bonus/Commissions In Relation to Overtime</field>
        <field name="code">EXTRA.INPUT.bonus_commissions_overtime</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_superannuation_treatment">salary</field>
        <field name="l10n_au_paygw_treatment">no_paygw</field>
        <field name="l10n_au_payment_type">other</field>
        <field name="l10n_au_payroll_code">Overtime</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_gross_director_fee" model="hr.salary.rule">
        <field name="name">Director's Fees</field>
        <field name="code">EXTRA.INPUT.gross_director_fee</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">other</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_superannuation_treatment">ote</field>
        <field name="l10n_au_payroll_code">Directors' fees</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_fees" model="hr.salary.rule">
        <field name="name">Union and professional association fees</field>
        <field name="code">DED.UPF</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">deduction</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_paygw_treatment">no_paygw</field>
        <field name="l10n_au_payroll_code">F</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_early_retirement_scheme" model="hr.salary.rule">
        <field name="name">Early Retirement Scheme</field>
        <field name="code">ETP.ERS</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">etp</field>
        <field name="l10n_au_etp_type">excluded</field>
        <field name="l10n_au_payroll_code">R</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_genuine_redundancy" model="hr.salary.rule">
        <field name="name">Genuine Redundancy</field>
        <field name="code">ETP.GRN</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">etp</field>
        <field name="l10n_au_etp_type">excluded</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_payroll_code">R</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_permanent_disability" model="hr.salary.rule">
        <field name="name">Permanent Disability</field>
        <field name="code">ETP.DIS.permanent_disability</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">etp</field>
        <field name="l10n_au_etp_type">excluded</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_payroll_code">R</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_personal_injury" model="hr.salary.rule">
        <field name="name">Compensation for Personal Injury</field>
        <field name="code">ETP.INJ</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">etp</field>
        <field name="l10n_au_etp_type">excluded</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_payroll_code">R</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_unfair_dismissal" model="hr.salary.rule">
        <field name="name">Compensation for Unfair Dismissal</field>
        <field name="code">ETP.UDS</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">etp</field>
        <field name="l10n_au_etp_type">excluded</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_payroll_code">R</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_harassment" model="hr.salary.rule">
        <field name="name">Compensation for Harassment</field>
        <field name="code">ETP.HRS</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">etp</field>
        <field name="l10n_au_etp_type">excluded</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_payroll_code">R</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_discrimination" model="hr.salary.rule">
        <field name="name">Compensation for Discrimination</field>
        <field name="code">ETP.DIS.discrimination</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">etp</field>
        <field name="l10n_au_etp_type">excluded</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_payroll_code">R</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_lumpsum_death" model="hr.salary.rule">
        <field name="name">Lump Sum Paid on Death of Employee</field>
        <field name="code">ETP.DED</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">etp</field>
        <field name="l10n_au_etp_type">excluded</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_payroll_code">R</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_golden_handshake" model="hr.salary.rule">
        <field name="name">Golden Handshake</field>
        <field name="code">ETP.GLD</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">etp</field>
        <field name="l10n_au_etp_type">non_excluded</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_payroll_code">O</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_non_genuine_redundancy" model="hr.salary.rule">
        <field name="name">Non-Genuine Redundancy</field>
        <field name="code">ETP.NGR</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">etp</field>
        <field name="l10n_au_etp_type">non_excluded</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_payroll_code">O</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_severance_pay" model="hr.salary.rule">
        <field name="name">Severance Pay</field>
        <field name="code">ETP.SEV</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">etp</field>
        <field name="l10n_au_etp_type">non_excluded</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_payroll_code">O</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_severance_pay_genuine" model="hr.salary.rule">
        <field name="name">Genuine Redundancy - Severance Pay</field>
        <field name="code">ETP.SEV.GEN</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">etp</field>
        <field name="l10n_au_etp_type">excluded</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_payroll_code">R</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_gratuity" model="hr.salary.rule">
        <field name="name">Gratuity</field>
        <field name="code">ETP.GRT</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">etp</field>
        <field name="l10n_au_etp_type">non_excluded</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_payroll_code">O</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_in_lieu_of_notice" model="hr.salary.rule">
        <field name="name">Payment in Lieu of Notice</field>
        <field name="code">ETP.ILO</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">etp</field>
        <field name="l10n_au_etp_type">non_excluded</field>
        <field name="l10n_au_superannuation_treatment">ote</field>
        <field name="l10n_au_payroll_code">O</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_in_lieu_of_notice_genuine" model="hr.salary.rule">
        <field name="name">Genuine Redundancy - Payment in Lieu of Notice</field>
        <field name="code">ETP.ILO.GEN</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">etp</field>
        <field name="l10n_au_etp_type">excluded</field>
        <field name="l10n_au_superannuation_treatment">ote</field>
        <field name="l10n_au_payroll_code">R</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_etp_other" model="hr.salary.rule">
        <field name="name">Other ETP</field>
        <field name="code">ETP.OTH</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">etp</field>
        <field name="l10n_au_etp_type">non_excluded</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_payroll_code">O</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_b2work" model="hr.salary.rule">
        <field name="name">Return To Work Payment</field>
        <field name="code">B2WORK</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_superannuation_treatment">ote</field>
        <field name="l10n_au_payroll_code">W</field>
        <field name="l10n_au_payment_type">other</field>
        <field name="l10n_au_paygw_treatment">no_paygw</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_cents_per_kilometer_2" model="hr.salary.rule">
        <field name="name">Cents per Kilometer: Mileage for business purposes</field>
        <field name="code">ALW.CPK.cents_per_kilometer_2</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_paygw_treatment">special</field>
        <field name="l10n_au_payroll_code">CD</field>
        <field name="l10n_au_quantity" eval="True"/>
        <field name="l10n_au_input_uom">kms</field>
        <field name="l10n_au_requires_details" eval="True"/>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_cents_per_kilometer_3" model="hr.salary.rule">
        <field name="name">Cents per Kilometer: Mileage for other vehicles</field>
        <field name="code">ALW.CPK.cents_per_kilometer_3</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">ote</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">OD</field>
        <field name="l10n_au_payroll_code_description">V1</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_cents_per_kilometer_5" model="hr.salary.rule">
        <field name="name">Cents per Kilometer: Mileage for private purposes assessed not to be fully spent</field>
        <field name="code">ALW.CPK.cents_per_kilometer_5</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">ote</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">OD</field>
        <field name="l10n_au_payroll_code_description">ND</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_award_transport_1" model="hr.salary.rule">
        <field name="name">Award Transport: Transport for business purposes traced to historical award</field>
        <field name="code">ALW.AT.award_transport_1</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_paygw_treatment">no_paygw</field>
        <field name="l10n_au_payroll_code">AD</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_award_transport_2" model="hr.salary.rule">
        <field name="name">Award Transport: Transport for business purposes not traced to historical award</field>
        <field name="code">ALW.AT.award_transport_2</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">ote</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">OD</field>
        <field name="l10n_au_payroll_code_description">T1</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_award_transport_3" model="hr.salary.rule">
        <field name="name">Award Transport: Transport for private purposes</field>
        <field name="code">ALW.AT.award_transport_3</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">ote</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">OD</field>
        <field name="l10n_au_payroll_code_description">ND</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_laundry_2" model="hr.salary.rule">
        <field name="name">Laundry: Allowance for approved uniforms</field>
        <field name="code">ALW.LA.laundry_2</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_payroll_code">LD</field>
        <field name="l10n_au_paygw_treatment">special</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_laundry_3" model="hr.salary.rule">
        <field name="name">Laundry: Allowance for the exception for conventional clothing</field>
        <field name="code">ALW.LA.laundry_3</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">ote</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">OD</field>
        <field name="l10n_au_payroll_code_description">G1</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_laundry_4" model="hr.salary.rule">
        <field name="name">Laundry: Allowance for non-approved uniforms or private purposes</field>
        <field name="code">ALW.LA.laundry_4</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">ote</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">OD</field>
        <field name="l10n_au_payroll_code_description">ND</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_call_back" model="hr.salary.rule">
        <field name="name">Call Back: Called back to work overtime after leaving premises</field>
        <field name="code">ALW.CB</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">salary</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">Overtime</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_on_call_1" model="hr.salary.rule">
        <field name="name">On Call: Pre-sacrificed amount for payments outside ordinary hours</field>
        <field name="code">ALW.OC.on_call_1</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">salary</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">Overtime</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_on_call_2" model="hr.salary.rule">
        <field name="name">On Call: Pre-sacrificed amount for payments within ordinary hours</field>
        <field name="code">ALW.OC.on_call_2</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">ote</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">KN</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_domestic_travel_allowance_1" model="hr.salary.rule">
        <field name="name">Domestic Travel Allowance: For meals, accommodation and incidentals when sleeping away for business purposes</field>
        <field name="code">ALW.DTA.domestic_travel_allowance_1</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_payroll_code">RD</field>
        <field name="l10n_au_paygw_treatment">special</field>
        <field name="l10n_au_input_uom">days</field>
        <field name="l10n_au_requires_details" eval="True"/>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_domestic_travel_allowance_2" model="hr.salary.rule">
        <field name="name">Domestic Travel Allowance: For meals, accommodation and incidentals when not sleeping away for business purposes</field>
        <field name="code">ALW.DTA.domestic_travel_allowance_2</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">ote</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">OD</field>
        <field name="l10n_au_payroll_code_description">ND</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_domestic_travel_allowance_4" model="hr.salary.rule">
        <field name="name">Domestic Travel Allowance: For meals, accommodation and incidentals when sleeping away for private purposes</field>
        <field name="code">ALW.DTA.domestic_travel_allowance_4</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">ote</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">OD</field>
        <field name="l10n_au_payroll_code_description">ND</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_overseas_travel_allowance_2" model="hr.salary.rule">
        <field name="name">Overseas Travel Allowance: For meals and incidentals for business purposes</field>
        <field name="code">ALW.OTA.overseas_travel_allowance_2</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_paygw_treatment">special</field>
        <field name="l10n_au_payroll_code">RD</field>
        <field name="l10n_au_input_uom">days</field>
        <field name="l10n_au_requires_details" eval="True"/>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_overseas_travel_allowance_3" model="hr.salary.rule">
        <field name="name">Overseas Travel Allowance: For meals and incidentals for private purposes</field>
        <field name="code">ALW.OTA.overseas_travel_allowance_3</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">ote</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">OD</field>
        <field name="l10n_au_payroll_code_description">ND</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_overseas_accommodation_allowance_1" model="hr.salary.rule">
        <field name="name">Overseas Accommodation Allowance: For business purposes</field>
        <field name="code">ALW.OAA</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">ote</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">OD</field>
        <field name="l10n_au_payroll_code_description">G1</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_work_related_non_expense" model="hr.salary.rule">
        <field name="name">Work-Related Non-Expense: Allowance to compensate for specific work, activities, disabilities, skills or qualifications</field>
        <field name="code">ALW.WNE</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">ote</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">KN</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_qualifications_expense" model="hr.salary.rule">
        <field name="name">Qualifications Expense: To cover the cost of qualifications, insurance, licenses and certifications</field>
        <field name="code">ALW.QE</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">QN</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_uniform_allowance" model="hr.salary.rule">
        <field name="name">Uniform Allowance: For purchase of approved uniforms</field>
        <field name="code">ALW.UA</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">OD</field>
        <field name="l10n_au_payroll_code_description">U1</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_car" model="hr.salary.rule">
        <field name="name">Car: Fixed rates paid to cover transport costs not covered by award transport</field>
        <field name="code">ALW.CAR</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">OD</field>
        <field name="l10n_au_payroll_code_description">V1</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_home_office" model="hr.salary.rule">
        <field name="name">Home Office: Allowance to cover the cost of equipment or connection</field>
        <field name="code">ALW.HO</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">OD</field>
        <field name="l10n_au_payroll_code_description">H1</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_fares" model="hr.salary.rule">
        <field name="name">Fares: Allowance to cover the cost of fares</field>
        <field name="code">ALW.FARE</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">OD</field>
        <field name="l10n_au_payroll_code_description">T1</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_other_deductible" model="hr.salary.rule">
        <field name="name">Other Deductible: Deductible allowances not defined separately elsewhere</field>
        <field name="code">ALW.OTHER</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">OD</field>
        <field name="l10n_au_payroll_code_description">G1</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_overtime_meal_allowance_2" model="hr.salary.rule">
        <field name="name">Overtime Meal Allowance: Overtime</field>
        <field name="code">ALW.OMA</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">allowance</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_payroll_code">MD</field>
        <field name="l10n_au_paygw_treatment">special</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_voluntary_reportable_employer_superannuation_contribution" model="hr.salary.rule">
        <field name="name">Voluntary Reportable Employer Superannuation Contribution</field>
        <field name="code">VSC</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">other</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_paygw_treatment">no_paygw</field>
        <field name="l10n_au_payroll_code">R</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_toil_cashed_out_in_service" model="hr.salary.rule">
        <field name="name">Cashing out time off in lieu (TOIL)</field>
        <field name="code">EXTRA.INPUT.toil_cashed_out_in_service</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">other</field>
        <field name="l10n_au_superannuation_treatment">salary</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">Overtime</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_leaves_cashed_out_in_service" model="hr.salary.rule">
        <field name="name">Cashing out leaves (annual, long service, personal or RDO)</field>
        <field name="code">EXTRA.INPUT.leaves_cashed_out_in_service</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">leave</field>
        <field name="l10n_au_superannuation_treatment">ote</field>
        <field name="l10n_au_paygw_treatment">regular</field>
        <field name="l10n_au_payroll_code">C</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_fringe_benefits_amount" model="hr.salary.rule">
        <field name="name">Fringe Benefits Amount</field>
        <field name="code">FBT.fringe_benefits_amount</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">other</field>
        <field name="l10n_au_payroll_code">T</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_fringe_benefits_exempt_amount" model="hr.salary.rule">
        <field name="name">Fringe Benefits Amount - Exempt</field>
        <field name="code">FBT.fringe_benefits_exempt_amount</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">other</field>
        <field name="l10n_au_payroll_code">X</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_unused_leave_annual" model="hr.salary.rule">
        <field name="name">Unused Annual Leave</field>
        <field name="code">AL</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">other</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_unused_leave_long_service" model="hr.salary.rule">
        <field name="name">Unused Long Service Leave</field>
        <field name="code">LSL</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">other</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_child_support_garnishee_periodic" model="hr.salary.rule">
        <field name="name">Child Support Garnishee: Periodic</field>
        <field name="code">CHILD_SUPPORT_GARNISHEE.child_support_garnishee_periodic</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">deduction</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_payroll_code">G</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_child_support_garnishee_lump_sum" model="hr.salary.rule">
        <field name="name">Child Support Garnishee: Lump Sum</field>
        <field name="code">CHILD_SUPPORT_GARNISHEE.child_support_garnishee_lump_sum</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">deduction</field>
        <field name="l10n_au_superannuation_treatment">not_salary</field>
        <field name="l10n_au_payroll_code">G</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_gross_income_correction_ote" model="hr.salary.rule">
        <field name="name">Pre-sacrificed gross income correction (OTE)</field>
        <field name="code">BASIC.CORRECTION.gross_income_correction_ote</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">other</field>
        <field name="l10n_au_superannuation_treatment">ote</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>

    <record id="input_gross_income_correction_non_ote" model="hr.salary.rule">
        <field name="name">Pre-sacrificed gross income correction (not OTE)</field>
        <field name="code">BASIC.CORRECTION.gross_income_correction_non_ote</field>
        <field name="input_usage_payslip" eval="True"/>
        <field name="l10n_au_payment_type">other</field>
        <field name="l10n_au_superannuation_treatment">salary</field>
        <field name="struct_ids" eval="[(6, 0, [
            ref('l10n_au_hr_payroll.hr_payroll_structure_au_regular'),
        ])]"/>
        <field name="sequence">0</field>
        <field name="appears_on_payslip">never</field>
        <field name="condition_select">python</field>
        <field name="condition_python">result = False</field>
        <field name="amount_select">code</field>
        <field name="amount_python_compute">result = 0</field>
        <field name="category_ids" eval="[(6, 0, [ref('hr_payroll.ALW')])]"/>
        <field name="country_id" ref="base.au"/>
    </record>
</odoo>

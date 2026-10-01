<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <record id="hr_payroll_salary_increase_form_view_inherit_l10n_be_hr_payroll" model="ir.ui.view">
        <field name="name">hr.payroll.salary.increase.view.form.inherit</field>
        <field name="model">hr.payroll.salary.increase</field>
        <field name="inherit_id" ref="hr_payroll.hr_payroll_salary_increase_form_view"/>
        <field name="arch" type="xml">
            <field name="state" invisible="1" position="before">
                <field name="country_code" invisible="1"/>
                <field name="legal_indexation_available" invisible="1"/>
            </field>
            <group name="manual" position="before">
                <group col="2" invisible="country_code != 'BE'">
                    <div class="alert alert-warning mb-0" role="alert" colspan="2"
                         invisible="legal_indexation_available or not employee_ids">
                        <field name="legal_indexation_warning" readonly="1"/>
                    </div>

                    <span class="o_form_label" style="margin-right: 7.2rem !important;">Type</span>
                    <field name="type" widget="radio" nolabel="1" class="o_hr_narrow_field_fit" options="{'horizontal': True}" readonly="not legal_indexation_available"/>
                    <field name="year" invisible="type == 'manual'"/>
                    <field name="rate" widget="percentage" invisible="type == 'manual'"/>
                </group>
            </group>
            <group name="manual" position="attributes">
                <attribute name="invisible">type == 'legal'</attribute>
            </group>
        </field>
    </record>

</odoo>

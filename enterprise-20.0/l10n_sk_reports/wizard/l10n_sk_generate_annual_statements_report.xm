<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data>

        <record id="view_l10n_sk_generate_annual_statements_report" model="ir.ui.view">
            <field name="name">l10n_sk.generate.annual.statements.report</field>
            <field name="model">l10n_sk.generate.annual.statements.report</field>
            <field name="arch" type="xml">
                <form>
                    <group col="3">
                        <field name="type_of_closing"/>
                        <field name="accounting_unit_size"/>
                    </group>
                    <footer>
                        <button name="get_xml" string="Export XML" type="object" class="oe_highlight"/>
                    </footer>
               </form>
            </field>
        </record>

        <record id="action_l10n_sk_generate_annual_statements_report" model="ir.actions.act_window">
            <field name="name">Generate Annual Statements</field>
            <field name="res_model">l10n_sk.generate.annual.statements.report</field>
            <field name="view_mode">form</field>
            <field name="view_id" ref="view_l10n_sk_generate_annual_statements_report"/>
            <field name="target">new</field>
        </record>

    </data>
</odoo>

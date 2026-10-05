<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="res_config_settings_view_form" model="ir.ui.view">
        <field name="name">res.config.settings.view.form.inherit.inter.company.rules</field>
        <field name="model">res.config.settings</field>
        <field name="inherit_id" ref="account_inter_company_rules.res_config_settings_view_form"/>
        <field name="arch" type="xml">
            <xpath expr="//div[@name='module_account_inter_company_rules_company_id']" position="inside">
                <div >
                    <field name="intercompany_generate_sales_orders" class="oe_inline o_light_label"/>
                    <label string="Create Sales Orders" for="intercompany_generate_sales_orders" class="oe_inline o_light_label ps-1 me-0"/>
                    <div class="oi" data-icon="help" title="If another company confirms a Purchase Order with this company, a Sales Order will be created with the chosen warehouse based on the contact address for the delivery of goods."/>
                </div>
                <div>
                    <field name="intercompany_generate_purchase_orders" class="oe_inline o_light_label"/>
                    <label string="Create Purchase Orders" for="intercompany_generate_purchase_orders" class="oe_inline ps-1 me-0 o_light_label"/>
                    <div class="oi" data-icon="help" title="If another company confirms a Sales Order with this company, a Purchase Order will be created with the chosen warehouse based on the contact address for the receipt of goods."/>
                </div>
            </xpath>
        </field>
    </record>
</odoo>

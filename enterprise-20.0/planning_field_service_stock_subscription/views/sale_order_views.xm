<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <record id="fsm_stock_subscription_order_view_form" model="ir.ui.view">
        <field name="name">fsm.stock.subscription.order.form</field>
        <field name="model">sale.order</field>
        <field name="inherit_id" ref="sale_subscription.sale_subscription_order_view_form"/>
        <field name="arch" type="xml">
            <xpath expr="//list/field[@name='analytic_distribution']" position="after">
                <field
                    name="lot_ids"
                    widget="many2many_tags"
                    groups="planning_field_service_stock_subscription.group_field_service_allow_maintenance_contract"
                    readonly="not allow_lot_update"
                    optional="hide"
                    context="{'show_lot_product': True}"
                />
            </xpath>
        </field>
    </record>

</odoo>

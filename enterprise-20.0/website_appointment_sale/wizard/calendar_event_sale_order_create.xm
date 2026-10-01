<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="calendar_event_sale_order_create_view_form" model="ir.ui.view">
        <field name="name">calendar.event.sale.order.create.view.form</field>
        <field name="model">calendar.event.sale.order.create</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <field name="partner_id" options="{'no_create': True}"/>
                        <field name="total_capacity_reserved"/>
                        <field name="calendar_event_id" invisible="1"/> <!--Needed for related field total_capacity_reserved-->
                    </group>
                </sheet>
                <footer>
                    <button string="Create Order" class="btn-primary" type="object" name="action_create_open_sale_order"/>
                    <button class="btn-secondary" special="cancel" data-hotkey="z"/>
                </footer>
            </form>
        </field>
    </record>
</odoo>

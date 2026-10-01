<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <record id="action_planning_vehicle_warehouse" model="ir.actions.act_window">
        <field name="name">Vehicle Warehouses</field>
        <field name="res_model">planning.vehicle.warehouse</field>
        <field name="view_mode">list,kanban,form</field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">
                No vehicle warehouses found. Let’s create one!
            </p>
            <p>
                Assign vehicles to technicians to track stock usage
            </p>
        </field>
    </record>

    <record id="res_config_settings_view_form_inherit_vehicle" model="ir.ui.view">
        <field name="name">res.config.settings.view.form.inherit.vehicle</field>
        <field name="model">res.config.settings</field>
        <field name="inherit_id" ref="planning.res_config_settings_view_form"/>
        <field name="arch" type="xml">
            <xpath expr="//setting[@id='planning_setting_stock_by_vehicle']" position="replace">
                <setting string="Stock by Vehicle"
                         help="Track inventory stored in technicians' vehicles"
                         invisible="not module_planning_field_service">
                    <div class="mt8">
                        <button name="%(action_planning_vehicle_warehouse)d" 
                                type="action" 
                                string="Set up vehicle warehouses" 
                                icon="east" 
                                class="btn-link"/>
                    </div>
                </setting>
            </xpath>
        </field>
    </record>

</odoo>

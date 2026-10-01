<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="action_l10n_eg_nosi_form1_export" model="ir.actions.act_window">
        <field name="name">Egypt NOSI Form 1</field>
        <field name="res_model">l10n.eg.nosi.form1.wizard</field>
        <field name="view_mode">form</field>
        <field name="target">new</field>
        <field name="view_id" ref="l10n_eg_nosi_export_wizard_view_form"/>
    </record>

    <menuitem
        id="menu_l10n_eg_nosi_form1"
        name="Egypt NOSI Form 1"
        parent="hr.hr_menu_l10n_eg"
        action="action_l10n_eg_nosi_form1_export"
        sequence="100"/>
</odoo>

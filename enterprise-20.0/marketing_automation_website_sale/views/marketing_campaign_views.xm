<odoo>
    <record id="marketing_campaign_view_form_trigger" model="ir.ui.view">
        <field name="name">marketing.campaign.view.form.trigger.inherit.website.sale</field>
        <field name="model">marketing.campaign</field>
        <field name="inherit_id" ref="marketing_automation.marketing_campaign_view_form_trigger"/>
        <field name="arch" type="xml">
            <xpath expr="//field[@name='mailing_list_ids']" position="after">
                <field name="product_ids" widget="many2many_tags" invisible="enroll_type != 'action' or enroll_action_type not in ['product_bought', 'product_cart']"/>
            </xpath>
        </field>
    </record>
</odoo>

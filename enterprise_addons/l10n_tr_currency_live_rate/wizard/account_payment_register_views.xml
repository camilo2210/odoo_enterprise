<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="view_account_payment_register_form" model="ir.ui.view">
        <field name="name">account.payment.register.form.inherit.l10n_tr_currency_live_rate</field>
        <field name="model">account.payment.register</field>
        <field name="inherit_id" ref="account.view_account_payment_register_form"/>
        <field name="arch" type="xml">
            <xpath expr="//div[@name='currency_conversion_div']" position="inside">
                <field name="l10n_tr_currency_rate_type" invisible="1"/> <!-- Used only by the toggle button below. -->
                <button type="object"
                        name="l10n_tr_action_toggle_currency_rate_type"
                        icon="sync_alt"
                        icon_class="oi-filled me-1"
                        class="btn btn-link text-dark p-0 ms-2 fw-normal"
                        title="Click to toggle between the Selling and Buying rate"
                        invisible="not can_edit_wizard or not currency_id.l10n_tr_show_buy_rate">
                    <span class="text-muted" invisible="l10n_tr_currency_rate_type != 'sell'">Selling Rate</span>
                    <span class="text-muted" invisible="l10n_tr_currency_rate_type != 'buy'">Buying Rate</span>
                </button>
            </xpath>
        </field>
    </record>
</odoo>

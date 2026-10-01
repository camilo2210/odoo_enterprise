<?xml version="1.0" encoding="utf-8"?>
<odoo>
<template id="appointments_cards" inherit_id="website_appointment_account_payment.appointments_cards">
    <xpath expr="//strong[@t-out='appointment.product_lst_price']" position="replace">
        <t t-set="combination_info" t-value="appointment.product_id.product_tmpl_id._get_combination_info(product_id=appointment.product_id.id)"/>
        <strong t-out="combination_info['price']"
            t-options="{'widget': 'monetary', 'display_currency': combination_info['currency']}"/>
        <span t-if="combination_info['has_discounted_price']" class="oe_striked_price text-muted small text-decoration-line-through text-nowrap"
            t-out="combination_info['list_price']" t-options="{'widget': 'monetary', 'display_currency': combination_info['currency']}"/>
    </xpath>
</template>

<template id="appointment_picture_item" inherit_id="website_appointment_account_payment.appointment_picture_item">
    <xpath expr="//strong[@t-out='appointment.product_lst_price']" position="replace">
        <t t-set="combination_info" t-value="appointment.product_id.product_tmpl_id._get_combination_info(product_id=appointment.product_id.id)"/>
        <strong t-out="combination_info['price']"
            t-options="{'widget': 'monetary', 'display_currency': combination_info['currency']}"/>
    </xpath>
</template>

<template id="appointment_list_item" inherit_id="appointment_account_payment.appointment_list_item">
    <xpath expr="//strong[@t-out='appointment.product_lst_price']" position="replace">
        <t t-set="combination_info" t-value="appointment.product_id.product_tmpl_id._get_combination_info(product_id=appointment.product_id.id)"/>
        <strong t-out="combination_info['price']"
            t-options="{'widget': 'monetary', 'display_currency': combination_info['currency']}"/>
    </xpath>
</template>

<template id="appointment_info" inherit_id="appointment_account_payment.appointment_info">
    <xpath expr="//span[hasclass('o_appointment_details_price')]" position="replace">
        <t t-set="combination_info" t-value="appointment_type.product_id.product_tmpl_id._get_combination_info(
            product_id=appointment_type.product_id.id,
            add_qty=asked_capacity if isDetailsManageCapacity else 1.0)"/>
        <span class="o_appointment_details_price">
            <span t-out="combination_info['price'] * asked_capacity if isDetailsManageCapacity else combination_info['price']"
                t-options="{'widget': 'monetary', 'display_currency': combination_info['currency']}"/>
            <span t-if="not isDetails and combination_info['has_discounted_price']" class="oe_striked_price text-muted small text-decoration-line-through text-nowrap"
                t-out="combination_info['list_price']"
                t-options="{'widget': 'monetary', 'display_currency': combination_info['currency']}"/>
        </span>
    </xpath>
</template>

<template id="appointment_form" inherit_id="appointment_account_payment.appointment_form">
    <xpath expr="//button[@t-if='appointment_type.has_payment_step and appointment_type.product_id.lst_price']/span" position="replace">
        <span t-if="appointment_type._has_accessory_products()">Proceed to Checkout</span>
        <span t-else="">Proceed to Payment</span>
    </xpath>
</template>
</odoo>

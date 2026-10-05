<?xml version="1.0" encoding="UTF-8"?>
<templates id="template" xml:space="preserve">
    <t t-name="pos_avatax.OrderDisplay" t-inherit="point_of_sale.OrderDisplay" t-inherit-mode="extension">
        <xpath expr="//div[@id='order-widget-taxes']" position="inside">
            <span t-if="this.props.isAvataxConfig" type="button" data-bs-toggle="tooltip" data-bs-placement="top" data-bs-title="Avatax Status">
                <span class="text-warning ms-2 cursor-pointer" t-on-click="() => this.refreshAvatax()">
                    <i class="oi" data-icon="refresh" aria-hidden="true"></i>
                </span>
            </span>
        </xpath>
    </t>
</templates>

<?xml version="1.0" encoding="UTF-8"?>

<templates id="template" xml:space="preserve">
    <t t-name="l10n_de_pos_cert.CashMovePopup" t-inherit="point_of_sale.CashMovePopup" t-inherit-mode="extension">
        <xpath expr="//div[hasclass('form-floating')]" position="before">
            <t t-if="this.pos.isCountryGermanyAndFiskaly()">
                <div class="form-floating mt-3 mb-1">
                    <select class="form-select" t-model.proxy="this.state.reason_type">
                        <t t-foreach="this.categoryReasons" t-as="reason" t-key="reason.value">
                            <option t-att-value="reason.value" t-out="reason.label" />
                        </t>
                    </select>
                    <label>Category Reason</label>
                </div>
            </t>
        </xpath>
    </t>
</templates>

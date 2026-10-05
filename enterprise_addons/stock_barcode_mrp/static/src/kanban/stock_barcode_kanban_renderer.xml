<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">

    <t t-name="stock_barcode_mrp.KanbanRenderer" t-inherit-mode="extension" t-inherit="stock_barcode.KanbanRenderer">
        <xpath expr="//div[hasclass('o_barcode_view_info')]/span[1]" position="after">
            <span t-if="this.props.list.resModel === 'mrp.production'" t-out="this.mrpKanbanTip"/>
        </xpath>
    </t>

</templates>

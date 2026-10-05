<?xml version="1.0" encoding="UTF-8"?>
<odoo>
    <data>

        <template id="worksheet_page">
            <div class="page">
                <h1 class="mt-4 mb-4">Maintenance Request: <span t-field="doc.name"/></h1>
                <t name="qc_content">
                    <div t-if="doc.worksheet_template_id">
                            <t t-call="worksheet.worksheet_template_properties_display" props_formatted="doc._get_props_formatted()"/>
                    </div>
                </t>
            </div>
        </template>

        <template id="maintenance_worksheet">
            <t t-call="web.html_container">
                <t t-foreach="docs" t-as="doc">
                    <t t-call="web.external_layout">
                        <t t-call="maintenance_worksheet.worksheet_page"/>
                    </t>
                </t>
            </t>
        </template>

    </data>
</odoo>

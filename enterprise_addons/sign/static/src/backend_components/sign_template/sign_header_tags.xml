<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
    <t t-name="sign.SignHeaderTags">
        <Record t-props="this.recordProps" t-slot-scope="data">
            <t t-set="record" t-value="data.record"/>
            <div t-attf-class="o_sign_template_tags_and_save d-flex align-items-center gap-2">
                <span class="text-nowrap">Tags</span>
                <div class="o_field_widget o_field_many2many_tags w-100">
                    <Many2ManyTagsField t-props="this.getMany2ManyProps(record, this.fieldName)" colorField="'color'"/>
                </div>
            </div>
        </Record>
    </t>
</templates>

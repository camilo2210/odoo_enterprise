<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">

    <t t-name="planning.PlanningEmployeeAvatar" t-inherit="mail.Avatar">
        <xpath expr="//span[@t-out='this.props.displayName']" position="attributes">
            <attribute name="t-ref">this.displayNameRef</attribute>
        </xpath>
        <xpath expr="//div[hasclass('o-mail-Avatar')]" position="attributes">
            <attribute name="t-attf-class" add="{{ this.planningProps.showPopover ? 'o_field_many2one_avatar' : '' }}" separator=" "/>
        </xpath>
        <xpath expr="//div[hasclass('o-mail-Avatar')]/img" position="attributes">
            <attribute name="t-on-click.stop.prevent">this.openCard</attribute>
            <attribute name="t-if">!this.planningProps.isResourceMaterial</attribute>
            <attribute name="t-att-data-tooltip">this.props.displayName</attribute>
        </xpath>
        <xpath expr="//div[hasclass('o-mail-Avatar')]/img" position="after">
            <t t-if="this.planningProps.isResourceMaterial">
                <div t-attf-class="o_colorlist_item_color_{{ this.planningProps.resourceColor }} o_material_resource d-inline-flex flex-shrink-0 align-items-center justify-content-center me-1 rounded bg-200"
                     t-on-click.stop.prevent="this.openCard">
                    <i class="oi" data-icon="build"/>
                </div>
            </t>
        </xpath>
    </t>

</templates>

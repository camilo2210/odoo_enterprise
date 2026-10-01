<?xml version="1.0" encoding="UTF-8"?>
<templates>
    <t t-name="documents.DocumentsActivityController" t-inherit="mail.ActivityController" t-inherit-mode="primary">
        <xpath expr="//div" position="attributes">
            <attribute name="t-ref">this.rootRef</attribute>
        </xpath>
        <xpath expr="//CogMenu" position="replace"/>
        <xpath expr="//SearchBar" position="before">
            <div t-if="this.model?.root?.selection?.length" class="o_selection_container d-flex gap-1 w-100 w-md-auto">
                <SelectionBox root="this.model.root"/>
                <t t-if="this.props.info.actionMenus">
                    <ActionMenus t-if="this.showActions" t-props="this.actionMenuProps"/>
                </t>
            </div>
        </xpath>
        <xpath expr="//SearchBar" position="attributes">
            <attribute name="toggler">this.searchBarToggler</attribute>
            <attribute name="t-if" add="!this.model?.root?.selection?.length" separator="and"/>
        </xpath>
    </t>
</templates>

<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">

    <t t-name="documents.DocumentsSearchPanelActions">
        <div t-ref="this.containerRef">
            <t t-set="currentGroup" t-value=""/>
            <t t-foreach="this.items" t-as="item" t-key="item.key">
                <t t-if="currentGroup !== null and currentGroup !== item.groupNumber">
                    <div role="separator" class="dropdown-divider"/>
                </t>

                <t t-if="item.Component" t-component="item.Component" t-props="this.itemProps"/>

                <DropdownItem t-else="" class="item.class ? item.class + ' o_menu_item' : 'o_menu_item'" onSelected="() => this.onItemSelected(item)">
                    <i t-if="item.icon" class="oi oi-fw me-1" t-att-class="item.iconClass" t-att-data-icon="item.icon"/>
                    <t t-out="item.description"/>
                </DropdownItem>

                <t t-set="currentGroup" t-value="item.groupNumber"/>
            </t>
        </div>
    </t>

</templates>

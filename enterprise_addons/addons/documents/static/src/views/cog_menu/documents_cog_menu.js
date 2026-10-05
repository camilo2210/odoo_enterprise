import { CogMenu } from "@web/search/cog_menu/cog_menu";
import { documentsCogMenuPinAction } from "./documents_cog_menu_pin_actions";
import { documentsCogMenuItemAutomations } from "./documents_cog_menu_item_automations";

const documentMenuItems = [documentsCogMenuPinAction, documentsCogMenuItemAutomations];

export class DocumentsCogMenu extends CogMenu {
    async _registryItems() {
        const documentItemsPromise = documentMenuItems.map(async (item) =>
            (await this.scope.run(() => item.isDisplayed(this.env)))
                ? formatRegistryItem(item)
                : false
        );
        const [enabledItems, items] = await Promise.all([
            super._registryItems(),
            Promise.all(documentItemsPromise),
        ]);
        return enabledItems.concat(items.filter(Boolean));
    }
}

function formatRegistryItem(item) {
    return {
        Component: item.Component,
        groupNumber: item.groupNumber,
        key: item.Component.name,
    };
}

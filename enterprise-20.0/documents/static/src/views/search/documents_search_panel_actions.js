import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { useNavigation } from "@web/core/navigation/navigation";
import { folderActions } from "@documents/views/action/folder_actions";
import { STATIC_COG_GROUP_ACTION_PIN } from "@documents/views/cog_menu/documents_cog_menu_group";

import { Component, onWillStart, proxy, signal, t, useProps, useScope } from "@odoo/owl";

export class DocumentsSearchPanelActions extends Component {
    static template = "documents.DocumentsSearchPanelActions";
    static components = {
        Dropdown,
        DropdownItem,
    };

    props = useProps({
        folder: t.object(),
        env: t.object().optional(),
        close: t.function().optional(),
    });

    containerRef = signal.ref();

    scope = useScope();

    setup() {
        this.state = proxy({ enabledItems: [] });
        this.env = this.props.env || this.env;
        useNavigation(this.containerRef);
        onWillStart(async () => {
            this.state.enabledItems = await this._registryItems();
        });
    }

    async _registryItems() {
        const enabledItems = [];
        for (const item of folderActions) {
            if (item.groupNumber === STATIC_COG_GROUP_ACTION_PIN) {
                continue;
            }
            const isDisplayed = await this.scope.run(() =>
                item.isDisplayed(this.env, this.props.folder)
            );
            if (isDisplayed) {
                enabledItems.push({
                    Component: item.Component,
                    groupNumber: item.groupNumber,
                    key: item.Component.name,
                });
            }
        }
        return enabledItems;
    }

    get items() {
        return this.state.enabledItems.sort(
            (item1, item2) => (item1.groupNumber || 0) - (item2.groupNumber || 0)
        );
    }

    get itemProps() {
        return { folder: this.props.folder, env: this.env, close: this.props.close };
    }
}

import { DocumentsAction } from "@documents/views/action/documents_action";
import { computed, signal, t, useProps } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { useDropdownNesting } from "@web/core/dropdown/_behaviours/dropdown_nesting";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { useNavigation } from "@web/core/navigation/navigation";
import { ActionMenus } from "@web/search/action_menus/action_menus";
import { STATIC_COG_GROUP_ACTION_PIN } from "../cog_menu/documents_cog_menu_group";

class ActionMenusFlat extends ActionMenus {
    static template = "documents.ActionMenusFlat";
}

export class DocumentsActionPopover extends DocumentsAction {
    static template = "documents.DocumentsActionPopover";
    static components = {
        ActionMenusFlat,
        Dropdown,
        DropdownItem,
    };

    popoverProps = useProps({
        close: t.function(),
    });

    containerRef = signal.ref();

    mainActions = computed(() =>
        this.topBarActions().filter((action) => action.groupNumber !== STATIC_COG_GROUP_ACTION_PIN)
    );

    pinActions = computed(() =>
        this.topBarActions().filter((action) => action.groupNumber === STATIC_COG_GROUP_ACTION_PIN)
    );

    setup() {
        super.setup();
        useNavigation(this.containerRef, {
            shouldFocusFirstItem: true,
            isNavigationAvailable: () => true,
        });
        useDropdownNesting(useDropdownState({ onClose: () => this.popoverProps.close() }));
    }

    onItemSelected(action) {
        action.callback();
        this.popoverProps.close();
    }
}

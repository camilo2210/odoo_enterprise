import { Component, computed, t, useProps } from "@odoo/owl";
import { SIZES } from "@web/core/ui/ui_utils";
import { useService } from "@web/core/utils/hooks";
import { ActionMenus } from "@web/search/action_menus/action_menus";

export class DocumentsAction extends Component {
    static template = "documents.DocumentsAction";
    static components = {
        ActionMenus,
    };

    props = useProps({
        targetRecords: t.array(t.object()),
        folderId: t.or([t.string(), t.number(), t.literal(false)]),
        isPreview: t.boolean().optional(),
    });

    actionMenuProps = computed(() => {
        const selectionActions = this.documentService.getSelectionActions();
        if (!selectionActions || !this.props.isPreview) {
            return null;
        }
        const props = selectionActions.getMenuProps();
        props.items.action = props.items.action.filter(this.isPreviewAction.bind(this));
        return props;
    });
    topBarActions = computed(() => {
        const selectionActions = this.documentService.getSelectionActions();
        if (!selectionActions) {
            return [];
        }
        const actions = selectionActions.getTopBarActions();
        const values =
            this.props.folderId === "TRASH" && actions.download
                ? [actions.download]
                : Object.values(actions);
        return values
            .filter((action) => action.isAvailable?.() ?? true)
            .sort((a, b) => a.groupNumber - b.groupNumber || (a.sequence || 0) - (b.sequence || 0));
    });

    visibleTopbarActions = computed(() => (this.uiService.size >= SIZES.XL ? 3 : 2));

    setup() {
        this.documentService = useService("document.document");
        this.uiService = useService("ui");
    }

    isPreviewAction(action) {
        return action.key !== "export";
    }
}

import { patch } from "@web/core/utils/patch";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { _t } from "@web/core/l10n/translation";
import { useInsertInSpreadsheet } from "../view_hook";
import { session } from "@web/session";

export const patchKanbanControllerExportSelection = {
    setup() {
        super.setup();
        this.canInsertInSpreadsheet = session.can_insert_in_spreadsheet;
        this.insertInSpreadsheet = useInsertInSpreadsheet(this.env, () =>
            this.getExportableFields()
        );
    },

    getStaticActionMenuItems() {
        const menuItems = super.getStaticActionMenuItems(...arguments);
        menuItems["insert"] = {
            isAvailable: () => this.canInsertInSpreadsheet,
            sequence: 15,
            icon: "view_list",
            description: _t("Spreadsheet"),
            callback: () => this.insertInSpreadsheet(),
        };
        return menuItems;
    },
};

export const unpatchKanbanControllerExportSelection = patch(
    KanbanController.prototype,
    patchKanbanControllerExportSelection
);

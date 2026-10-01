import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";
import { _t } from "@web/core/l10n/translation";
import { session } from "@web/session";
import { useInsertInSpreadsheet } from "../view_hook";

patch(ListController.prototype, {
    setup() {
        super.setup();
        this.canInsertInSpreadsheet = session.can_insert_in_spreadsheet;
        this.insertInSpreadsheet = useInsertInSpreadsheet(this.env, () =>
            this.getExportableFields().filter((f) => {
                const fieldNode = Object.values(this.archInfo.fieldNodes).find(
                    (fN) => fN.name === f.name
                );
                return fieldNode?.widget !== "handle";
            })
        );
    },

    getStaticActionMenuItems() {
        const menuItems = super.getStaticActionMenuItems(...arguments);
        menuItems["insert"] = {
            isAvailable: () => this.canInsertInSpreadsheet,
            sequence: 15,
            icon: "view_list",
            description: _t("Insert in spreadsheet"),
            callback: () => this.insertInSpreadsheet(),
        };
        return menuItems;
    },
});

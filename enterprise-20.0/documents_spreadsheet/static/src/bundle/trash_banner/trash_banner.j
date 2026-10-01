import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";
import { components } from "@odoo/o-spreadsheet";

patch(components.TopBar.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.uiService = useService("ui");
        this.state.deletion_delay = null;

        onWillStart(async () => {
            if (this.env.isArchived && this.env.isArchived()) {
                this.state.deletion_delay = await this.orm.call(
                    "documents.document",
                    "get_deletion_delay",
                    [[]]
                );
            }
        });
    },

    get trashDescription() {
        const deletionMessage = _t(
            "This file will be deleted forever in %(deletion_delay)s days. You can still download it.",
            { deletion_delay: this.state.deletion_delay }
        );

        if (this.env.hasWriteAccess()) {
            return deletionMessage + " " + _t("To access this file, take it out of the trash.");
        }
        return (
            deletionMessage +
            " " +
            _t("To access this file, contact the owner to take it out of the trash.")
        );
    },
});

import { Thread } from "@mail/core/common/thread_model";
import { patch } from "@web/core/utils/patch";

patch(Thread.prototype, {
    /** @override */
    open() {
        if (this.model !== "spreadsheet.cell.thread") {
            return super.open(...arguments);
        }
        this.store.env.services.orm
            .call("spreadsheet.cell.thread", "get_spreadsheet_access_action", [this.id])
            .then((action) => this.store.env.services.action.doAction(action));
        return true;
    },
});

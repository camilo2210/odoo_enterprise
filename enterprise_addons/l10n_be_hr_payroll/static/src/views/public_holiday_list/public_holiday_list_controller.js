import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";

export class PublicHolidayListController extends ListController {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.orm = useService("orm");
    }

    async onRecordSaved(record) {
        await super.onRecordSaved(record);
        const action = await this.orm.call(
            "resource.calendar.leaves",
            "action_open_multi_allocations_wizard",
            [record.resId],
        );
        if (action) {
            await this.actionService.doAction(action);
        }
    }
}

registry.category("views").add("l10n_be_public_holiday_list", {
    ...listView,
    Controller: PublicHolidayListController,
});

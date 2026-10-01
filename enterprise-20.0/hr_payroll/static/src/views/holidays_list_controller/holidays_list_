import { patch } from "@web/core/utils/patch";
import { HolidaysListController } from "@hr_holidays/views/list/holidays_list_controller";
patch(HolidaysListController.prototype, {
    get actionFilters() {

        return {
            ...super.actionFilters,
            action_adjust_corresponding_payslip: (record) => true,
        };
    },
});
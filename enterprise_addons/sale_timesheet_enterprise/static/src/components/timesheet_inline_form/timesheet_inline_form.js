import { patch } from "@web/core/utils/patch";
import { TimesheetInlineForm } from "@timesheet_grid/components/timesheet_inline_form/timesheet_inline_form";
import { user } from "@web/core/user";

patch(TimesheetInlineForm.prototype, {
    async onWillStart() {
        this.isSalesman = await user.hasGroup("sales_team.group_sale_salesman");
        await super.onWillStart();
    },

    get fieldNames() {
        const res = [
            ...super.fieldNames,
            "allow_billable",
            "so_line",
            ...(this.isSalesman ? ["is_billable", "has_available_so"] : []),
        ];

        return res;
    },

    displayIsBillable(record) {
        return this.isSalesman && record.data.has_available_so;
    },
});

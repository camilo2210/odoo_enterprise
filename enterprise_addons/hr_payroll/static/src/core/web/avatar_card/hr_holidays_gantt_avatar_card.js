import { HrHolidaysGanttAvatarCard } from "@hr_holidays_gantt/core/web/avatar_card/hr_holidays_gantt_avatar_card";
import { patch } from "@web/core/utils/patch";
import { formatMonetary } from "@web/views/fields/formatters";
import { onWillStart, proxy } from "@odoo/owl";

patch(HrHolidaysGanttAvatarCard.prototype, {
    setup() {
        super.setup(...arguments);
        this.state = proxy({
            benefits: [],
        });
        onWillStart(async () => {
            await this._loadPayrollCardData();
        });
    },
    async _loadPayrollCardData() {
        const employeeId = this.props.id;
        // in hr.payslip list view, the versionId is passed to the avatar
        // card to get the benefits for that specific payslip version
        const versionId = this.payrollProps?.versionId;
        const [benefitsData] = await Promise.all([
            employeeId
                ? this.orm.call("hr.employee", "get_benefit_fields_value", [employeeId, versionId])
                : Promise.resolve([]),
        ]);
        const filteredBenefits = benefitsData
            .filter((benefit) => benefit.value && typeof benefit.value === "number")
            .map((benefit) => {
                const formattedValue = benefit.currency
                    ? formatMonetary(benefit.value, { currencyId: benefit.currency })
                    : benefit.value;
                return {
                    id: benefit.id,
                    name: benefit.name,
                    value: formattedValue,
                };
            });
        this.state.benefits = filteredBenefits;
    },
});

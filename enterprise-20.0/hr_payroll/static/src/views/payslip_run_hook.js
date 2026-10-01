import { useService } from "@web/core/utils/hooks";
import { serializeDate } from "@web/core/l10n/dates";

export function useOpenPayRun() {
    const actionService = useService("action");
    const ormService = useService("orm");
    return async ({
        id = null,
        date_start = null,
        date_end = null,
        structure_id = null,
    }) => {
        if (id) {
            const action = await ormService.call("hr.payslip.run", "action_open_payslips", [[id]]);
            return actionService.doAction(action);
        }
        return actionService.doAction("hr_payroll.action_hr_payslip_run_create", {
            additionalContext: {
                ...(date_start ? { default_date_start: serializeDate(date_start) } : {}),
                ...(date_end ? { default_date_end: serializeDate(date_end) } : {}),
                ...(structure_id ? { default_structure_id: structure_id } : {}),
            },
        });
    };
}

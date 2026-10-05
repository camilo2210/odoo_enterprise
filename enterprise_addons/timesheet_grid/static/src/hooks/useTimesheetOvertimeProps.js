import { computed, useProps } from "@odoo/owl";
import { useEnv } from "@web/owl2/utils";

/**
 * Hook to get the props for the timesheet overtime component use in the
 * timesheet_many2one and timesheet_avatar_many2one components.
 * (assume the hook is used in many2one grid component)
 *
 * @param {import("@odoo/owl").ReactiveValue<string>} resId
 */
export function useTimesheetOvertimeProps(resId) {
    const env = useEnv();
    const props = useProps();
    return computed(() => {
        const id = resId();
        const showTargetLeft = env.searchModel?.context?.show_target_left;
        if (showTargetLeft && props.targetLimitsSet) {
            if (props.targetLeft && id && id in props.targetLeft) {
                return props.targetLeft[id];
            }
        } else if (id && props.workingHours && id in props.workingHours) {
            return props.workingHours[id];
        }
        return {};
    });
}

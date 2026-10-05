import { patch } from "@web/core/utils/patch";
import { formatNumber } from "@hr_holidays/views/hooks";
import { user } from "@web/core/user";
import { LeaveStatsComponent } from "@hr_holidays/leave_stats/leave_stats";

// The 3 BE hours-tracked types can have an exact hour balance that disagrees with the rounded
// day count shown here -- l10n_be_hours_remaining is only present on rawAllocationData (from
// get_allocation_data_request, stashed there by core) when that's actually the case.
patch(LeaveStatsComponent.prototype, {
    async loadLeaves(employee) {
        await super.loadLeaves(employee);
        for (const leave of this.state.leaves) {
            const hoursRemaining = this.state.rawAllocationData[leave.data.id]?.l10n_be_hours_remaining;
            if (hoursRemaining !== undefined) {
                leave.l10n_be_hoursRemaining = formatNumber(user.lang, hoursRemaining);
            }
        }
    },
});

import { Component, onWillStart, t, useProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

import { Many2OneAvatarRankField } from "@sale_timesheet_enterprise/components/many2one_avatar_rank_field/many2one_avatar_rank_field";
import { TimesheetLeaderboardDialog } from "@sale_timesheet_enterprise/views/timesheet_leaderboard_dialog/timesheet_leaderboard_dialog";

export class TimesheetLeaderboard extends Component {
    static template = "sale_timesheet_enterprise.TimesheetLeaderboard";
    static components = {
        Many2OneAvatarRankField,
    };

    props = useProps({
        date: t.object(),
        displayEarnYourRank: t.boolean(),
    });

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.uiService = useService("ui");
        this.timesheetLeaderboardService = useService("timesheet_leaderboard");
        onWillStart(async () => {
            await this.timesheetLeaderboardService.getLeaderboardData({
                periodStart: this.props.date,
            });
        });
    }

    openLeaderboardPopup() {
        this.dialog.add(TimesheetLeaderboardDialog, {
            date: this.props.date,
        });
    }

    get avatarDisplayLimit() {
        return 3;
    }
}

import { Component, onWillStart, useProps, t } from "@odoo/owl";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { formatPercentage } from "@web/views/fields/formatters";

import { TimesheetLeaderboard } from "@sale_timesheet_enterprise/components/timesheet_leaderboard/timesheet_leaderboard";

import { TimesheetKpi } from "../timesheet_kpi/timesheet_kpi";

const { DateTime } = luxon;
const defaultDate = DateTime.local();

export class TimesheetKpiLeaderboardHeader extends Component {
    static template = "sale_timesheet_enterprise.TimesheetKpiLeaderboardHeader";
    static components = { TimesheetKpi, TimesheetLeaderboard };
    props = useProps({
        date: t.object().optional(defaultDate),
    });

    setup() {
        this.actionService = useService("action");
        this.timesheetUOMService = useService("timesheet_uom");
        this.timesheetKpiService = useService("timesheet_kpi");
        this.timesheetLeaderboardService = useService("timesheet_leaderboard");
        this.uiService = useService("ui");
        onWillStart(this.onWillStart);
    }

    async _fetchServiceData() {
        return Promise.all([
            this.timesheetKpiService.getKpiData({
                periodStart: this.props.date,
                kwargs: { context: user.context },
            }),
            this.timesheetLeaderboardService.getLeaderboardData({
                periodStart: this.props.date,
                kwargs: { context: user.context },
            }),
        ]);
    }

    async onWillStart() {
        const groupProm = user
            .hasGroup("timesheet_grid.group_timesheet_assistant")
            .then((result) => (this.isAssistantEnabled = result));
        return Promise.all([this._fetchServiceData(), groupProm]);
    }

    toggleBillableTimesheetsSearch() {
        const searchItem = Object.values(this.env.searchModel.searchItems).find(
            (i) => i.name === "billable"
        );
        this.env.searchModel.toggleSearchItem(searchItem.id);
    }

    _formatValue(value) {
        value = Math.round(value);
        return this.timesheetUOMService
            .formatter(value, {
                numeric: true,
                noLeadingZeroHour: true,
                showSeconds: false,
                digits: [false, 0],
            })
            .replace(/(:00|\.00)/g, "");
    }

    get workedTime() {
        return this._formatValue(this.timesheetKpiService.data.worked_time);
    }

    get billableTime() {
        return this._formatValue(this.timesheetKpiService.data.billable_time);
    }

    get billableTimeTarget() {
        return this._formatValue(this.timesheetKpiService.data.billable_time_target);
    }

    get billingRate() {
        return this.timesheetKpiService.data.billing_rate;
    }

    get workedTimeKpiProps() {
        const uom = this.timesheetKpiService.data.uom;
        const month = this.props.date.monthLong;
        return {
            name: "worked_time_kpi",
            value: this.workedTime,
            label: _t("%(uom)s worked", { uom }),
            title: _t("%(uom)s worked in %(month)s", { uom, month }),
        };
    }

    get billableTimeKpiProps() {
        const uom = this.timesheetKpiService.data.uom;
        const month = this.props.date.monthLong;
        return {
            name: "billable_time_kpi",
            value: this.billableTime,
            target: this.timesheetKpiService.showIndicators ? this.billableTimeTarget : undefined,
            label: _t("%(uom)s billable", { uom }),
            title: _t("%(uom)s billable in %(month)s\nClick to filter", { uom, month }),
            extraClass: "btn o_show_billable_timesheets_button border-0 p-0",
            onClick: this.toggleBillableTimesheetsSearch.bind(this),
        };
    }

    get billingRateKpiProps() {
        const uom = this.timesheetKpiService.data.uom.toLowerCase();
        const month = this.props.date.monthLong;
        const billableTime = this.billableTime;
        const billableTimeTarget = this.billableTimeTarget;
        return {
            name: "billing_rate_kpi",
            value: formatPercentage(this.billingRate, { digits: [false, 0] }),
            label: _t("Billing rate"),
            title: _t(
                "Billing rate in %(month)s (%(billableTime)s / %(billableTimeTarget)s %(uom)s billable)",
                {
                    month,
                    billableTime,
                    billableTimeTarget,
                    uom,
                }
            ),
            valueExtraClass:
                this.timesheetKpiService.data.billing_rate >= 1.0 ? "text-success" : "text-danger",
        };
    }

    get showAssistantButton() {
        return (
            !this.uiService.isSmall &&
            this.timesheetUOMService.timesheetWidget === "float_time" &&
            this.isAssistantEnabled
        );
    }
}

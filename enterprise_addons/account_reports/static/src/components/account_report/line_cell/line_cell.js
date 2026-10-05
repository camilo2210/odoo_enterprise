import { localization } from "@web/core/l10n/localization";

import { registry } from "@web/core/registry";
import { ORM } from "@web/core/orm_plugin";
import { PopoverPlugin } from "@web/core/popover/popover_plugin";
import { ActionPlugin } from "@web/webclient/actions/action_plugin";

import { Component, computed, markup, signal, t, useEffect, usePlugin, useProps } from "@odoo/owl";

import { AccountReportCarryoverPopover } from "@account_reports/components/account_report/line_cell/popover/carryover_popover";
import { AccountReportController } from "@account_reports/components/account_report/controller";


export class AccountReportLineCell extends Component {
    static template = "account_reports.AccountReportLineCell";
    props = useProps({
        line: t.object().optional(),
        cell: t.object(),
        cellIndex: t.number(),
    });

    action = usePlugin(ActionPlugin);
    controller = usePlugin(AccountReportController);
    popover = usePlugin(PopoverPlugin);
    orm = usePlugin(ORM);

    noFormatSign = computed(() => {
        const sign = Math.sign(this.props.cell.no_format?.());
        // Slight optimization to prevent invalidating getCellClasses when the switch branch wont change afterward.
        if (isNaN(sign)) return 1;
        if (Object.is(sign, -0)) return 0;
        return sign;
    });
    hasCellLabel = computed(() => Boolean(this.props.cell.cell_label?.()));
    hasInfoPopupData = computed(() => Boolean(this.props.cell.info_popup_data?.()));

    cellRef = signal.ref();
    cellClasses = "";

    setup() {
        useEffect(() => {
            const classes = this.getCellClasses();
            if (classes === this.cellClasses) return;

            const prevCellClasses = this.cellClasses;
            this.cellClasses = classes;
            const prev = prevCellClasses ? prevCellClasses.trim().split(/\s+/).filter(Boolean) : [];
            const next = classes ? classes.trim().split(/\s+/).filter(Boolean) : [];
            this.controller.scheduleClassUpdate(this.cellRef, prev, next);
        });
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Attributes
    // -----------------------------------------------------------------------------------------------------------------
    getCellClasses() {
        switch (this.props.cell.comparison_mode?.()) {
            case "green":
                return "text-end text-success";
            case "muted":
                return "text-end muted";
            case "red":
                return "text-end text-danger";
        }

        let classes = "";
        if (this.props.cell.auditable?.()) {
            classes += " auditable";
        }

        const css_class = this.props.cell.css_class?.();
        switch(this.props.cell.figure_type()) {
            case "date":
                classes += " date";
                break;
            case "string":
                classes += " text";
                break;
            case "float":
            case "integer":
            case "monetary":
            case "percentage":
                classes += " numeric";

                if (!css_class)
                    switch (this.noFormatSign()) {
                        case 1:
                            break;
                        case 0:
                            classes += " muted";
                            break;
                        case -1:
                            classes += " text-danger";
                            break;
                    }
                break;
        }

        if (this.props.cellIndex % 2) {
            classes += " line_cell_odd";
        }

        if (css_class) {
            classes += ` ${css_class}`;
        }

        return classes;
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Audit
    // -----------------------------------------------------------------------------------------------------------------
    async audit() {
        const auditAction = await this.orm.call(
            "account.report",
            "dispatch_report_action",
            [
                this.controller.options().report_id,
                this.controller.options(),
                "action_audit_cell",
                {
                    report_line_id: this.props.cell.report_line_id?.(),
                    expression_label: this.props.cell.expression_label(),
                    calling_line_dict_id: this.props.line.id(),
                    column_group_index: this.props.cell.column_group_index(),
                },
            ],
            {
                context: this.controller.context,
            }
        );
        if (auditAction.help) {
            auditAction.help = markup(auditAction.help);
        }

        return this.action.doAction(auditAction);
    }

    //------------------------------------------------------------------------------------------------------------------
    // Carryover popover
    //------------------------------------------------------------------------------------------------------------------
    carryoverPopover(ev) {
        if (this.popoverCloseFn) {
            this.popoverCloseFn();
            this.popoverCloseFn = null;
        }

        this.popoverCloseFn = this.popover.add(
            ev.currentTarget,
            AccountReportCarryoverPopover,
            {
                carryoverData: JSON.parse(this.props.cell.info_popup_data()),
                options: this.controller.options(),
                context: this.controller.context,
            },
            {
                closeOnClickAway: true,
                position: localization.direction === "rtl" ? "bottom" : "right",
            },
        );
    }
}

registry.category("account_reports.default_components").add("AccountReportLineCell", AccountReportLineCell);

import { _t } from "@web/core/l10n/translation";
import { formatFloatTime } from "@web/views/fields/formatters";
import { Record } from "@web/model/record";
import { FormRenderer } from "@web/views/form/form_renderer";
import { Component, plugin, props, signal, types as t } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { executeButtonCallback } from "@web/views/view_button/view_button_hook";
import { ORM } from "@web/core/orm_plugin";

export class HrHolidayPopover extends Component {
    static template = "hr_holidays_gantt.HrHolidayPopover";
    static components = {
        Record,
        FormRenderer,
    };

    props = props({
        close: t.function(),
        readonly: t.boolean(),
        onReload: t.function(),
        originalRecord: t.object(),
        recordProps: t.object(),
        archInfo: t.object(),
        getDurationStr: t.function(),
        useWorkEntryCode: t.boolean().optional(),
    });

    rootRef = signal.ref();

    setup() {
        this.orm = plugin(ORM);
        this.action = useService("action");
    }

    get currentRecordProps() {
        return {
            ...this.props.recordProps,
            resId: this.props.originalRecord.id,
            mode: this.props.readonly ? "readonly" : "edit",
            hooks: {
                onRootLoaded: (root) => {
                    root.canSaveOnUpdate = false;
                },
            },
        };
    }

    get archInfo() {
        return this.props.archInfo;
    }

    _getEmployeeName(data) {
        for (const emp of [this.props.originalRecord?.employee_id, data.employee_id]) {
            if (Array.isArray(emp)) {
                if (emp[1]) return emp[1];
            } else if (emp?.display_name) {
                return emp.display_name;
            }
        }
        return _t("Employee");
    }

    getPopoverTitle(data) {
        return `${this._getEmployeeName(data)} - ${data.duration_display}`;
    }

    getDurationStr(duration) {
        const durationStr = formatFloatTime(duration, {
            noLeadingZeroHour: true,
        }).replace(/(:00|:)/g, "h");
        return ` ${durationStr}`;
    }

    async editLeave(record) {
        await executeButtonCallback(this.rootRef(), async () => {
            await this.orm.call("hr.leave", "action_back_to_approval", [[record.resId]]);
        });
        await this.load(record, "edit");
    }

    canApprove(record) {
        return (
            record.data.state === "confirm" &&
            (record.data.can_approve || record.data.can_validate)
        );
    }

    canRefuse(record) {
        return record.data.state === "confirm" && record.data.can_refuse;
    }

    /** Approving or refusing carries a pending edit; a reader who may do neither saves alone. */
    canSave(record) {
        return record.dirty && !this.canApprove(record) && !this.canRefuse(record);
    }

    /** Pending edits are saved first: save() is a no-op on a record without changes. */
    async _applyLeaveAction(record, method) {
        await executeButtonCallback(this.rootRef(), async () => {
            if (await record.save()) {
                await this.orm.call("hr.leave", method, [[record.resId]]);
                await this.load(record, "readonly");
            }
        });
    }

    approve(record) {
        return this._applyLeaveAction(record, "action_approve");
    }

    refuse(record) {
        return this._applyLeaveAction(record, "action_refuse");
    }

    async saveLeave(record) {
        await executeButtonCallback(this.rootRef(), async () => {
            if (await record.save()) {
                await this.load(record);
            }
        });
    }

    onClickExpand() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.leave",
            views: [[false, "form"]],
            res_id: this.props.originalRecord.id,
            target: "current",
        });
    }
    
    async discardLeave(record) {
        await executeButtonCallback(this.rootRef(), async () => {
            await record.discard();
        });
        await this.load(record);
    }

    async deleteLeave(record) {
        await executeButtonCallback(this.rootRef(), async () => {
            await this.orm.call("hr.leave", "unlink", [[record.resId]]);
        });
        this.props.close();
        await this.props.onReload();
    }

    async load(record, mode) {
        const recordReload = record.load().then(() => mode && record.switchMode(mode));
        await Promise.all([this.props.onReload(), recordReload]);
    }
}

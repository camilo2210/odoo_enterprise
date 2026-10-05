import { usePlugin, proxy, onWillStart } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";
import { ConfirmationDialog, deleteConfirmationMessage } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { PayRunChatterService } from "@hr_payroll/js/payrun_chatter_service";
import { PayRunKanbanCompiler } from "@hr_payroll/views/payslip_run_kanban/hr_payslip_run_kanban_compiler";
import { parseXML } from "@web/core/utils/xml";
import { PayRunArchParser } from "@hr_payroll/views/payslip_run_kanban/hr_payslip_run_kanban_arch_parser";
import { PayrunKanbanMenu } from "@hr_payroll/views/payslip_run_kanban/hr_payslip_run_kanban_record";
import { Record } from "@web/model/record";
import { extractFieldsFromArchInfo } from "@web/model/relational_model/utils";

export class PayRunControlPanel extends ControlPanel {
    static template = "hr_payroll.PayRunControlPanel";

    static components = {
        ...ControlPanel.components,
        Record,
        PayrunKanbanMenu,
    };

    setup() {
        super.setup();
        this.payRunChatter = usePlugin(PayRunChatterService);
        this.viewService = useService("view");
        this.dialogService = useService("dialog");
        this.actionService = useService("action");
        this.state = proxy({ revId: 0, payRunReactive: this.env.payRunReactive });
        this.payRunChatter = usePlugin(PayRunChatterService);
        this.payRunKanbanCompiler = PayRunKanbanCompiler;

        onWillStart(async () => {
            // no current payrun loaded. Don't show the payrun action buttons
            if (!this.state.payRunReactive) return;

            // the archinfo is used by the compiler to generate the payrun action buttons
            const { fields, relatedModels, views } = await this.viewService.loadViews({
                resModel: 'hr.payslip.run',
                views: [[this.state.payRunReactive.payrunKanbanCardViewId ?? false, "kanban"]],
            });
            const resModel = "hr.payslip.run";
            const xmlDoc = parseXML(views["kanban"].arch);
            this.payRunArchInfo = new PayRunArchParser().parse(xmlDoc, relatedModels, resModel);
            const { activeFields } = extractFieldsFromArchInfo(this.payRunArchInfo, fields);
            this.payRunArchInfo.activeFields = activeFields;
            this.payRunArchInfo.fields = fields;
        });

        useBus(this.env.bus, "HR_PAYROLL:UPDATE_PAYRUN", this._updatePayRun.bind(this));
    }

    toggleChatter() {
        if (!this.payRunChatter.payslipRunId) {
            this.env.selectFirstRecord?.();
        }
        this.payRunChatter.toggleChatter();
    }

    get payrunRecordComponentProps() {
        return {
            resModel: "hr.payslip.run",
            resId: this.state.payRunReactive.payRunId,
            activeFields: this.payRunArchInfo.activeFields,
            fields: this.payRunArchInfo.fields,
            context: this.env.context,
            mode: "readonly",
        };
    }

    deletePayRun(record) {
        this.dialogService.add(ConfirmationDialog, {
            body: deleteConfirmationMessage,
            cancel: () => {},
            cancelLabel: _t("No, keep it"),
            confirm: async () => {
                await record.delete();
                // we are currently viewing the deleted payrun, we need to go
                // back to the payrun overview
                this.state.payRunReactive.payRunId = null;
                await this.actionService.doAction("hr_payroll.action_hr_payslip_run");
            },
            confirmLabel: _t("Delete"),
            confirmClass: "btn-danger",
            title: _t("Bye-bye, record!"),
        });
    }

    _updatePayRun() {
        // refresh the action buttons to match the new payrun state
        this.state.revId++;

        // Refresh the aside chatter messages without remounting it: a remount
        // would discard the composer state (open log note, drafted message).
        const payRunId = this.payRunChatter.payslipRunId;
        if (payRunId) {
            this.env.bus.trigger("MAIL:RELOAD-THREAD", {
                model: "hr.payslip.run",
                id: payRunId,
            });
        }
    }

}

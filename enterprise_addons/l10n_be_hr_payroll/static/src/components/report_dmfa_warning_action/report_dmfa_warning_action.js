import { Component, t, useProps } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class ReportDmfaWarning extends Component {
    static template = "l10n_be_hr_payroll.reportDmfaWarningDialog";
    static components = { Dialog };

    props = useProps({
        action: t.object(),
    });

    setup() {
        this.reportId = this.props.action.params.report_id;
        this.modelName = this.props.action.params.model_name;
        this.hasCertificate = this.props.action.params.has_certificate;
        this.action = useService("action");
        this.orm = useService("orm");
        this.dialogService = useService("dialog");
    }

    actionOpenPayrollSettings() {
        this.action.doAction("hr_payroll.action_hr_payroll_configuration");
    }

    async actionSubmitDmfa() {
        await this.orm.call(this.modelName, "action_submit_declaration", [this.reportId]);
        this.dialogService.add(ConfirmationDialog, {
            title: _t("DMFA Successfully Submitted"),
            body: _t("You'll receive the status by email from the DMFA in a few days."),
            confirmLabel: _t("Close"),
            confirm: () => {
                this.props.close();
            },
        });
    }

    async actionMarkDone() {
        await this.orm.call(this.modelName, "generate_reference_name", [this.reportId]);
        await this.orm.call(this.modelName, "action_mark_done", [this.reportId]);
        this.action.doAction({ type: "ir.actions.client", tag: "soft_reload" });
    }

    async actionViewReport() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: this.modelName,
            res_id: this.reportId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

export function ReportDmfaWarningAction(env, action) {
    const dialog = useService("dialog");
    dialog.add(ReportDmfaWarning, { action });
}

registry
    .category("actions")
    .add("l10n_be_hr_payroll.report_dmfa_warning_action", ReportDmfaWarningAction);

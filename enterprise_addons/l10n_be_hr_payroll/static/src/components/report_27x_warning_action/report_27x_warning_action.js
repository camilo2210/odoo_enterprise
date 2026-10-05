import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, t, useProps } from "@odoo/owl";
import { download } from "@web/core/network/download";
import { Dialog } from "@web/core/dialog/dialog";

class Report27XWarning extends Component {
    static template = "l10n_be_hr_payroll.report27xWarningDialog";
    static components = { Dialog };

    props = useProps({
        action: t.object(),
    });

    setup() {
        this.reportId = this.props.action.params.report_id;
        this.modelName = this.props.action.params.model_name;
        this.action = useService("action");
        this.orm = useService("orm");
    }

    async actionDownloadXml() {
        const downloadData = await this.orm.call(
            this.modelName,
            "action_generate_xml_and_download_data",
            [this.reportId]
        );
        await download({
            data: downloadData,
            url: "/web/content?download=true",
        });
    }

    async actionMarkDone() {
        await this.orm.call(this.modelName, "action_force_done", [this.reportId]);
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

export function Report27XWarningAction(env, action) {
    const dialog = useService("dialog");
    dialog.add(Report27XWarning, { action });
}

registry
    .category("actions")
    .add("l10n_be_hr_payroll.report_27x_warning_action", Report27XWarningAction);

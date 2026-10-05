import { Component, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { download } from "@web/core/network/download";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class Report281Warning extends Component {
    static template = "l10n_be_hr_payroll.report281WarningDialog";
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
        await this.orm.call(this.modelName, "action_mark_as_done", [this.reportId], {
            context: { skip_validation: true },
        });
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

export function Report281WarningAction(env, action) {
    const dialog = useService("dialog");
    dialog.add(Report281Warning, { action });
}

registry
    .category("actions")
    .add("l10n_be_hr_payroll.report_281_xx_warning_action", Report281WarningAction);

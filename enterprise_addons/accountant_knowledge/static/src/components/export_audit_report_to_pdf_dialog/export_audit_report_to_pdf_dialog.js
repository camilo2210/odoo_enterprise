import { Component, proxy, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

export class ExportAuditReportToPDFDialog extends Component {
    static template = "accountant_knowledge.ExportAuditReportToPDFDialog";
    static components = { Dialog };

    props = useProps({
        record: t.object(),
        close: t.function(),
    });

    setup() {
        this.action = useService("action");
        this.state = proxy({
            includePdfFiles: true,
            includeChildArticles: true,
        });
    }

    async exportAuditReportToPDF() {
        this.props.close();
        await this.action.doActionButton({
            type: "object",
            resModel: "knowledge.article",
            resId: this.props.record.resId,
            name: "action_export_audit_report_to_pdf",
            context: {
                include_pdf_files: Number(this.state.includePdfFiles),
                include_child_articles: Number(this.state.includeChildArticles),
            },
        });
    }
}

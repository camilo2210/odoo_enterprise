import { patch } from "@web/core/utils/patch";
import { ExportAuditReportToPDFDialog } from "@accountant_knowledge/components/export_audit_report_to_pdf_dialog/export_audit_report_to_pdf_dialog";

patch(ExportAuditReportToPDFDialog.prototype, {
    async exportAuditReportToPDF() {
        if (this.props.record.data.inherited_esg_report_id?.records.length) {
            this.props.close();
            await this.action.doActionButton({
                type: "object",
                resModel: "knowledge.article",
                resId: this.props.record.resId,
                name: "action_export_esg_report_to_pdf",
                context: {
                    include_pdf_files: Number(this.state.includePdfFiles),
                    include_child_articles: Number(this.state.includeChildArticles),
                },
            });
        } else {
            await super.exportAuditReportToPDF();
        }
    },
});

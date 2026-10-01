import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

async function downloadAuditReportAction(env, actionDescr) {
    const action = useService("action");
    const { articleId, includePdfFiles, includeChildArticles, next } = actionDescr.params;
    const params = new URLSearchParams({
        include_pdf_files: includePdfFiles,
        include_child_articles: includeChildArticles,
    });
    await action.doAction({
        type: "ir.actions.act_url",
        target: "download",
        url: `/knowledge_accountant/article/${articleId}/audit_report?${params.toString()}`,
    });
    return next;
}

registry.category("actions").add("download_audit_report", downloadAuditReportAction);

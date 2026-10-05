import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

async function downloadEsgReportAction(env, actionDescr) {
    const action = useService("action");
    const {
        articleId,
        includePdfFiles,
        includeChildArticles,
        next } = actionDescr.params;
    const params = new URLSearchParams({
        include_pdf_files: includePdfFiles,
        include_child_articles: includeChildArticles
    });
    await action.doAction({
        type: "ir.actions.act_url",
        target: "download",
        url: `/esg/article/${articleId}/esg_report?${params.toString()}`,
    });
    return next;
};

registry.category("actions").add("download_esg_report", downloadEsgReportAction);

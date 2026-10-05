import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";

export class AuditReportListController extends ListController {
    /** @override */
    async createRecord() {
        return this.actionService.doAction(
            "accountant_knowledge.action_audit_report_quick_create",
            {
                onClose: () => this.env.model.load(),
            }
        );
    }

    /** @override */
    async openRecord(record) {
        this.actionService.doAction("knowledge.ir_actions_server_knowledge_home_page", {
            additionalContext: {
                res_id: record.data.knowledge_article_id.id,
            },
        });
    }

    /**
     * @override
     * Disables the standard "Duplicate" action in the list view menu.
     * Instead, a button is provided on each row to call a custom duplicate
     * method (`action_duplicate_audit_report`), allowing the user to modify
     * the start/end dates of the new audit report copy.
     */
    getStaticActionMenuItems() {
        const menuItems = super.getStaticActionMenuItems();
        delete menuItems.duplicate;
        return menuItems;
    }
}

export const auditReportListView = {
    ...listView,
    Controller: AuditReportListController,
};

registry.category("views").add("audit_report_list", auditReportListView);

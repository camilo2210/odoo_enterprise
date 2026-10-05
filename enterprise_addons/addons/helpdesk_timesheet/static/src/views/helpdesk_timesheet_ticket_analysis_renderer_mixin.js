import { HelpdeskTicketAnalysisRendererMixin } from "@helpdesk/views/helpdesk_ticket_analysis_renderer_mixin";
import { Domain } from "@web/core/domain";

export const HelpdeskTimesheetTicketAnalysisRendererMixin = (T) =>
    class HelpdeskTimesheetTicketAnalysisRendererMixin extends HelpdeskTicketAnalysisRendererMixin(T) {
        openView(domain, views, context) {
            const fieldMapping = {
                'employee_id': 'user_id.employee_id',
                'department_id': 'user_id.employee_id.department_id',
                'employee_parent_id': 'user_id.employee_id.parent_id'
            };

            const updateDomain = domain.flatMap(leaf => {
                if (!Array.isArray(leaf) || !fieldMapping[leaf[0]]) return [leaf];

                const [field, operator, value] = leaf;
                const targetField = fieldMapping[field];

                // Handle the "is not set" (null/false) case
                if (operator === "=" && !value) {
                    return ["|", ["user_id", "=", false], [targetField, "=", false]];
                }

                return [[targetField, operator, value]];
            });

            const newDomain = Domain.removeDomainLeaves(updateDomain, ["total_hours_spent"]).toList();
            super.openView(newDomain, views, context);
        }
    };

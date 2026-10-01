import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { KanbanHeader } from "@web/views/kanban/kanban_header";

export class Form138KanbanHeader extends KanbanHeader {
    static template = "l10n_in_hr_payroll.Form138KanbanHeader";
}

export class Form138KanbanRenderer extends KanbanRenderer {
    static template = "l10n_in_hr_payroll.Form138KanbanRenderer";
    static components = {
        ...KanbanRenderer.components,
        KanbanHeader: Form138KanbanHeader,
    };
}

const Form138KanbanView = {
    ...kanbanView,
    Renderer: Form138KanbanRenderer,
};

registry.category("views").add("form_138_kanban", Form138KanbanView);

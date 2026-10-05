import { registry } from "@web/core/registry";

import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { AppraisalActionHelper } from "@hr_appraisal/views/helper/appraisal_helper_view/appraisal_helper_view";
import { AppraisalKanbanController } from "@hr_appraisal/views/kanban/appraisal_kanban/appraisal_kanban_controller";

export class AppraisalKanbanRenderer extends KanbanRenderer {
    static template = "hr_appraisal.AppraisalKanbanRenderer";
    static components = {
        ...KanbanRenderer.components,
        AppraisalActionHelper,
    };
};


export const AppraisalKanbanView = {
    ...kanbanView,
    Renderer: AppraisalKanbanRenderer,
    Controller: AppraisalKanbanController,
};

registry.category("views").add("appraisal_kanban_view", AppraisalKanbanView);

import { registry } from "@web/core/registry";

import { kanbanView } from "@web/views/kanban/kanban_view";
import { AccountReturnCheckKanbanRenderer } from "./account_return_check_kanban_renderer";
import { AccountReturnCheckKanbanController } from "./account_return_check_kanban_controller";
import { AccountReturnCheckControlPanel } from "./account_return_check_control_panel";

export const accountReturnCheckKanbanView = {
    ...kanbanView,
    Renderer: AccountReturnCheckKanbanRenderer,
    Controller: AccountReturnCheckKanbanController,
    ControlPanel: AccountReturnCheckControlPanel,
};

registry.category("views").add("account_return_check_kanban", accountReturnCheckKanbanView);

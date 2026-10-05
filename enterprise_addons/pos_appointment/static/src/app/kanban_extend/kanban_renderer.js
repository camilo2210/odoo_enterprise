import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { PosKanbanRecord } from "./kanban_record";
import { PosKanbanHeader } from "./kanban_header";

export class PosKanbanRenderer extends KanbanRenderer {
    static components = {
        ...KanbanRenderer.components,
        KanbanRecord: PosKanbanRecord,
        KanbanHeader: PosKanbanHeader,
    };
}

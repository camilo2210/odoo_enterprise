import { registry } from "@web/core/registry";

import { kanbanView } from "@web/views/kanban/kanban_view";
import { DocumentsControlPanel } from "../search/documents_control_panel";
import { DocumentsKanbanController } from "./documents_kanban_controller";
import { DocumentsKanbanModel } from "./documents_kanban_model";
import {
    DocumentsKanbanRenderer,
    DocumentsKanbanRendererCommon,
} from "./documents_kanban_renderer";
import { DocumentsSearchModel } from "../search/documents_search_model";
import { DocumentsSearchPanel } from "../search/documents_search_panel";
import { DocumentsKanbanArchParser } from "./documents_kanban_arch_parser";
import { DocumentsKanbanCompiler } from "./documents_kanban_compiler";

export const DocumentsKanbanViewCommon = Object.assign({}, kanbanView, {
    ArchParser: DocumentsKanbanArchParser,
    SearchModel: DocumentsSearchModel,
    SearchPanel: DocumentsSearchPanel,
    ControlPanel: DocumentsControlPanel,
    Controller: DocumentsKanbanController,
    Compiler: DocumentsKanbanCompiler,
    Model: DocumentsKanbanModel,
    Renderer: DocumentsKanbanRendererCommon,
    buttonTemplate: "documents.DocumentsKanbanView.Buttons",
    searchMenuTypes: ["filter", "groupBy", "favorite"],
});

export const DocumentsKanbanView = Object.assign({}, DocumentsKanbanViewCommon, {
    Renderer: DocumentsKanbanRenderer,
});

registry.category("views").add("documents_kanban", DocumentsKanbanView);
registry.category("views").add("documents_kanban_secondary", DocumentsKanbanViewCommon);

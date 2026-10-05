import { KanbanArchParser } from "@web/views/kanban/kanban_arch_parser";

// The pay run archs name their templates with the payrun_* scheme
// (payrun_name, payrun_kpis, payrun_steps, payrun_menu) so they are easy to
// find in the codebase; the two the framework requires under the standard
// kanban names are translated back before parsing.
const TEMPLATE_ALIASES = { payrun_kpis: "card", payrun_menu: "menu" };

export class PayRunArchParser extends KanbanArchParser {
    parse(xmlDoc, models, modelName) {
        for (const [alias, name] of Object.entries(TEMPLATE_ALIASES)) {
            for (const node of xmlDoc.querySelectorAll(`[t-name="${alias}"]`)) {
                node.setAttribute("t-name", name);
            }
        }
        return super.parse(xmlDoc, models, modelName);
    }
}

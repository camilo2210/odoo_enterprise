import { ListRenderer } from "@web/views/list/list_renderer";

export class AiAgentPanelListRenderer extends ListRenderer {
    static template = "ai_agentic.AiAgentPanelList";
    static rowTemplate = "";
    static empty = { icon: "", text: "" };
    /** Optional left-hand side of the header row; the add button is shared. */
    static headerTemplate = "";

    /**
     * Shared by every list in this panel (skills, sources, ...).
     * From ListRenderer: we can't really use `super.setup()` because it
     * expects to be used on a html table which is not the case here.
     */
    setup() {}
}

import { Component, proxy } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class KnowledgeTableOfContentPanel extends Component {
    static template = "knowledge.KnowledgeTableOfContentPanel";

    setup() {
        this.tocService = useService("knowledge.toc");
        this.tocState = proxy(this.tocService.getTocState());
        this.panelState = proxy(this.env.panelState);
    }

    get headings() {
        return this.tocState.tocManager?.structure.headings ?? [];
    }

    onTocLinkClick(heading) {
        this.tocState.tocManager?.scrollIntoView(heading);
    }
}

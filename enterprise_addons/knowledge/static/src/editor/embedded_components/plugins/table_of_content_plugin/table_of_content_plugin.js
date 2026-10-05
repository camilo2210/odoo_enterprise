import { TableOfContentPlugin } from "@html_editor/others/embedded_components/plugins/table_of_content_plugin/table_of_content_plugin";

export class KnowledgeTableOfContent extends TableOfContentPlugin {
    setup() {
        super.setup();
        const tocService = this.services["knowledge.toc"];
        this.tocState = tocService.getTocState();
        this.lastTocManager = this.tocState.tocManager;
        this.tocState.tocManager = this.manager;
    }

    destroy() {
        super.destroy();
        this.tocState.tocManager = this.lastTocManager;
    }
}

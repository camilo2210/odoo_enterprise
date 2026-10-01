import { Reactive } from "@web/core/utils/reactive";

export class PanelState extends Reactive {
    constructor(commentsState) {
        super();
        this.activePanel = undefined;
        this.commentsState = commentsState;
    }

    isDisplayed(panelName) {
        if (this.activePanel && this.activePanel === panelName) {
            return true;
        } else if (panelName === "comments") {
            return this.commentsState.displayMode === "panel";
        }
        return false;
    }

    /**
     * @param {"comments" | "chatter" | "properties" | "toc" | undefined} panelName
     */
    setActivePanel(panelName) {
        if (panelName !== "comments") {
            this.activePanel = panelName;
            this.commentsState.displayMode = "handler";
        } else if (panelName === "comments") {
            this.activePanel = undefined;
            this.commentsState.displayMode = "panel";
        } else {
            this.activePanel = undefined;
            this.commentsState.displayMode = "handler";
        }
    }

    isSidePanelOpen() {
        return this.activePanel || this.commentsState.displayMode === "panel";
    }
}

import {
    getEditableDescendants,
    useEditableDescendants,
} from "@html_editor/others/embedded_component_utils";
import { Component, onMounted, onWillStart, proxy } from "@odoo/owl";
import { isMobileOS } from "@web/core/browser/feature_detection";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

export class ReadonlyVoiceTranscription extends Component {
    static template = "ai.ReadonlyVoiceTranscription";
    static components = { Dropdown, DropdownItem };

    setup() {
        const { descendants, refs } = useEditableDescendants();
        this.descendants = descendants;
        this.descendantRefs = refs;
        this.isMobileOS = isMobileOS();
        this.supportedLanguages = [];
        this.state = proxy({
            currentTab: "notes",
            isOpened: true,
            hasSummary: this.descendants.summaryContent.textContent.trim() !== "",
        });

        onWillStart(() => {
            if (this.state.hasSummary) {
                this.state.currentTab = "summary";
            }
        });

        onMounted(() => {
            this.state.firstRecordingDate =
                this.descendants.transcriptContent.querySelector("b")?.innerText;
        });
    }

    setCurrentTab(tabName) {
        this.state["currentTab"] = tabName;
    }
}

export const aiReadonlyVoiceTranscriptionEmbeddedComponent = {
    name: "voice-transcription",
    Component: ReadonlyVoiceTranscription,
    getEditableDescendants,
    getProps: (host) => ({ host }),
};

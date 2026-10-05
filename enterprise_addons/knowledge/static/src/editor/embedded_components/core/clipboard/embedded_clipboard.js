import {
    getEditableDescendants,
    useEditableDescendants,
} from "@html_editor/others/embedded_component_utils";
import {
    EmbeddedComponentToolbar,
    EmbeddedComponentToolbarButton,
} from "@html_editor/others/embedded_components/core/embedded_component_toolbar/embedded_component_toolbar";
import { Component, signal } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { usePopover } from "@web/core/popover/popover_hook";
import { Tooltip } from "@web/core/tooltip/tooltip";

export class EmbeddedClipboardComponent extends Component {
    static components = {
        EmbeddedComponentToolbar,
        EmbeddedComponentToolbarButton,
    };
    static template = "knowledge.EmbeddedClipboard";

    setup() {
        const { descendants, refs } = useEditableDescendants();
        this.descendants = descendants;
        this.descendantRefs = refs;
        this.popover = usePopover(Tooltip);
        this.copyToClipboardButtonRef = signal.ref();
    }

    //--------------------------------------------------------------------------
    // HANDLERS
    //--------------------------------------------------------------------------

    async onClickCopyToClipboard() {
        const selection = document.getSelection();
        selection.removeAllRanges();
        const range = new Range();
        range.selectNodeContents(this.descendants.clipboardContent);
        selection.addRange(range);
        if (document.execCommand("copy")) {
            // Nor the original `clipboard.write` function nor the polyfill
            // written in `clipboard.js` does trigger the `clipboard_plugin`
            // `copy` handler, therefore `execCommand` should be called here so
            // that html content is properly handled within the editor.
            this.popover.open(this.copyToClipboardButtonRef(), {
                tooltip: _t("Content copied to clipboard."),
            });
            browser.setTimeout(this.popover.close, 800);
        }
        selection.removeAllRanges();
    }
}

export const clipboardEmbedding = {
    name: "clipboard",
    Component: EmbeddedClipboardComponent,
    getEditableDescendants: getEditableDescendants,
    getProps: (host) => ({ host }),
};

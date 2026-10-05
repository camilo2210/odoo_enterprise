import {
    getEditableDescendants,
    getEmbeddedProps,
    useEditableDescendants,
} from "@html_editor/others/embedded_component_utils";
import { Component, proxy, t, useProps } from "@odoo/owl";

export const readonlyFoldableSectionProps = {
    showContent: t.boolean().optional(),
};

export class ReadonlyFoldableSection extends Component {
    static template = "knowledge.ReadonlyEmbeddedFoldableSection";

    props = useProps(readonlyFoldableSectionProps);

    setup() {
        const { descendants, refs } = useEditableDescendants();
        this.editableDescendants = descendants;
        this.descendantRefs = refs;
        this.state = proxy({
            showContent: this.props.showContent,
        });
    }
    onInputChange(ev) {
        this.state.showContent = ev.target.checked;
    }
}

export const readonlyFoldableSectionEmbedding = {
    name: "foldableSection",
    Component: ReadonlyFoldableSection,
    getProps: (host) => ({ host, ...getEmbeddedProps(host) }),
    getEditableDescendants: getEditableDescendants,
};

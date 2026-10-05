import { Component, t, useProps } from "@odoo/owl";

export class CommentAnchorText extends Component {
    static template = "knowledge.CommentAnchorText";

    props = useProps({
        anchorText: t.string(),
    });

    get anchorTextArray() {
        return (this.props.anchorText || "").split("<br>");
    }
}

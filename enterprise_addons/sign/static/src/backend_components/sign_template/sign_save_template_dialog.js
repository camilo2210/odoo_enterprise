import { Component, onWillUpdateProps, proxy, t, useProps } from "@odoo/owl";

export class SignSaveTemplateDialog extends Component {
    static template = "sign.SignSaveTemplateDialog";

    props = useProps({
        isShown: t.boolean(),
        documentUsedTimesCounter: t.number(),
        onTemplateSaveClick: t.function(),
    });

    setup() {
        this.state = proxy({
            isShown: this.props.isShown,
        });

        onWillUpdateProps((nextProps) => {
            this.props = nextProps;
            this.state.isShown = this.props.documentUsedTimesCounter > 2;
        });
    }
}

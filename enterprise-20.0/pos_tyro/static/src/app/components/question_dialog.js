import { Component, useProps, t } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class QuestionDialog extends Component {
    static template = "pos_tyro.QuestionDialog";
    static components = { Dialog };
    props = useProps({
        question: t.object({
            text: t.string(),
            options: t.array(t.string()),
            isError: t.boolean().optional(),
            isManualCancel: t.boolean().optional(),
        }),
        onClickAnswer: t.function(),
        close: t.function(),
    });

    onClickOption(option) {
        this.props.onClickAnswer(option);
        this.props.close();
    }
}

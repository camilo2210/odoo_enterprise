import { Component, useProps, t } from "@odoo/owl";

const Alignment = {
    LEFT: 1,
    CENTER: 2,
    RIGHT: 3,
};

export class PrintRecMessage extends Component {
    static template = "l10n_it_pos.PrintRecMessage";
    props = useProps({
        operator: t.number().optional(1),
        messageType: t.customValidator(
            t.number(),
            (messageType) => 1 <= messageType && messageType <= 8
        ),
        index: t.customValidator(t.number(), (index) => index > 0).optional(),
        font: t.number().optional(),
        message: t.string(),
        alignment: t.selection(Object.values(Alignment)).optional(Alignment.LEFT),
    });

    get message() {
        const { messageType, message, alignment } = this.props;
        const MAX_CHARS = messageType === 4 ? 37 : 46;

        if (message.length >= MAX_CHARS) {
            return message;
        }

        let paddingLeft = 0;
        if (alignment === Alignment.CENTER) {
            paddingLeft = Math.floor((MAX_CHARS - message.length) / 2);
        } else if (alignment === Alignment.RIGHT) {
            paddingLeft = MAX_CHARS - message.length;
        }

        return " ".repeat(paddingLeft) + message;
    }
}

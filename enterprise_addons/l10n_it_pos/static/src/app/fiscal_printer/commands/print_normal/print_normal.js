import { Component, useProps, t } from "@odoo/owl";

const Alignment = {
    LEFT: 1,
    CENTER: 2,
    RIGHT: 3,
};

const MAX_CHARS = 46;

export class PrintNormal extends Component {
    static template = "l10n_it_pos.PrintNormal";
    props = useProps({
        operator: t.number().optional(1),
        font: t.number().optional(),
        data: t.string(),
        alignment: t.selection(Object.values(Alignment)).optional(Alignment.LEFT),
    });

    get data() {
        const { data, alignment } = this.props;

        if (data.length >= MAX_CHARS) {
            return data;
        }

        let paddingLeft = 0;
        if (alignment === Alignment.CENTER) {
            paddingLeft = Math.floor((MAX_CHARS - data.length) / 2);
        } else if (alignment === Alignment.RIGHT) {
            paddingLeft = MAX_CHARS - data.length;
        }

        return " ".repeat(paddingLeft) + data;
    }
}

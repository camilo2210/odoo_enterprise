import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";

import { Component, proxy, t, useProps } from "@odoo/owl";

export class RecordsSelectorPopover extends Component {
    static components = { MultiRecordSelector };
    static template = "ai.RecordsSelectorPopover";

    props = useProps({
        resModel: t.string(),
        close: t.function(),
        domain: t.array().optional(),
        validate: t.function(),
        resIds: t.array().optional(),
    });

    setup() {
        this.state = proxy({
            resIds: this.props.resIds || [],
        });
    }

    update(resIds) {
        this.state.resIds = resIds;
    }

    validate() {
        this.props.validate(this.state.resIds);
        this.props.close();
    }
}

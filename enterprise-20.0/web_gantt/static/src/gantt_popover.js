import { CARD_ATTRIBUTE } from "@web/views/card/card_arch_parser";
import { CardPopover } from "@web/views/card/card_popover/card_popover";
import { parseXML } from "@web/core/utils/xml";
import { _t } from "@web/core/l10n/translation";
import { GanttModel } from "./gantt_model";

import { Component, t, useProps } from "@odoo/owl";

// Exported so overriding modules can extend the schema (props is now an instance
// field, so `GanttPopover.props` no longer resolves; they must build on this instead).
export const ganttPopoverProps = {
    model: t.instanceOf(GanttModel),
    resId: t.any(),
    close: t.any(),
    context: t.any().optional(() => ({})),
    reloadOnClose: t.any().optional(() => () => {}),
    openRecord: t.any().optional(() => () => {}),
};

export class GanttPopover extends Component {
    static template = "web_gantt.GanttPopover";
    static components = { CardPopover };
    // downstream modules that want a custom footer override this static
    // field on their own subclass, t-inheriting "web.CardPopover.DefaultFooterButtons"
    // (directly, or through another addon's own override of this field).
    static defaultFooterButtonsTemplate = "web.CardPopover.DefaultFooterButtons";

    props = useProps(ganttPopoverProps);

    get readonly() {
        return !this.props.model.metaData.canEdit;
    }

    get cardPopoverProps() {
        const { metaData } = this.props.model;
        return {
            close: this.props.close,
            fields: metaData.fields,
            resModel: metaData.resModel,
            resId: this.props.resId,
            popoverNode: metaData.popoverNode,
            readonly: this.readonly,
            rootClass: "o_gantt_popover",
            context: this.props.model.searchParams.context,
            reloadOnClose: this.props.reloadOnClose,
            openRecord: this.props.openRecord,
            getDefaultPopoverBody: () => this.getDefaultPopoverBody(),
        };
    }

    get openRecordButtonLabel() {
        return this.readonly ? _t("View") : _t("Edit");
    }

    async onFooterBtnClicked(callback) {
        await callback();
        this.props.close();
    }

    getDefaultPopoverBody() {
        // These values to be assigned outside of arch to properly generate POT files.
        const startString = _t("Start");
        const stopString = _t("Stop");
        const { dateStartField, dateStopField } = this.props.model.metaData;
        const arch = `
            <t t-name="${CARD_ATTRIBUTE}">
                <div>
                    <strong>${startString}</strong>: <field name="${dateStartField}"/>
                </div>
                <div>
                    <strong>${stopString}</strong>: <field name="${dateStopField}"/>
                </div>
            </t>
        `;
        return parseXML(arch);
    }
}

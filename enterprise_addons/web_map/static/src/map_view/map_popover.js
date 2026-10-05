import { parseXML } from "@web/core/utils/xml";
import { _t } from "@web/core/l10n/translation";
import { CARD_ATTRIBUTE } from "@web/views/card/card_arch_parser";
import { CardPopover } from "@web/views/card/card_popover/card_popover";

import { Component, t, useProps } from "@odoo/owl";
import { MapModel } from "./map_model";

export class MapPopover extends Component {
    static template = "web_map.MapPopover";
    static components = { CardPopover };
    static defaultFooterButtonsTemplate = "web_map.MapPopover.DefaultFooterButtons";

    props = useProps({
        close: t.function(),
        model: t.instanceOf(MapModel),
        resIds: t.array(),
        record: t.object(),
        openRecord: t.function().optional(),
        reloadOnClose: t.function().optional(),
        url: t.string().optional(),
    });

    get resId() {
        return this.props.record.id;
    }

    get readonly() {
        return !this.props.model.metaData.canEdit;
    }

    get cardPopoverProps() {
        const { metaData } = this.props.model;
        return {
            close: this.props.close,
            fields: metaData.fields,
            resModel: metaData.resModel,
            resId: this.resId,
            popoverNode: metaData.popoverNode,
            readonly: this.readonly,
            rootClass: "o_map_popover",
            context: metaData.context,
            reloadOnClose: this.props.reloadOnClose,
            openRecord: this.props.openRecord,
            getDefaultPopoverBody: () => this.getDefaultPopoverBody(),
        };
    }

    get openRecordButtonLabel() {
        return this.readonly || this.props.resIds.length > 1 ? _t("View") : _t("Edit");
    }

    async onFooterBtnClicked(callback) {
        await callback();
        this.props.close();
    }

    getDefaultPopoverBody() {
        // These values to be assigned outside of arch to properly generate POT files.
        const locationOnly = this.props.resIds.length > 1;
        const fields = this.getMarkerPopupRecordData(this.props.record, locationOnly);
        const fieldsTemplate = fields.map((field) => {
            if (field.name) {
                return `<div>${field.string}</div><div><field name="${field.name}"/></div>`;
            } else if (field.value) {
                return `<div>${field.string}</div><div>${field.value}</div>`;
            }
        });
        const arch = `
            <t t-name="${CARD_ATTRIBUTE}">
                <div class="d-grid gap-2 o_map_card_grid">${fieldsTemplate.join("")}</div>
            </t>
        `;
        return parseXML(arch);
    }

    getMarkerPopupRecordData(record, locationOnly = true) {
        const fieldsView = [];
        if (!this.props.model.metaData.hideAddress) {
            if (record.partner.contact_address_complete) {
                fieldsView.push({
                    value: record.partner.contact_address_complete,
                    string: _t("Address"),
                });
            } else if (record.partner.partner_latitude && record.partner.partner_longitude) {
                fieldsView.push({
                    value:
                        record.partner.partner_latitude + ", " + record.partner.partner_longitude,
                    string: _t("Geolocation"),
                });
            }
        }
        if (locationOnly) {
            return fieldsView;
        }
        // Retro-compatibility layer: generate a card template from the fields in the arch
        for (const field of this.props.model.metaData.popoverFieldNodes) {
            if (record[field.fieldName]) {
                const fieldDef = this.props.model.metaData.fields[field.fieldName];
                fieldsView.push({
                    name: field.fieldName,
                    string: field.string || fieldDef?.string,
                });
            }
        }
        return fieldsView;
    }
}

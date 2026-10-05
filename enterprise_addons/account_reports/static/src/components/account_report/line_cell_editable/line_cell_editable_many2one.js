import { Many2OneField } from "@web/views/fields/many2one/many2one_field";
import { Record } from "@web/model/record";
import { useService } from "@web/core/utils/hooks";

import { Component, asyncComputed, computed, onWillStart, t, useProps } from "@odoo/owl";


export class AccountReportLineCellEditableMany2One extends Component {
    static template = "account_reports.AccountReportLineCellEditableMany2One";
    static components = { Many2OneField, Record };
    props = useProps({
        onChange: t.function(),
        cell: t.object(),
        audit: t.function(),
    });

    value = computed(() => this.getValue());
    
    setup() {
        this.nameService = useService("name");
        this.name = asyncComputed(() => this.loadDisplayName());
        // Wait for the name to load so it's not fetch here AND in the Many2OneField.
        onWillStart(async () => await this.name.currentPromise());
    }

    async loadDisplayName() {
        const [resModel, resId] = this.value().split(':');
        const id = parseInt(resId);
        if (!id) {
            return '';
        }
        const names = await this.nameService.loadDisplayNames(resModel, [id]);
        return names[id] || '';
    }

    async update(value) {
        const resModel = this.value().split(':')[0];
        const resId = value.data.id.id || 0;
        await this.props.onChange(`${resModel}:${resId}`);
    }

    getValue() {
        const no_format = this.props.cell.no_format();
        if (no_format) return no_format;

        const edit_popup_data = this.props.cell?.edit_popup_data();
        if (!edit_popup_data) return '';
        const cellEditData = JSON.parse(edit_popup_data);
        return `${cellEditData.target_model}:0`;
    }

    get recordProps() {
        const name = this.name();
        const [resModel, resId] = this.value().split(':');
        const id = parseInt(resId) || false;
        const fields = {
            id: {
                type: "many2one",
                relation: resModel,
            },
        };

        return {
            hooks: { onRecordChanged: (r, _) => this.update(r) },
            values: {
                id: id && name !== undefined ? [id, name] : id,
            },
            resModel,
            fields,
            activeFields: fields,
        };
    }
}

import { useService } from "@web/core/utils/hooks";
import { Component, t, useProps } from "@odoo/owl";
import { Record } from "@web/model/record";
import { Many2ManyTagsField } from "@web/views/fields/many2many_tags/many2many_tags_field";
import { getActionActiveFields } from "./sign_template_access_rights";

export class SignHeaderTags extends Component {
    static template = "sign.SignHeaderTags";
    static components = {
        Many2ManyTagsField,
        Record,
    };

    props = useProps({
        resModel: t.string(),
        resId: t.number(),
        fieldsInfo: t.object(),
    });

    setup() {
        this.orm = useService("orm");
        this.activeFields = getActionActiveFields(this.props.fieldsInfo);
    }

    getMany2ManyProps(record, fieldName) {
        return {
            name: fieldName,
            id: fieldName,
            record,
            readonly: false,
        };
    }

    get fieldName() {
        return Object.keys(this.activeFields)[0];
    }

    get recordProps() {
        return {
            mode: "edit",
            hooks: {
                onRecordChanged: (record, changes) => {
                    this.saveChanges(record, changes);
                },
            },
            resModel: this.props.resModel,
            resId: this.props.resId,
            fieldNames: Object.keys(this.activeFields),
            activeFields: this.activeFields,
        };
    }

    async saveChanges(record, changes) {
        return await this.orm.write(this.props.resModel, [record.resId], changes);
    }
}

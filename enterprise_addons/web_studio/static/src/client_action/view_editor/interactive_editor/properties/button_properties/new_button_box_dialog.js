import { Component, useProps, signal, validateType, computed, types as t } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { StudioIconSelector } from "@web_studio/client_action/components/icon_selector/icon_selector";
import { ViewEditorModel } from "@web_studio/client_action/view_editor/view_editor_model";

function buildField(params = {}) {
    const field = signal(params.value ?? null);
    if (params.validation) {
        field.required = params.required ?? true;
        field.isValid = computed(() => validateType(field(), params.validation).length === 0);
    } else {
        field.isValid = () => true;
    }
    return field;
}

export class NewButtonBoxDialog extends Component {
    static template = "web_studio.NewButtonBoxDialog";
    static components = {
        Dialog,
        StudioIconSelector,
        Many2XAutocomplete,
    };
    props = useProps({
        isAddingButtonBox: t.boolean(),
        model: t.instanceOf(ViewEditorModel),
        close: t.function(),
    });

    fields = {
        icon: buildField({ validation: t.string().optional(), required: false, value: "diamond" }),
        field_id: buildField({
            validation: t.object({
                id: t.number(),
            }),
        }),
        label: buildField({ validation: t.string() }),
    };

    canConfirm = computed(() => Object.values(this.fields).every((f) => f.isValid()));
    showInvalid = signal(false);

    setup() {
        this.orm = useService("orm");
    }

    async update(selection) {
        if (selection && !selection[0].display_name) {
            const resId = selection[0].id;
            const fields = ["display_name"];
            const record = await this.orm.read("ir.model.fields", [resId], fields);
            selection[0].display_name = record[0].display_name;
        }
        this.fields.field_id.set(selection[0]);
    }
    getDomain() {
        return [
            ["relation", "=", this.props.model.resModel],
            ["ttype", "in", ["many2one", "many2many"]],
            ["store", "=", true],
        ];
    }

    isInvalid(fname) {
        return this.showInvalid() && !this.fields[fname].isValid();
    }

    invalidClass(fname) {
        return this.isInvalid(fname) && "o_field_invalid";
    }

    onConfirm() {
        if (!this.canConfirm()) {
            this.showInvalid.set(true);
            return;
        }

        if (this.props.isAddingButtonBox) {
            this.props.model.pushOperation({ type: "buttonbox" });
        }
        this.props.model.doOperation({
            type: "add",
            target: {
                tag: "div",
                attrs: {
                    class: "oe_button_box",
                },
            },
            position: "inside",
            node: {
                tag: "button",
                field: this.fields.field_id().id,
                string: this.fields.label() || _t("New button"),
                attrs: {
                    class: "oe_stat_button",
                    icon: this.fields.icon(),
                },
            },
        });
        this.props.close();
    }
}

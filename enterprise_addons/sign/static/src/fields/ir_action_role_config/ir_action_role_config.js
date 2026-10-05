import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { Many2OneField } from "@web/views/fields/many2one/many2one_field";
import { onMounted } from "@odoo/owl";

export class IrActionRoleConfig extends X2ManyField {
    /** This component is necessary because the signing roles are dinamically shown in the UI
     * according to the selected Template. The roles get loaded on each template selection. */
    static template = "sign.IrActionRoleConfig";
    static components = { ...X2ManyField.components, Many2OneField };

    setup() {
        super.setup();
        onMounted(() => {
            for (const record of this.list.records) {
                if (
                    record.data.signer_type === "fixed" &&
                    record.data.assign_to &&
                    !record.data.sign_action_partner_id
                ) {
                    record.update(
                        { sign_action_partner_id: record.data.assign_to },
                        { save: true }
                    );
                }
            }
        });
    }

    /** Returns configuration for the sign_action_partner_id many2one field. */
    get partnerIdFieldInfo() {
        return {
            name: "sign_action_partner_id",
            forceSave: true,
            additionalProps: {
                readonly: false,
                placeholder: _t("Type a name or email..."),
                context: { force_email: true, show_email: true },
                domain: [["email", "!=", false]],
            },
        };
    }

    /** Returns the available signer type options for the selection field. */
    get signerTypeOptions() {
        return [
            { value: "fixed", label: _t("Fixed Signer") },
            { value: "linked_field", label: _t("Linked Field") },
        ];
    }

    /** Returns configuration for the linked_field_id many2one field with dynamic domain. */
    get linkedFieldIdFieldInfo() {
        const modelName = this.props.record.data.model_name;
        const modelId = modelName && this.props.record.data.model_id.id;
        return {
            name: "linked_field_id",
            forceSave: true,
            additionalProps: {
                readonly: false,
                placeholder: _t("Select field..."),
                domain: modelName
                    ? [
                          ["model_id", "=", modelId],
                          ["ttype", "=", "many2one"],
                          ["relation", "in", ["res.users", "res.partner"]],
                      ]
                    : [["id", "=", -1]],
            },
        };
    }

    /** Handles signer type changes and clears the opposite field value. */
    async onSignerTypeChange(record, ev) {
        const newValue = ev.target.value;
        const updates = { signer_type: newValue };
        if (newValue === "fixed") {
            updates.linked_field_id = false;
            // Set sign_action_partner_id to assign_to if not already set.
            if (record.data.assign_to && !record.data.sign_action_partner_id) {
                updates.sign_action_partner_id = record.data.assign_to;
            }
        } else {
            updates.sign_action_partner_id = false;
        }
        await record.update(updates, { save: true });
    }
}

export const irActionRoleConfig = {
    component: IrActionRoleConfig,
    displayName: _t("Role Configuration"),
    additionalClasses: ["o_required_modifier"],
    supportedTypes: ["one2many", "many2many"],
    relatedFields: [
        { name: "name", type: "char", readonly: true },
        { name: "assign_to", type: "many2one", relation: "res.partner", readonly: true },
        {
            name: "sign_action_partner_id",
            type: "many2one",
            relation: "res.partner",
            readonly: false,
            forceSave: true,
        },
        {
            name: "signer_type",
            type: "selection",
            readonly: false,
            forceSave: true,
            selection: [
                ["fixed", _t("Fixed Signer")],
                ["linked_field", _t("Linked Field")],
            ],
        },
        {
            name: "linked_field_id",
            type: "many2one",
            relation: "ir.model.fields",
            readonly: false,
            forceSave: true,
        },
    ],
    fieldDependencies: [],
    extractProps: x2ManyField.extractProps,
};

registry.category("fields").add("ir_action_role_config", irActionRoleConfig);

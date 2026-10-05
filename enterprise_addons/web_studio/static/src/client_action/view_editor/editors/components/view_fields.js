import { Component, proxy, t, usePlugin, useProps } from "@odoo/owl";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";
import { _t } from "@web/core/l10n/translation";
import { localeCompare } from "@web/core/l10n/utils";
import { SidebarDraggableItem } from "@web_studio/client_action/components/sidebar_draggable_item/sidebar_draggable_item";

export class ExistingFields extends Component {
    static components = { SidebarDraggableItem };
    props = useProps({
        fieldsInArch: t.array(),
        fields: t.object(),
        filterFields: t.boolean().optional(true),
        folded: t.boolean().optional(true),
        resModel: t.string().optional(""),
    });
    static template = "web_studio.ViewFields.ExistingFields";

    debugMode = usePlugin(DebugModePlugin);

    setup() {
        this.state = proxy({
            folded: this.props.folded,
            searchValue: "",
        });
    }

    isMatchingSearch(field) {
        if (!this.state.searchValue) {
            return true;
        }
        const search = this.state.searchValue.toLowerCase();
        let matches = field.string.toLowerCase().includes(search);
        if (!matches && this.debugMode.isActive() && field.name) {
            matches = field.name.toLowerCase().includes(search);
        }
        return matches;
    }

    get existingFields() {
        const fieldsInArch = this.props.fieldsInArch;
        const filtered = Object.entries(this.props.fields).filter(([fName, field]) => {
            if (
                !this.isMatchingSearch(field) ||
                (this.props.filterFields && fieldsInArch.includes(fName))
            ) {
                return false;
            }
            return true;
        });

        return filtered
            .map(([fName, field]) => ({
                ...field,
                name: fName,
                classType: field.type,
                dropData: JSON.stringify({ fieldName: fName }),
            }))
            .sort((fieldA, fieldB) =>
                localeCompare(fieldA.string || fieldA.name, fieldB.string || fieldB.name)
            );
    }

    getDropInfo(field) {
        return {
            structure: "field",
            fieldName: field.name,
            isNew: false,
        };
    }
}

const newFields = [
    { type: "char", string: _t("Text") },
    { type: "text", string: _t("Multiline Text") },
    { type: "integer", string: _t("Integer") },
    { type: "float", string: _t("Decimal") },
    { type: "html", string: _t("HTML") },
    { type: "monetary", string: _t("Monetary") },
    { type: "date", string: _t("Date") },
    { type: "datetime", string: _t("Datetime") },
    { type: "boolean", string: _t("CheckBox") },
    { type: "selection", string: _t("Selection") },
    { type: "binary", string: _t("File"), widget: "file" },
    { type: "one2many", string: _t("Lines"), special: "lines" },
    { type: "one2many", string: _t("One2Many") },
    { type: "many2one", string: _t("Many2One") },
    { type: "many2many", string: _t("Many2Many") },
    { type: "binary", string: _t("Image"), widget: "image", name: "picture" },
    { type: "many2many", string: _t("Tags"), widget: "many2many_tags", name: "tags" },
    { type: "selection", string: _t("Priority"), widget: "priority" },
    { type: "binary", string: _t("Signature"), widget: "signature" },
    { type: "related", string: _t("Related Field") },
];

export class NewFields extends Component {
    static components = { SidebarDraggableItem };
    static template = "web_studio.ViewFields.NewFields";

    get newFieldsComponents() {
        return newFields.map((f) => {
            const classType = f.special || f.name || f.widget || f.type;
            return {
                ...f,
                name: classType,
                classType,
                dropData: JSON.stringify({
                    fieldType: f.type,
                    widget: f.widget,
                    name: f.name,
                    special: f.special,
                    string: f.string,
                }),
            };
        });
    }
}

import {
    Component,
    onWillStart,
    onWillUpdateProps,
    proxy,
    t,
    usePlugin,
    useProps,
} from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";
import { Property } from "@web_studio/client_action/view_editor/property/property";
import { CheckBox } from "@web/core/checkbox/checkbox";
import { TypeWidgetProperties } from "@web_studio/client_action/view_editor/interactive_editor/properties/type_widget_properties/type_widget_properties";
import { ViewStructureProperties } from "@web_studio/client_action/view_editor/interactive_editor/properties/view_structure_properties/view_structure_properties";
import { useService } from "@web/core/utils/hooks";
import { ClassAttribute } from "../class_attribute/class_attribute";
import { ModifiersProperties } from "../modifiers/modifiers_properties";
import { useEditNodeAttributes } from "@web_studio/client_action/view_editor/view_editor_model";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

class TechnicalName extends Component {
    static template = "web_studio.ViewEditor.InteractiveEditorProperties.Field.TechnicalName";
    static components = { Property };

    props = useProps({
        node: t.object(),
    });

    debugMode = usePlugin(DebugModePlugin);

    setup() {
        this.renameField = (value) =>
            this.env.viewEditorModel.renameField(this.props.node.attrs.name, `x_studio_${value}`, {
                autoUnique: false,
            });
    }

    get canEdit() {
        return (
            this.debugMode.isActive() &&
            this.env.viewEditorModel.isFieldRenameable(this.props.node.attrs.name)
        );
    }

    get fieldName() {
        const fName = this.props.node.attrs.name;
        if (this.canEdit) {
            return fName.split("x_studio_")[1];
        }
        return fName;
    }
}

export class FieldProperties extends Component {
    static template = "web_studio.ViewEditor.InteractiveEditorProperties.Field";
    static components = {
        ClassAttribute,
        Property,
        TechnicalName,
        TypeWidgetProperties,
        ViewStructureProperties,
        ModifiersProperties,
        CheckBox,
    };

    props = useProps({
        node: t.object(),
        availableOptions: t.array().optional(),
    });

    debugMode = usePlugin(DebugModePlugin);

    setup() {
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.multiCompany = user.allowedCompanies.length > 1;
        this.activeCompany = user.activeCompany;
        this.state = proxy({});
        this.editNodeAttributes = useEditNodeAttributes();

        onWillStart(async () => {
            const node = this.props.node;
            if (this._canShowDefaultValue(node) || this.canShowTracking(node)) {
                const infos = await this.getFieldInfos(node);
                if (this._canShowDefaultValue(node)) {
                    this.state.defaultValue = infos.default_value;
                }
                if (this.canShowTracking(node)) {
                    this.state.tracking = infos.tracking;
                }
            }
        });

        onWillUpdateProps(async (nextProps) => {
            const node = nextProps.node;
            if (this._canShowDefaultValue(node) || this.canShowTracking(node)) {
                const infos = await this.getFieldInfos(node);
                if (this._canShowDefaultValue(node)) {
                    this.state.defaultValue = infos.default_value;
                }
                if (this.canShowTracking(node)) {
                    this.state.tracking = infos.tracking;
                }
            }
        });
    }

    get viewEditorModel() {
        return this.env.viewEditorModel;
    }

    async onChangeFieldString(value) {
        if (this.viewEditorModel.isFieldRenameable(this.props.node.field.name) && value) {
            return this.viewEditorModel.renameField(this.props.node.attrs.name, value, {
                label: value,
            });
        } else {
            const operation = {
                new_attrs: { string: value },
                type: "attributes",
                position: "attributes",
                target: this.viewEditorModel.getFullTarget(this.viewEditorModel.activeNodeXpath),
            };
            // FIXME: the python API is messy: we need to send node, which is the same as target since
            // we are editing the target's attributes, to be able to modify the python field's string
            operation.node = operation.target;
            return this.viewEditorModel.doOperation(operation);
        }
    }

    onChangeAttribute(value, name) {
        const attributesToChange = { [name]: value };
        if (name === "widget") {
            attributesToChange["options"] = null;
        }
        return this.editNodeAttributes(attributesToChange);
    }

    async onChangeDefaultValue(value) {
        await rpc("/web_studio/set_default_value", {
            model_name: this.env.viewEditorModel.resModel,
            field_name: this.props.node.field.name,
            value,
            company_id: user.activeCompany.id,
        });
        this.state.defaultValue = value;
    }

    getBoldValue() {
        const classList = this.props.node.arch.classList;
        return (
            classList.contains("fw-bold") ||
            classList.contains("fw-bolder") ||
            this.props.node.attrs.bold // legacy kanban
        );
    }

    get optionalVisibilityChoices() {
        return {
            choices: [
                { label: _t("Show by default"), value: "show" },
                { label: _t("Hide by default"), value: "hide" },
            ],
        };
    }

    getDefaultValuePropertyProps() {
        if (!this._canShowDefaultValue(this.props.node)) {
            return null;
        }
        const { field, attrs } = this.props.node;
        const props = {
            childProps: {},
            inputAttributes: {},
        };
        if (field.selection) {
            props.childProps.choices = this.props.node.field.selection.map(([value, label]) => ({
                label,
                value,
            }));
        }
        const fieldType = field.type;
        const widget = attrs.widget;
        props.type = fieldType;
        if (widget === "statusbar") {
            props.type = "selection";
        }
        return props;
    }

    _canShowDefaultValue(node) {
        const field = node.field;
        return (
            !["image", "many2many", "one2many", "many2one", "binary"].includes(field.type) &&
            !field.readonly
        );
    }

    get canEditSelectionChoices() {
        return this.props.node.field.manual && this.props.node.field.type === "selection";
    }

    get canEditStages() {
        return (
            this.props.node.field.type === "many2one" &&
            this.props.node.attrs?.widget === "statusbar"
        );
    }

    editStages() {
        this.action.doAction({
            name: _t("Edit Stages for field %s", this.props.node.field.label),
            type: "ir.actions.act_window",
            res_model: this.props.node.field.relation,
            views: [
                [false, "list"],
                [false, "form"],
            ],
        });
    }

    /**
     * @param {string} name of the attribute
     * @returns if this attribute supported in the current view
     */
    isAttributeSupported(name) {
        return this.props.availableOptions?.includes(name);
    }

    editSelectionChoices() {
        return this.viewEditorModel.editFieldSelectionChoices({
            fieldName: this.props.node.field.name,
        });
    }

    async getFieldInfos(node) {
        return rpc("/web_studio/get_field_infos", {
            model_name: this.env.viewEditorModel.resModel,
            field_name: node.field.name,
            company_id: user.activeCompany.id,
        });
    }

    async onChangeTracking(value) {
        const trackingValue = value ? 100 : 0;
        await rpc("/web_studio/set_field_tracking", {
            model_name: this.env.viewEditorModel.resModel,
            field_name: this.props.node.field.name,
            tracking_value: trackingValue,
        });
        this.state.tracking = value;
    }

    canShowTracking(node) {
        return node.field.manual && !["one2many", "binary", "image"].includes(node.field.type);
    }
}

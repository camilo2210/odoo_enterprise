import { Component, proxy, useProps } from "@odoo/owl";
import { rpcBus } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { StatusBarField } from "@web/views/fields/statusbar/statusbar_field";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";

class StudioStatusBarField extends Component {
    static template = "web_studio.StudioStatusBarField";
    static components = {
        StatusBarField,
    };

    props = useProps(standardFieldProps);

    static onFieldClicked(ev, { onClickDefault }) {
        if (ev.target.closest("[data-enable-click]")) {
            onClickDefault();
            return true;
        }
    }

    setup() {
        this.dialog = useService("dialog");
        this.state = proxy({
            barKey: 0,
        });
        this.fieldType = this.props.record.fields[this.props.name].type;
    }

    addSelectionStage() {
        return this.env.viewEditorModel.editFieldSelectionChoices({ fieldName: this.props.name });
    }

    addStage() {
        if (this.fieldType === "selection") {
            return this.addSelectionStage();
        } else if (this.fieldType === "many2one") {
            return this.addMany2OneStage();
        }
    }

    addMany2OneStage() {
        const record = this.props.record;
        const resModel = record.fields[this.props.name].relation;
        this.dialog.add(FormViewDialog, {
            resModel,
            onRecordSaved: () => {
                record.model.specialDataCaches = {};
                rpcBus.trigger("CLEAR-CACHES", "search_read");
                this.state.barKey++;
            },
        });
    }
}

registry.category("editor_fields").add("statusbar", StudioStatusBarField);

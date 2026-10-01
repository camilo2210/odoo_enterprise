import { Component, useProps, proxy, signal, t } from "@odoo/owl";
import { useOwnedDialogs, useAutofocus } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

import { _t } from "@web/core/l10n/translation";

import { useDialogConfirmation } from "@web_studio/client_action/utils";
import { ModelConfiguratorDialog } from "../model_configurator/model_configurator";
import { RecordSelector } from "@web/core/record_selectors/record_selector";

export class MenuCreatorModel {
    constructor({ allowNoModel } = {}) {
        this.data = {
            modelId: false,
            menuName: "",
            modelChoice: "new",
        };

        // Info to select what kind of model is linked to the menu
        this.modelChoiceSelection = {
            new: _t("New Model"),
            existing: _t("Existing Model"),
        };

        if (allowNoModel) {
            this.modelChoiceSelection.parent = _t("Parent Menu");
        }
    }

    validateField(fieldName) {
        if (fieldName === "menuName") {
            return !!this.data.menuName;
        } else if (fieldName === "modelId") {
            return this.data.modelChoice === "existing" ? !!this.data.modelId : true;
        }
    }

    get isValid() {
        return ["menuName", "modelId"].every((fName) => this.validateField(fName));
    }
}

export class MenuCreator extends Component {
    static template = "web_studio.MenuCreator";

    autofocusRef = signal.ref();
    static components = { RecordSelector };
    props = useProps({
        menuCreatorModel: t.object(),
        showValidation: t.boolean().optional(false),
    });

    get multiRecordSelectorProps() {
        return {
            resModel: "ir.model",
            fieldString: _t("Models"),
            resId: this.state.data.modelId && this.state.data.modelId[0],
            update: (resId) => (this.state.data.modelId = [resId]),
            domain: [
                ["transient", "=", false],
                ["abstract", "=", false],
            ],
        };
    }

    setup() {
        useAutofocus({ ref: this.autofocusRef });
        this.state = proxy(this.props.menuCreatorModel);
    }

    isValid(fieldName) {
        return this.props.showValidation ? this.state.validateField(fieldName) : true;
    }
}

export class MenuCreatorDialog extends Component {
    static template = "web_studio.MenuCreatorDialog";
    static components = { Dialog, MenuCreator };
    props = useProps({
        confirm: t.function(),
        close: t.function(),
    });

    setup() {
        this.addDialog = useOwnedDialogs();
        this.menuCreatorModel = proxy(new MenuCreatorModel({ allowNoModel: true }));
        this.state = proxy({ showValidation: false });
        const { confirm, cancel } = useDialogConfirmation({
            confirm: async (data = {}) => {
                if (!this.menuCreatorModel.isValid) {
                    this.state.showValidation = true;
                    return false;
                }
                await this.props.confirm(data);
            },
        });
        this._confirm = confirm;
        this._cancel = cancel;
    }

    confirm(data = {}) {
        this._confirm({ ...this.menuCreatorModel.data, ...data });
    }

    onCreateNewModel() {
        if (!this.menuCreatorModel.isValid) {
            this.state.showValidation = true;
            return;
        }
        this.addDialog(ModelConfiguratorDialog, {
            confirmLabel: _t("Create Menu"),
            confirm: (data) => {
                this.confirm({ modelOptions: data });
            },
        });
    }
}

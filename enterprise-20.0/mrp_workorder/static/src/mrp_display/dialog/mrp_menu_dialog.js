import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { MrpWorkcenterDialog } from "./mrp_workcenter_dialog";
import { MrpQualityCheckSelectDialog } from "./mrp_check_select_dialog";

import { Component, proxy, onWillStart, t, useProps } from "@odoo/owl";

export class MrpMenuDialog extends Component {
    static template = "mrp_workorder.MrpDisplayMenuDialog";
    static components = { Dialog };

    props = useProps({
        close: t.function(),
        groups: t.object(),
        params: t.object(),
        record: t.object(),
        reload: t.function(),
        title: t.string(),
        removeFromCache: t.function(),
        registerProduction: t.function(),
        logTime: t.function(),
        updateWorkcenter: t.function(),
        onNavigateToMO: t.function().optional(),
    });

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialogService = useService("dialog");
        this.notification = useService("notification");
        this.state = proxy({ menu: "main" });
        this.workOrdersEnabled = false;

        onWillStart(async () => {
            this.workOrdersEnabled = await user.hasGroup("mrp.group_mrp_routings");
        });
    }

    getNotificationMessage(method) {
        // Notification messages are consolidated here to avoid redundant overrides in extending modules.
        if (method === "action_scrap") {
            return _t("The scrap order has been successfully registered.");
        } else if (method === "button_quality_alert") {
            return _t("The quality alert has been successfully created.");
        } else if (method === "button_maintenance_req") {
            return _t("The maintenance request has been successfully created.");
        }
        return "";
    }

    async callAction(method, props = {}) {
        const action = await this.orm.call(
            this.props.record.resModel,
            method,
            [[this.props.record.resId]],
            {
                context: { from_shop_floor: true },
            }
        );

        const message = this.getNotificationMessage(method);
        if (message) {
            props.onSave = async () => {
                this.notification.add(message, { type: "success" });
            };
        }

        await this.action.doAction(action, {
            onClose: async () => {
                await this.props.reload(this.props.record);
            },
            props,
        });
        this.props.close();
    }

    async callAddComponentAction() {
        return this.callAction("action_add_component", {
            onCatalogUpdated: async () => {
                await this.props.reload(this.props.record);
            },
        });
    }

    async callAddByProductAction() {
        return this.callAction("action_add_byproduct", {
            onCatalogUpdated: async () => {
                await this.props.reload(this.props.record);
            },
        });
    }

    async moveToWorkcenter() {
        const workcenters = await this.orm.searchRead("mrp.workcenter", [], ["display_name"]);
        function _moveToWorkcenter(workcenters) {
            const workcenter = workcenters[0];
            this.props.record.update({ workcenter_id: workcenter });
            this.props.record.save().then((succeeded) => {
                if (succeeded) {
                    this.notification.add(_t("The operation has been successfully moved."), {
                        type: "success",
                    });
                }
            });
            this.props.removeFromCache(this.props.record.resId);
            this.props.close();
        }
        const params = {
            title: _t("Select a new work center"),
            confirm: _moveToWorkcenter.bind(this),
            radioMode: true,
            workcenters: workcenters.filter(
                (w) => w.id !== this.props.record.data.workcenter_id.id
            ),
        };
        this.dialogService.add(MrpWorkcenterDialog, params);
    }

    async openMO() {
        const id =
            this.props.record.resModel === "mrp.production"
                ? this.props.record.resId
                : this.props.record.data.production_id.id;

        if (this.props.onNavigateToMO) {
            this.props.onNavigateToMO();
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "mrp.production",
            views: [[false, "form"]],
            res_id: id,
        });

        this.props.close();
    }

    async block() {
        const options = {
            additionalContext: { default_workcenter_id: this.props.record.data.workcenter_id.id },
            onClose: async (result) => {
                await this.props.reload();
                if (!result) {
                    this.props.updateWorkcenter(this.props.record.data.workcenter_id.id, "blocked")
                }
            },
        };
        await this.action.doAction("mrp.act_mrp_block_workcenter_wo", options);
        this.props.close();
    }

    async unblock() {
        await this.action.doActionButton({
            type: "object",
            resId: this.props.record.data.workcenter_id.id,
            name: "unblock",
            resModel: "mrp.workcenter",
            onClose: async () => {
                await this.props.reload();
                this.props.updateWorkcenter(this.props.record.data.workcenter_id.id, "normal")
            },
        });
        this.props.close();
    }

    displayMainMenu() {
        this.state.menu = "main";
    }

    displayInstructionsMenu() {
        this.state.menu = "instructions";
    }

    displayImprovementMenu() {
        this.state.menu = "improvement";
    }

    displayModifyRoutingMenu() {
        this.state.menu = "routing";
    }

    updateStep() {
        this.proposeChange("update_step");
    }

    async addStep() {
        if (this.props.params.checks?.length > 0) {
            this.proposeChange("add_step");
        } else {
            await this.proposeChangeForCheck("add_step", null);
        }
    }

    removeStep() {
        this.proposeChange("remove_step");
    }

    setPicture() {
        this.proposeChange("set_picture");
    }

    proposeChange(type) {
        let title = _t("Select the step you want to modify");
        if (type === "add_step") {
            title = _t("Indicate after which step you would like to add this one");
        }
        const params = {
            title,
            confirm: this.proposeChangeForCheck.bind(this),
            checks: this.props.params.checks,
            type,
        };
        this.dialogService.add(MrpQualityCheckSelectDialog, params);
    }

    async proposeChangeForCheck(type, check) {
        let action;
        if (type === "add_step") {
            if (check) {
                await this.orm.write("mrp.workorder", [this.props.record.resId], {
                    current_quality_check_id: check.id,
                });
            }
            action = await this.orm.call("mrp.workorder", "action_add_step", [
                [this.props.record.resId],
            ]);
        } else {
            action = await this.orm.call("mrp.workorder", "action_propose_change", [
                [this.props.record.resId],
                type,
                check.id,
            ]);
        }
        await this.action.doAction(action, {
            onClose: async () => {
                await this.props.reload(this.props.record);
                if (type === "remove_step") {
                    this.notification.add(
                        _t(
                            "Your suggestion to delete the %s step was successfully created.",
                            check.display_name
                        ),
                        { type: "success" }
                    );
                }
            },
        });
        this.props.close();
    }
}

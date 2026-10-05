import { proxy } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { VersionPayrunListRenderer } from "./hr_version_list_renderer";

export class VersionPayrunListController extends ListController {
    static template = "hr_payroll.VersionPayrunListController";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.dialogService = useService("dialog");
        this.state = proxy({
            disabled: false,
        });
        this.baseDomain = this.props.domain || [];
        this.extraVersionIds = [];
    }

    buildRawRecord(rawRecord) {
        return {
            ...rawRecord,
            date_start: luxon.DateTime.fromISO(rawRecord.date_start).toISODate(),
            date_end: luxon.DateTime.fromISO(rawRecord.date_end).toISODate(),
            structure_id: rawRecord.structure_id.id,
            company_id: rawRecord.company_id,
        };
    }

    async onSelect() {
        // if the payrun already exists, just add more employees to it
        if (this.props.context?.payrun_id) {
            await this.addVersions();
        } else {
            await this.createPayrun();
        }
    }

    async _openPayrun(ids, options = {}) {
        const action = await this.orm.call("hr.payslip.run", "action_open_payslips", [ids]);
        return this.actionService.doAction(action, options);
    }

    async addVersions() {
        this.state.disabled = true;
        const selectedVersions = await this.model.root.getResIds(true);
        const payrunId = this.props.context.payrun_id;
        await this.orm.call("hr.payslip.run", "action_add_versions", [payrunId, selectedVersions]);
        return this._openPayrun(payrunId, { stackPosition: "replaceCurrentAction" });
    }

    async createPayrun() {
        this.state.disabled = true;
        const selectedEmployees = await this.model.root.getResIds(true);
        if (this.props.context.raw_record) {
            const rawRecord = this.buildRawRecord(this.props.context.raw_record);
            const ids = await this.orm.create("hr.payslip.run", [rawRecord]);
            if (ids) {
                await this.orm.call("hr.payslip.run", "action_assign_versions", [ids, selectedEmployees]);
                return this._openPayrun(ids);
            }
        }
    }

    async onClose() {
        return this.actionService.doAction({ type: "ir.actions.act_window_close" });
    }

    async onBack() {
        const rawRecord = this.buildRawRecord(this.props.context.raw_record);
        return this.actionService.doAction("hr_payroll.action_hr_payslip_run_create", {
            additionalContext: Object.fromEntries(
                Object.entries(rawRecord).map(([key, value]) => [`default_${key}`, value])
            ),
        });
    }

    async onCreateEmployee() {
        this.dialogService.add(FormViewDialog, {
            resModel: "hr.employee",
            onRecordSaved: async (record) => {
                const employeeId = record.resId;
                const newVersionIds = await this.orm.search("hr.version", [
                    ["employee_id", "=", employeeId],
                ]);
                this.extraVersionIds.push(...newVersionIds);
                const newDomain = [
                    "|",
                    ...this.baseDomain,
                    ["id", "in", this.extraVersionIds],
                ];
                await this.model.load({ domain: newDomain });
                this.model.notify();
            },
        });
    }

    /**
     * @override
     */
    async openRecord(record, { force, newWindow } = { force: false }) {
        const dirty = await record.isDirty();
        if (dirty) {
            await record.save();
        }
        return this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.employee",
            res_id: record.resId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}
export const versionPayrunListController = {
    ...listView,
    Controller: VersionPayrunListController,
    buttonTemplate: "hr_payroll.VersionPayrunListController.Buttons",
    Renderer: VersionPayrunListRenderer,
};

registry.category("views").add("hr_version_payrun_list", versionPayrunListController);

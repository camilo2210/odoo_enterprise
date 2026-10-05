import { useSubEnv } from "@web/owl2/utils";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { registry } from "@web/core/registry";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { KanbanHeader } from "@web/views/kanban/kanban_header";
import { useOpenPayRun } from "../payslip_run_hook";
import { PayRunKanbanCompiler } from "./hr_payslip_run_kanban_compiler";
import { PayRunArchParser } from "./hr_payslip_run_kanban_arch_parser";
import { PayrunKanbanRecord } from "./hr_payslip_run_kanban_record";
import { onWillStart, usePlugin } from "@odoo/owl";
import { Chatter } from "@mail/chatter/web_portal_project/chatter";
import { PayRunControlPanel } from "@hr_payroll/search/payrun_control_panel";
import { PayRunChatterService } from "@hr_payroll/js/payrun_chatter_service";
import { addFieldDependencies } from "@web/model/relational_model/utils";

class PayrunKanbanController extends KanbanController {
    static template = "hr_payroll.PayrunKanbanController";
    static components = {
        ...KanbanController.components,
        Chatter,
    };

    /**
     * @override
     */
    setup() {
        super.setup();
        this.openPayRun = useOpenPayRun();
        this.payRunChatter = usePlugin(PayRunChatterService);
        this.isPayRunReady = new Promise((resolve) => {
            this._resolvePayRun = resolve;
        });
        useSubEnv({
            isPayRunReady: this.isPayRunReady,
            selectFirstRecord: () => {
                const records = this.model.root.records;
                if (records.length) {
                    this.payRunChatter.selectPayslipRun(records[0]);
                }
            },
        });
        onWillStart(async () => {
            addFieldDependencies(
                this.model.config.activeFields,
                this.model.config.fields,
            );
            // we now need to reload to fetch the new fields dependencies
            await this.model.root.load();

            this.payRunChatter.closeChatter();
            this.payRunChatter.selectPayslipRun(undefined);
        });
    }

    get modelParams() {
        const params = super.modelParams;
        params.hooks.onRootLoaded = () => this._resolvePayRun();
        return params;
    }

    async openRecord(record, { newWindow } = {}) {
        await this.openPayRun({ id: record.resId });
    }

    async createRecord() {
        this.payRunChatter.closeChatter();
        await this.openPayRun({});
    }
}

export class PayrunKanbanHeader extends KanbanHeader {
    static template = "hr_payroll.PayrunKanbanHeader";
}

export class PayrunKanbanRenderer extends KanbanRenderer {
    static template = "hr_payroll.PayrunKanbanRenderer";

    static components = {
        ...KanbanRenderer.components,
        KanbanHeader: PayrunKanbanHeader,
        KanbanRecord: PayrunKanbanRecord,
    };

    setup() {
        super.setup();
        this.payRunChatter = usePlugin(PayRunChatterService);
    }
}

const PayrunKanbanView = {
    ...kanbanView,
    ArchParser: PayRunArchParser,
    Controller: PayrunKanbanController,
    Compiler: PayRunKanbanCompiler,
    Renderer: PayrunKanbanRenderer,
    ControlPanel: PayRunControlPanel,
};

registry.category("views").add("payslip_run_kanban", PayrunKanbanView);

import { onMounted, onWillStart, proxy, signal, status, useEffect } from "@odoo/owl";
import { useSubEnv } from "@web/owl2/utils";
import { useBus, useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { PayslipListRenderer } from "./hr_payslip_list_renderer";
import { PayrunNewDropdown } from "@hr_payroll/views/payslip_run_new_dropdown/payslip_run_new_dropdown";
import { PayRunLayout } from "@hr_payroll/search/payrun_layout";

export class PayslipListController extends ListController {
    static template = "hr_payroll.PayslipListView";
    static components = {
        ...PayslipListController.components,
        PayrunNewDropdown,
        Layout: PayRunLayout,
    };
    setup() {
        super.setup();

        this.rootRef = this.rootRef ?? signal.ref();

        let _resolvePayRun;
        this.isPayRunReady = new Promise((resolve) => {
            _resolvePayRun = resolve;
        });
        const self = this;
        this.payRunReactive = proxy({
            _payRunId: this.props.context?.payrun_id ?? null,
            get payRunId() {
                return this._payRunId;
            },
            set payRunId(value) {
                this._payRunId = value;
                if (value) {
                    _resolvePayRun(value);
                } else {
                    self.isPayRunReady = new Promise((resolve) => {
                        _resolvePayRun = resolve;
                    });
                }
            },
        });

        useSubEnv({
            payRunReactive: this.payRunReactive,
            isPayRunReady: this.isPayRunReady,
            rootRef: this.rootRef,
        });
        if (this.payRunReactive.payRunId) {
            const id = this.payRunReactive.payRunId;
            onWillStart(async () => {
                _resolvePayRun(id);
            });
        }

        let prevPayRunId = this.payRunReactive.payRunId;
        useEffect(() => {
            const currentId = this.payRunReactive.payRunId;
            if (currentId !== prevPayRunId) {
                prevPayRunId = currentId;
                if (currentId) {
                    this.env.bus.trigger("HR_PAYROLL:UPDATE_PAYRUN");
                }
            }
        });

        this.orm = useService("orm");
        this.viewService = useService("view");
        this.actionService = useService("action");
        this.notificationService = useService("notification");
        this.state = proxy({});

        this.displayHeaderButtonsTransitions = {
            draft: ["action_refresh_from_work_entries", "action_validate"],
            validated: ["action_payslip_paid"],
            paid: ["action_payslip_draft"],
        };

        const syncPayRunFromDomain = () => {
            const newId =
                this.env.searchModel.domain.find(
                    ([field, operator]) => field === "payslip_run_id" && operator === "="
                )?.[2] || null;
            if (newId !== this.payRunReactive.payRunId) {
                this.payRunReactive.payRunId = newId;
            }
        };
        onMounted(syncPayRunFromDomain);
        useBus(this.env.searchModel, "update", syncPayRunFromDomain);
    }

    get modelParams() {
        const params = super.modelParams;
        const superOnRootLoaded = params.hooks?.onRootLoaded;
        params.hooks = {
            ...params.hooks,
            onRootLoaded: (root) => {
                superOnRootLoaded?.(root);
                if (status(this) === "mounted") {
                    this.env.bus.trigger("HR_PAYROLL:UPDATE_PAYRUN");
                }
            },
        };
        return params;
    }

    /**
     * @override
     */
    async reload() {
        await this.model.root.load();
    }

    getSelectionFields() {
        return ["state"];
    }

    async onSelectionChanged() {
        await super.onSelectionChanged();
        let selection;
        if ((selection = await this.model.root.getResIds(true))) {
            this.state.selectionStates = await this.orm.read("hr.payslip", selection, this.getSelectionFields());
        }
    }

    displayButton(button) {
        const stateButtons = Object.values(this.displayHeaderButtonsTransitions).flat();
        const btnName = button.clickParams.name;

        if (!stateButtons.includes(btnName)) {
            return true;
        }
        const states = (this.state.selectionStates || []).map((s) => s.state);

        const effectiveState = states.includes("draft")
            ? "draft"
            : states.includes("validated")
            ? "validated"
            : "paid";

        return (this.displayHeaderButtonsTransitions[effectiveState] || []).includes(btnName);
    }

    afterExecuteActionButton() {
        // a payrun action button may change the payrun state, so we need to
        // rerender the buttons to match it
        this.env.bus.trigger("HR_PAYROLL:UPDATE_PAYRUN");
        return super.afterExecuteActionButton(...arguments);
    }

    createNewPayslip() {
        return this.actionService.doAction("hr_payroll.action_hr_payslip_new");
    }

    createNewPayRun() {
        return this.actionService.doAction("hr_payroll.action_hr_payslip_run_create");
    }
}

export const payslipListView = {
    ...listView,
    Renderer: PayslipListRenderer,
    Controller: PayslipListController,
    buttonTemplate: "hr_payroll.PayslipListView.Buttons",
};

registry.category("views").add("hr_payroll_payslip_list", payslipListView);

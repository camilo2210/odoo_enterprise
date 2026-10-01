import { useService } from "@web/core/utils/hooks";
import { PayRunButtonBox } from "../../components/payrun_card/button_box/payrun_button_box";
import { PayRunViewButton } from "@hr_payroll/views/payslip_run_view_button/payrun_view_button";
import { onWillRender, onMounted, usePlugin } from "@odoo/owl";
import { KanbanRecord } from "@web/views/kanban/kanban_record";
import { PayRunChatterService } from "@hr_payroll/js/payrun_chatter_service";

export class PayrunKanbanRecord extends KanbanRecord {
    static template = "hr_payroll.PayrunKanbanRecord";
    static menuTemplate = "hr_payroll.PayrunKanbanRecordMenu";
    static components = {
        ...KanbanRecord.components,
        PayRunButtonBox,
        ViewButton: PayRunViewButton,
    };

    setup() {
        super.setup();
        this.payRunChatter = usePlugin(PayRunChatterService);
        this.bottomSheet = useService("bottom_sheet");
        this.uiService = useService("ui");
        this.payRunDetails = useService("payRunDetails");
        onWillRender(() => {
            this.payRunDetails.publish({
                templates: this.templates,
                renderingContext: this.renderingContext,
                isPayRunReady: this.env.isPayRunReady,
                onClickViewButton: this.env.onClickViewButton,
            });
        });
        onMounted(() => {
            const root = this.rootRef();
            const input = root?.querySelector('[data-payrun-name]');
            if (!input) return;
            input.addEventListener('change', (ev) => this.onChangeName(ev));
        });
    }

    get isChatterOpen() {
        return this.payRunChatter.visible();
    }

    get isSelected() {
        return this.payRunChatter.payslipRunId === this.props.record.resId;
    }

    get renderingContext() {
        return {
            ...super.renderingContext,
            isChatterOpen: this.isChatterOpen,
            isSelected: this.isSelected,
            toggleChatter: this.toggleChatter.bind(this),
        };
    }

    onGlobalClick(ev) {
        if (ev.target.closest('.o_payrun_chatter_icon')) {
            this.toggleChatter(ev);
            return;
        }
        super.onGlobalClick(ev);
    }

    toggleChatter(ev) {
        ev?.stopPropagation();
        if (this.isChatterOpen) {
            if (this.isSelected) {
                this.payRunChatter.toggleChatter();
            } else {
                this.payRunChatter.selectPayslipRun(this.props.record);
            }
            return;
        }
        this.payRunChatter.selectPayslipRun(this.props.record);
        this.payRunChatter.toggleChatter();
    }

    getCardClasses() {
        return `${super.getCardClasses()} o_payrun_card_root d-flex flex-row align-items-center`;
    }

    async onChangeName(ev) {
        const newName = ev.target.value.trim();
        if (!newName) {
            ev.target.value = this.props.record.data.name;
            return;
        }
        await this.props.record.update({ name: newName }, { save: true });
    }

}

// this component is mainly used when we only want to show the menu of the
// kanban card (to then compile it into the PayRunButtonBox)
export class PayrunKanbanMenu extends PayrunKanbanRecord {
    static template = "hr_payroll.PayrunKanbanRecordMenu";
}

import { proxy, useProps, t } from "@odoo/owl";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { KanbanRenderer, kanbanRendererProps } from "@web/views/kanban/kanban_renderer";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { registry } from "@web/core/registry";
import { standardViewProps } from "@web/views/standard_view_props";

export class BankRecReconcileDialogKanbanController extends KanbanController {
    static template = "account_accountant.BankRecReconcileDialogKanbanView";
    props = useProps({
        ...standardViewProps,
        readonly: t.boolean().optional(),
        allowSelectors: t.boolean().optional(true),
        Compiler: t.function(),
        Model: t.function(),
        Renderer: t.function(),
        buttonTemplate: t.string(),
        archInfo: t.object(),
        createRecord: t.function().optional(() => () => {}),
        selectRecord: t.function().optional(() => () => {}),
        bankRecInfo: t.object().optional(),
    });

    async onSelectionChanged() {
        this.props.bankRecInfo.onSelectionChanged(this);
    }
}

export class BankRecReconcileDialogKanbanRenderer extends KanbanRenderer {
    static template = "account_accountant.BankRecReconcileDialogKanbanRenderer";
    props = useProps({
        ...kanbanRendererProps,
        bankRecInfo: t.any().optional(),
    });

    setup() {
        super.setup();
        if (this.props.bankRecInfo?.state) {
            this.bankRecState = proxy(this.props.bankRecInfo.state);
        }
    }
}

export const bankRecReconcileDialogKanbanRenderer = {
    ...kanbanView,
    Renderer: BankRecReconcileDialogKanbanRenderer,
    Controller: BankRecReconcileDialogKanbanController,
    props: (genericProps, view) => {
        const baseProps = kanbanView.props(genericProps, view);
        return {
            ...baseProps,
            bankRecInfo: genericProps.bankRecInfo,
        };
    },
};

registry.category("views").add("bank_rec_dialog_kanban", bankRecReconcileDialogKanbanRenderer);

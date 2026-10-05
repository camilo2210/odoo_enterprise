import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { useService, useBus } from "@web/core/utils/hooks";
import { SIZES } from "@web/core/ui/ui_utils";
import { Component, onMounted, proxy, signal, useProps, usePlugin } from "@odoo/owl";
import { useBankInstitutions } from "@account_online_synchronization/hooks/bank_institutions_hook";
import { ORM } from "@web/core/orm_plugin";

class BankConfigureWidget extends Component {
    static template = "account.BankConfigureWidget";
    props = useProps(standardWidgetProps);
    orm = usePlugin(ORM);

    containerRef = signal.ref();

    setup() {
        this.allInstitutions = [];
        this.state = proxy({
            isLoading: true,
            institutions: [],
            gridStyle: "grid-template-columns: repeat(5, minmax(90px, 1fr));",
        });
        this.action = useService("action");
        this.ui = useService("ui");
        this.bankInstitutions = useBankInstitutions();
        onMounted(this.fetchInstitutions);
        useBus(this.ui.bus, "resize", this.computeGrid.bind(this));
    }

    computeGrid() {
        if (this.allInstitutions.length > 4) {
            let containerWidth = this.containerRef() ? this.containerRef().offsetWidth - 32 : 0;
            // when the container width can't be computed, use the screen size and number of journals.
            if (!containerWidth) {
                if (this.ui.size >= SIZES.XXL) {
                    containerWidth =
                        window.innerWidth / (this.props.record.model.root.count < 6 ? 2 : 3);
                } else {
                    containerWidth = Math.max(this.ui.size * 100, 400);
                }
            }
            const canFit = Math.floor(containerWidth / 100);
            const numberOfRows = (Math.floor((this.allInstitutions.length + 1) / 2) >= canFit) + 1;
            this.state.gridStyle = `grid-template-columns: repeat(${canFit}, minmax(90px, 1fr));
                                    grid-template-rows: repeat(${numberOfRows}, 1fr);
                                    grid-auto-rows: 0px;
                                   `;
        }
        this.state.institutions = this.allInstitutions;
    }

    async fetchInstitutions() {
        this.allInstitutions = await this.bankInstitutions.fetch();
        this.state.isLoading = false;
        this.computeGrid();
    }

    async connectBank(institutionId = null) {
        const action = await this.orm.call(
            "account.online.link",
            "action_new_synchronization",
            [[]],
            {
                preferred_inst: institutionId,
                journal_id: this.props.record.resId,
            }
        );
        this.action.doAction(action);
    }

    async fallbackConnectBank() {
        const action = await this.orm.call(
            "account.online.link",
            "action_create_manual_bank_account",
            [this.props.record.resId, { journal_type: this.props.record.data.type }],
            {
                context: {
                    active_model: "account.journal",
                    active_id: this.props.record.resId,
                },
            }
        );
        this.action.doAction(action);
    }
}

export const bankConfigureWidget = {
    component: BankConfigureWidget,
};

registry.category("view_widgets").add("bank_configure", bankConfigureWidget);

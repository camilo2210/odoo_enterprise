import { Component, proxy, useProps, usePlugin } from "@odoo/owl";
import { formatMonetary } from "@web/views/fields/formatters";
import { roundDecimals } from "@web/core/utils/numbers";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useSpecialData } from "@web/views/fields/relational_utils";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { ORM } from "@web/core/orm_plugin";

class OnlineAccountSelection extends Component {
    static template = "account_online_synchronization.OnlineAccountSelection";
    props = useProps(standardFieldProps);
    orm = usePlugin(ORM);

    setup() {
        super.setup();
        this.action = useService("action");
        this.state = proxy({ loading: false });

        this.specialData = useSpecialData(async (orm, props) => {
            const { records } = await orm.webSearchRead(
                "account.online.account",
                [["id", "in", this.accountOnlineAccountIds]],
                {
                    specification: {
                        display_name: {},
                        account_number: {},
                        balance: {},
                        currency_id: {},
                    },
                }
            );
            return records;
        });
    }

    formattedBalance(account) {
        if (account?.currency_id) {
            return formatMonetary(account.balance, {
                currencyId: account.currency_id,
            });
        }
        return roundDecimals(account.balance, 2);
    }

    async connectAccount(account) {
        if (this.state.loading) {
            return;
        }
        this.state.loading = true;
        try {
            await this.action.doActionButton({
                name: "sync_now",
                resModel: "account.bank.selection",
                resId: this.props.record.resId,
                args: JSON.stringify([account.id]),
                type: "object",
                context: this.props.record.context,
            });
        } finally {
            this.state.loading = false;
        }
    }

    get accountOnlineAccountIds() {
        return this.props.record.data.account_online_account_ids.resIds;
    }

    get accountOnlineAccounts() {
        return this.specialData.data;
    }
}

registry.category("fields").add("online_account_selection", {
    component: OnlineAccountSelection,
});

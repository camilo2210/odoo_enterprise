import { usePlugin } from "@odoo/owl";
import { AccountDuplicateTransactionsPlugin } from "./account_duplicate_transaction_plugin";

export function useCheckDuplicatePlugin() {
    return usePlugin(AccountDuplicateTransactionsPlugin);
}

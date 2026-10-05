import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { AccountUploadListController} from "@account/views/account_upload_list/account_upload_list_controller"
import { AccountUploadListRenderer } from "@account/views/account_upload_list/account_upload_list_renderer";

export const accountBankStatementUploadListView = {
    ...listView,
    Controller: AccountUploadListController,
    Renderer: AccountUploadListRenderer,
    buttonTemplate: "account.AccountBankStatementImport.Buttons",
};

registry.category("views").add("account_statement_upload_tree", accountBankStatementUploadListView);

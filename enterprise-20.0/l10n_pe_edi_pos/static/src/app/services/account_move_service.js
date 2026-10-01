import { AccountMoveService, accountMoveService } from "@account/services/account_move_service";
import { patch } from "@web/core/utils/patch";

patch(AccountMoveService.prototype, {
    setup(env, services) {
        super.setup(env, services);
        this.pos = services.pos;
    },

    async downloadPdf(accountMoveId) {
        if (this.pos.company.account_fiscal_country_id.code === "PE") {
            //Invoices are not downloaded in the POS in peru. The invoice is on a receipt ticket of type electronic invoice.
            return;
        }
        super.downloadPdf(accountMoveId);
    },
});
accountMoveService.dependencies = [...accountMoveService.dependencies, "pos"];

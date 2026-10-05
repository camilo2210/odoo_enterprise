import { Interaction } from '@web/public/interaction';
import { registry } from '@web/core/registry';
import { ImportFormDialog } from "@website_generator/client_actions/import_form_dialog/import_form_dialog";

export class FrontendImportButton extends Interaction {
    static selector = '.btn-link[name="website_generator_frontend_import_products"]';
    dynamicContent = {
        _root: { "t-on-click.prevent": this.locked(this.openImportFormDialog, true) },
    };

    async openImportFormDialog(ev) {
        await this.services.dialog.add(ImportFormDialog, {
            importProducts: true,
        });
    }
}

registry.category('public.interactions').add('website_generator_sale.frontend_import_button', FrontendImportButton);

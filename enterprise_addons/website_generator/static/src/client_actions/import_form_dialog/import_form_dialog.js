import { WebsiteGeneratorForm } from "@website_generator/client_actions/import_form/import_form";
import { Dialog } from "@web/core/dialog/dialog";

export class ImportFormDialog extends WebsiteGeneratorForm {
    static components = { Dialog };
    static template = 'website_generator_sale.ImportFormDialog';
}

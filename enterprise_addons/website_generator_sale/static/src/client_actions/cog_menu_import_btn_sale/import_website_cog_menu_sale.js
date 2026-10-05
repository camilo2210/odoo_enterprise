import { registry } from "@web/core/registry";
import { STATIC_ACTIONS_GROUP_NUMBER } from "@web/search/action_menus/action_menus";
import { ImportFormDialog } from "@website_generator/client_actions/import_form_dialog/import_form_dialog";
import { ImportWebsiteCogMenu } from "@website_generator/client_actions/import_website_cog_menu/import_website_cog_menu";

const cogMenuRegistry = registry.category("cogMenu");

export class ImportWebsiteCogMenuSale extends ImportWebsiteCogMenu {
    async onImportWebsiteClick() {
        await this.dialog.add(ImportFormDialog, {
            importProducts: true,
        });
    }
}

export const importWebsiteCogMenuSaleItem = {
    Component: ImportWebsiteCogMenuSale,
    groupNumber: STATIC_ACTIONS_GROUP_NUMBER,
    isDisplayed: (env) => {
        const allowedModels = [
            "website.page",
            "product.template",
            "product.public.category"
        ];

        return env.searchModel && allowedModels.includes(env.searchModel.resModel);
    },
};

cogMenuRegistry.add("import-website-menu-sale", importWebsiteCogMenuSaleItem, { sequence: 10 });

import { registry } from "@web/core/registry";
import { STATIC_ACTIONS_GROUP_NUMBER } from "@web/search/action_menus/action_menus";
import { ImportFormDialog } from "@website_generator/client_actions/import_form_dialog/import_form_dialog";
import { ImportWebsiteCogMenu } from "@website_generator/client_actions/import_website_cog_menu/import_website_cog_menu";

const cogMenuRegistry = registry.category("cogMenu");

export class ImportWebsiteCogMenuBlog extends ImportWebsiteCogMenu {
    async onImportWebsiteClick() {
        await this.dialog.add(ImportFormDialog, {
            importBlogs: true,
        });
    }
}

export const importWebsiteCogMenuBlogItem = {
    Component: ImportWebsiteCogMenuBlog,
    groupNumber: STATIC_ACTIONS_GROUP_NUMBER,
    isDisplayed: (env) => {
        const allowedModels = [
            "blog.post",
            "blog.tag",
            "blog.blog",
            "blog.tag.category",
        ];

        return env.searchModel && allowedModels.includes(env.searchModel.resModel);
    },
};

cogMenuRegistry.add("import-website-menu-blog", importWebsiteCogMenuBlogItem, { sequence: 10 });

import { usePlugin } from "@odoo/owl";
import { ORM } from "@web/core/orm_plugin";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";

const menuRouter = async () => {
    const companyId = user.context.allowed_company_ids[0];
    const orm = usePlugin(ORM);
    return await orm.call(
        "l10n_fr_reports.aspone.sso.wizard",
        "get_fiscal_report_action",
        [companyId],
    );
};

registry.category("actions").add("l10n_fr_reports.fiscal_declaration_menu_router", menuRouter);

import { usePlugin } from "@odoo/owl";
import { ORM } from "@web/core/orm_plugin";
import { user } from "@web/core/user";

// The institutions only depend on the company's fiscal country, and the widget
// only renders for journals of the main active company, so the whole dashboard
// shares a single request.
const institutionsByCompany = new Map();

export function useBankInstitutions() {
    const orm = usePlugin(ORM);
    function fetch() {
        const companyId = user.activeCompany.id;
        if (!institutionsByCompany.has(companyId)) {
            institutionsByCompany.set(
                companyId,
                orm.silent
                    .call("account.journal", "fetch_online_sync_favorite_institutions", [])
                    .catch(() => {
                        // Drop the memoized promise so a later render retries.
                        institutionsByCompany.delete(companyId);
                        return [];
                    })
            );
        }
        return institutionsByCompany.get(companyId);
    }
    return {
        fetch,
    };
}

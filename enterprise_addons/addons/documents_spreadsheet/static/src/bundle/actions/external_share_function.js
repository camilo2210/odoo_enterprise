import { EvaluationError, registries } from "@odoo/o-spreadsheet";
import { _t } from "@web/core/l10n/translation";

const { functionRegistry } = registries;

let alreadyPatched = false;

// Allowed because, data source definitions udpates (domains, etc.) are already
// forbidden server-side
// see PUBLIC_COMMAND_PERMISSIONS
const WHITELISTED_FUNCTIONS = ["ODOO.LIST", "ODOO.LIST.VALUE", "ODOO.LIST.HEADER"];

// Patches Odoo formulas (e.g. ODOO.BALANCE) to refuse evaluation in spreadsheets
// opened through an external share. This prevents a social engineering attack
// where an external user could craft a formula targeting data they want to
// exfiltrate, then trick an internal user into opening the spreadsheet and the formula
// would evaluate with the internal user's permissions and leak data
// if the user exports the spreadsheet.
export function patchSpreadsheetExternalShareFunctionCheck() {
    const functionsToPatch = functionRegistry
        .getAll()
        .filter((def) => def.category === "Odoo" && !WHITELISTED_FUNCTIONS.includes(def.name))
        .map((def) => def.name);
    if (alreadyPatched) {
        return functionsToPatch;
    }
    alreadyPatched = true;
    for (const funcName of functionsToPatch) {
        const formula = functionRegistry.get(funcName);
        const computeKey = formula.computeArray ? "computeArray" : "compute";
        const computeFormula = formula[computeKey];
        /* eslint-disable no-inner-declarations */
        function withExternalShareCheck(...args) {
            if (this.getters.getOdooEnv().isSharedExternally?.()) {
                return new EvaluationError(
                    _t("%(function_name)s is not available in spreadsheets shared externally.", {
                        function_name: funcName,
                    })
                );
            }
            return computeFormula.apply(this, args);
        }
        functionRegistry.replace(funcName, { ...formula, [computeKey]: withExternalShareCheck });
    }
    return functionsToPatch;
}

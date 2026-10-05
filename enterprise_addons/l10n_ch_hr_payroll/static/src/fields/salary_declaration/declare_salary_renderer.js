/** @odoo-module **/
import { Component, proxy, t, useProps } from "@odoo/owl";
import { Notebook } from "@web/core/notebook/notebook";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { pick } from "@web/core/utils/objects";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useViewButtonHandler } from "@web/views/view_button/view_button_hook";
import {
    getMissingKey,
    hasMissingValue,
    swissdecFormat,
    toList,
} from "@l10n_ch_hr_payroll/components/swissdec_format";

/** Declared domains, in the order of the tabs, with the salaries each person declares to them. */
const DOMAINS = [
    { domain: "AHV-AVS", label: _t("AVS"), salaries: [["AHV-AVS-Salaries", "AHV-AVS-Salary"]] },
    { domain: "FAK-CAF", label: _t("CAF"), salaries: [["FAK-CAF-Salaries", "FAK-CAF-Salary"]] },
    { domain: "BVG-LPP", label: _t("LPP"), salaries: [["BVG-LPP-Salaries", "BVG-LPP-Salary"]] },
    { domain: "UVG-LAA", label: _t("LAA"), salaries: [["UVG-LAA-Salaries", "UVG-LAA-Salary"]] },
    { domain: "UVGZ-LAAC", label: _t("LAAC"), salaries: [["UVGZ-LAAC-Salaries", "UVGZ-LAAC-Salary"]] },
    { domain: "KTG-AMC", label: _t("IJM"), salaries: [["KTG-AMC-Salaries", "KTG-AMC-Salary"]] },
    { domain: "Tax", label: _t("Wage Statements"), salaries: [["TaxSalaries", "TaxSalary"], ["TaxSalaries", "TaxAnnuity"]] },
    { domain: "TaxAtSource", label: _t("Source Tax"), salaries: [["TaxAtSourceSalaries", "TaxAtSourceSalary"]] },
    { domain: "TaxCrossborder", label: _t("Tax Crossborder"), salaries: [["TaxCrossborderSalaries", "TaxCrossborderSalary"]] },
    { domain: "Statistic", label: _t("Statistic"), salaries: [["StatisticSalaries", "StatisticSalary"]] },
];

function getInstitutionName(domain, institution) {
    switch (domain) {
        case "AHV-AVS":
            return institution["AK-CC-BranchNumber"];
        case "FAK-CAF":
            // a compensation fund can hold several affiliations of the company
            return [institution["FAK-CAF-BranchNumber"], institution["FAK-CAF-CustomerNumber"]].filter(Boolean).join(" / ");
        case "TaxAtSource":
        case "TaxCrossborder":
            return institution.CantonID;
        default:
            return institution.InsuranceCompanyName || institution.InsuranceID;
    }
}

/** Employees declared to one institution, as a table. */
export class DeclareSalaryInstitution extends Component {
    static template = "l10n_ch_hr_payroll.DeclareSalaryInstitution";
    props = useProps({
        domain: t.string(),
        rows: t.array(),
        missingValues: t.object(),
        openMissingValue: t.function(),
        generateWageStatement: t.function().optional(),
    });

    setup() {
        this.format = swissdecFormat;
        this.state = proxy({ generatingWageStatement: false });
    }

    /** Description of a missing value, to complete it (see _get_missing_values). */
    getMissingValue(value) {
        return this.props.missingValues[getMissingKey(value)];
    }

    /** The name of the person, or the one of its employee when part of it is missing. */
    getEmployeeName(particulars) {
        const missingName = this.getMissingValue(particulars.Lastname) || this.getMissingValue(particulars.Firstname);
        return missingName?.employee_name || this.format.personName(particulars);
    }

    get hasDeclarationEvents() {
        return this.props.rows.some((row) => this.format.declarationEvents(row.values.DeclarationCategory).length);
    }

    /** Current month of each person, followed by the old and new values of its corrections. */
    get taxAtSourceRows() {
        return this.props.rows.flatMap(({ values, ...row }) => [
            { ...row, month: values.CurrentMonth, municipality: values.TaxAtSourceMunicipalityID, values: values.Current || {} },
            ...toList(values.Correction).flatMap((correction) => [
                { person: row.person, kind: "old", month: correction.Month, values: correction.Old || {} },
                { person: row.person, kind: "new", month: correction.Month, values: correction.New || {} },
            ]),
        ]);
    }

    get statisticYearlyRows() {
        const rows = [];
        for (const { values, ...row } of this.props.rows) {
            for (const yearlyValues of toList(values.AnnualValues)) {
                rows.push({ ...row, isFirst: !rows.some(({ person }) => person === row.person), values: yearlyValues });
            }
        }
        return rows;
    }

    async onGenerateWageStatement(person) {
        this.state.generatingWageStatement = person.Particulars?.EmployeeNumber;
        try {
            await this.props.generateWageStatement(person);
        } finally {
            this.state.generatingWageStatement = false;
        }
    }
}

export class DeclareSalaryRenderer extends Component {
    static template = "l10n_ch_hr_payroll.DeclareSalaryRenderer";
    props = useProps(standardFieldProps);
    handleViewButton = useViewButtonHandler();
    static components = {
        Notebook,
    };

    setup() {
        this.action = useService("action");
    }

    get declaration() {
        return this.props.record.data[this.props.name] || {};
    }

    get persons() {
        return toList(this.declaration.Staff?.Person);
    }

    /** Missing values of the declaration, described by the declaration warnings. */
    get missingValues() {
        return Object.values(this.props.record.data.actionable_warnings || {}).flatMap(
            (warning) => warning.missing_values || []
        );
    }

    /** Missing values grouped by employee, in the order of the declaration. */
    get missingValueGroups() {
        const groups = new Map();
        for (const missingValue of this.missingValues) {
            if (!groups.has(missingValue.employee_id)) {
                groups.set(missingValue.employee_id, { name: missingValue.employee_name, values: [] });
            }
            groups.get(missingValue.employee_id).values.push(missingValue);
        }
        return [...groups.values()];
    }

    /** Whether some data is missing, including the values without record to complete. */
    get hasMissingValues() {
        return this.persons.some(hasMissingValue);
    }

    openMissingValue(missingValue) {
        return this.action.doAction(missingValue.action);
    }

    /** Executed like an object button of the form, see action_refresh_missing_data. */
    async refreshMissingData() {
        await this.handleViewButton({
            clickParams: { type: "object", name: "action_refresh_missing_data" },
            getResParams: () => pick(this.props.record, "context", "evalContext", "resModel", "resId", "resIds"),
        });
    }

    /** One page per institution, listing the salaries declared to it. */
    get institutionPages() {
        const missingValues = Object.fromEntries(this.missingValues.map((missingValue) => [missingValue.key, missingValue]));
        const personsWithMissingValues = new Set(this.persons.filter(hasMissingValue));
        const pages = [];
        for (const { domain, label, salaries } of DOMAINS) {
            const rowsByInstitution = new Map();
            for (const person of this.persons) {
                for (const [salariesKey, salaryKey] of salaries) {
                    for (const values of toList(person[salariesKey]?.[salaryKey])) {
                        const institutionRef = values.institutionIDRef || "";
                        if (!rowsByInstitution.has(institutionRef)) {
                            rowsByInstitution.set(institutionRef, []);
                        }
                        const rows = rowsByInstitution.get(institutionRef);
                        const isFirst = rows.at(-1)?.person !== person;
                        rows.push({
                            person,
                            values,
                            isFirst,
                            isPension: salaryKey === "TaxAnnuity",
                            hasMissingValue: personsWithMissingValues.has(person),
                        });
                    }
                }
            }
            const institutions = new Map(
                toList(this.declaration.Institutions?.[domain]).map((institution) => [institution.institutionID, institution])
            );
            const institutionRefs = [...institutions.keys()];
            const position = (institutionRef) => (institutions.has(institutionRef) ? institutionRefs.indexOf(institutionRef) : Infinity);
            const showName = rowsByInstitution.size > 1 || ["TaxAtSource", "TaxCrossborder"].includes(domain);
            const sortedRows = [...rowsByInstitution].sort(([refA], [refB]) => position(refA) - position(refB));
            for (const [institutionRef, rows] of sortedRows) {
                const institution = institutions.get(institutionRef);
                const name = institution ? getInstitutionName(domain, institution) : institutionRef.replace(/^#/, "");
                pages.push({
                    Component: DeclareSalaryInstitution,
                    id: `${domain}${institutionRef}`,
                    title: showName && name ? `${label} ${name}` : label,
                    props: {
                        domain,
                        rows,
                        missingValues,
                        openMissingValue: this.openMissingValue.bind(this),
                        generateWageStatement: domain === "Tax" ? this.generateWageStatement.bind(this) : undefined,
                    },
                });
            }
        }
        return pages;
    }

    /** Executed like an object button of the form: saves the record, then reloads the view and its chatter. */
    async generateWageStatement(person) {
        await this.handleViewButton({
            clickParams: {
                type: "object",
                name: "action_generate_wage_statement",
                args: JSON.stringify([person.Particulars?.EmployeeNumber]),
            },
            getResParams: () => pick(this.props.record, "context", "evalContext", "resModel", "resId", "resIds"),
        });
    }
}

export const declareSalaryField = {
    component: DeclareSalaryRenderer,
    displayName: _t("Salary Data"),
};


registry.category("fields").add("declare_salary_widget", declareSalaryField);

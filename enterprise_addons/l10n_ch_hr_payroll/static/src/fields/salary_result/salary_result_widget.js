/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useProps } from "@odoo/owl";
import { SwissdecNotification } from "@l10n_ch_hr_payroll/components/swissdec_notification";
import { swissdecFormat, toList, toNotifications } from "@l10n_ch_hr_payroll/components/swissdec_format";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class SalaryResultWidget extends Component {
    props = useProps(standardFieldProps);
    static template = "l10n_ch_hr_payroll.SalaryResultWidgetTemplate";
    static components = {
        SwissdecNotification,
    };

    setup() {
        this.format = swissdecFormat;
        this.toList = toList;
    }

    get institutionDomain() {
        return this.props.record.data.domain;
    }

    /** Answer of the institution, from a salary result or a dialog response. */
    get result() {
        const response = this.props.record.data[this.props.name];
        return (response?.SalaryResult || response?.Dialog)?.[this.institutionDomain] || null;
    }

    /** Every answer but an error comes with the institution and the transmission details. */
    get answer() {
        const result = this.result;
        return result && (result.Success || result.Processing || result.CompletionReleaseIsMissing || result.NotSupported);
    }

    get persons() {
        return toList(this.result?.Success?.Staff?.Person);
    }

    /** Optional columns of the staff table, displayed when at least one person has a value. */
    get staffColumns() {
        const persons = this.persons;
        return {
            employeeNumber: persons.some((person) => person.EmployeeNumber),
            sex: persons.some((person) => person.Sex),
            nationality: persons.some((person) => person.Nationality),
            declaration: persons.some((person) => person.DeclarationCategory?.Entry || person.DeclarationCategory?.Withdrawal),
            process: persons.some((person) => person.Process),
        };
    }

    /** Width of the notification rows of the staff table (all columns but the employee one). */
    getStaffNotificationColspan(staffColumns) {
        return 1 + Object.values(staffColumns).filter(Boolean).length;
    }

    getPersonNotifications(person) {
        return [
            ...toNotifications(person.Warning?.Notification, "warning"),
            ...toNotifications(person.Info?.Notification, "info"),
        ];
    }

    /** LPP contributions of the persons. */
    get contributionRows() {
        return this.persons.flatMap((person) =>
            toList(person.Contributions?.Contribution).map((contribution, index) => ({
                person,
                isFirst: !index,
                values: contribution,
                notifications: [
                    ...toNotifications(contribution.Warning?.Notification, "warning"),
                    ...toNotifications(contribution.Info?.Notification, "info"),
                ],
            }))
        );
    }

    /** Source tax corrections: old and new values of the reversed months. */
    get taxAtSourceReversalRows() {
        return this.getTaxAtSourceCorrections("Reversal").flatMap(({ person, correction: reversal }, index, corrections) => [
            {
                person,
                isFirst: corrections[index - 1]?.person !== person,
                kind: "old",
                month: reversal.Month,
                values: reversal.Old || {},
                notifications: [],
            },
            {
                person,
                kind: "new",
                month: reversal.Month,
                values: reversal.New || {},
                notifications: toNotifications(reversal.Comment?.Notification, "info"),
            },
        ]);
    }

    /** Source tax codes that the company has to correct. */
    get taxAtSourceAwaitedCorrectionRows() {
        return this.getTaxAtSourceCorrections("AwaitCorrectionFromCompany").map(({ person, correction }, index, corrections) => ({
            person,
            isFirst: corrections[index - 1]?.person !== person,
            values: correction,
            notifications: toNotifications(correction.Comment?.Notification, "warning"),
        }));
    }

    getTaxAtSourceCorrections(correctionType) {
        return this.persons.flatMap((person) =>
            toList(person.TaxAtSourceSalaries?.TaxAtSourceSalary).flatMap((taxAtSourceSalary) =>
                toList(taxAtSourceSalary.Correction)
                    .filter((correction) => correction[correctionType])
                    .map((correction) => ({ person, correction: correction[correctionType] }))
            )
        );
    }
}

registry.category("fields").add("swissdec_salary_result", {
    component: SalaryResultWidget,
});

export default SalaryResultWidget;

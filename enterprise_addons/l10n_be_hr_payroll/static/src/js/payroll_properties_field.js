import { propertiesField, PropertiesField } from "@web/views/fields/properties/properties_field";
import { useService } from "@web/core/utils/hooks";
import { useRecordObserver } from "@web/model/relational_model/utils";
import { registry } from "@web/core/registry";

export class PayrollPropertiesField extends PropertiesField {
    setup() {
        super.setup();

        this.orm = useService("orm");
        this.allowedProperties = null;

        useRecordObserver(async (record) => {
            if (!["hr.employee", "hr.payslip"].includes(record.config.resModel)) {
                this.allowedProperties = null;
                return;
            }

            const country_code = record.data.country_code;
            const jointCommitteeId = record.data.l10n_be_joint_committee_id?.id || false;
            const structureId = record.data.structure_id?.id || record.data.struct_id?.id || false;
            if (
                country_code != "BE" ||
                !structureId ||
                (jointCommitteeId === this._lastJointCommitteeId &&
                    structureId === this._lastStructureId)
            ) {
                return;
            }

            this._lastJointCommitteeId = jointCommitteeId;
            this._lastStructureId = structureId;

            await this._updateAllowedProperties(record, jointCommitteeId, structureId);
        });
    }

    async _updateAllowedProperties(record, jointCommitteeId, structureId) {
        if (!structureId) {
            this.allowedProperties = null;
            return;
        }

        const result = await this.orm.call(
            "hr.payroll.structure",
            "get_joint_committee_rules",
            [structureId],
            { joint_committee_id: jointCommitteeId ? jointCommitteeId : false }
        );

        this.allowedProperties = new Set(result.map(String));
    }

    _filterProperties(properties) {
        if (!this.allowedProperties) {
            return properties;
        }

        return properties.filter((property) => {
            if (/^\d+$/.test(property.name)) {
                return this.allowedProperties.has(property.name);
            }
            return true;
        });
    }

    // Override to filter salary inputs based on joint committee
    get propertiesList() {
        const baseList = super.propertiesList;
        return this._filterProperties(baseList);
    }
}

export const payrollPropertiesField = {
    ...propertiesField,
    component: PayrollPropertiesField,
    additionalClasses: ['o_field_properties'],
    fieldDependencies: [{ name: "l10n_be_joint_committee_id", type: "many2one" }],
};

registry.category("fields").add("payroll_properties", payrollPropertiesField);

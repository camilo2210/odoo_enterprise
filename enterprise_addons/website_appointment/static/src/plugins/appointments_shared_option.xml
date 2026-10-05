<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">

<t t-name="website_appointment.AppointmentsFilterOption">
    <BuilderRow label.translate="Filter On">
        <BuilderSelect dataAttributeAction="'filterType'" preview="false">
            <BuilderSelectItem dataAttributeActionValue="'none'" title.translate="No Filter">No Filter</BuilderSelectItem>
            <BuilderSelectItem dataAttributeActionValue="'users'" title.translate="Specific Users" id="'filter_users_opt'">Users</BuilderSelectItem>
            <BuilderSelectItem dataAttributeActionValue="'resources'" title.translate="Specific Resources" id="'filter_resources_opt'">Resources</BuilderSelectItem>
        </BuilderSelect>
    </BuilderRow>
    <BuilderRow label.translate="Resources" level="1" t-if="this.isActiveItem('filter_resources_opt')" preview="false">
        <BuilderMany2Many
            model="'appointment.type'"
            m2oField="'resource_ids'"
            dataAttributeAction="'filterResources'"
            message.translate="Choose a resource..."
        />
    </BuilderRow>
    <BuilderRow label.translate="Users" level="1" t-if="this.isActiveItem('filter_users_opt')" preview="false">
        <BuilderMany2Many
            model="'appointment.type'"
            m2oField="'staff_user_ids'"
            domain="[['share', '=', false]]"
            dataAttributeAction="'filterUsers'"
            message.translate="Choose a user..."
        />
    </BuilderRow>
    <BuilderRow label.translate="Names" preview="false">
        <BuilderTextInput dataAttributeAction="'appointmentNames'" id="'filter_appointment_name'"
            placeholder.translate="e.g. Dental Care, ..."
            title.translate="Comma-separated list of parts of appointment names"
        />
    </BuilderRow>
</t>

</templates>

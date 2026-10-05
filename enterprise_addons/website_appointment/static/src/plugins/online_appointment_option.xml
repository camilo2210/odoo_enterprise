<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">

<t t-name="website_appointment.OnlineAppointmentOption">
    <xpath expr="." position="inside">
        <BuilderRow label.translate="Appointments">
            <BuilderSelect dataAttributeAction="'targetTypes'" preview="false">
                <BuilderSelectItem dataAttributeActionValue="'all'" title.translate="All Types">All Types</BuilderSelectItem>
                <BuilderSelectItem dataAttributeActionValue="'specify'" title.translate="Specific Types" id="'appointment_types_opt'">Specific Types</BuilderSelectItem>
            </BuilderSelect>
        </BuilderRow>
        <BuilderRow label.translate="Specify" level="1" t-if="this.isActiveItem('appointment_types_opt')" preview="false">
            <BuilderMany2Many
                model="'appointment.type'"
                domain="[['website_published', '=', true],
                    ['staff_user_ids', '!=', false],
                    '|', ['end_datetime', '=', false], ['end_datetime', '>=', this.datetime_now],
                    '|', ['website_id', '=', this.current_website.id], ['website_id', '=', false]
                    ]"
                action="'setAppTypes'"
            />
        </BuilderRow>
        <BuilderRow label.translate="Users" level="1" t-if="this.state.currentAppointmentId !== null and this.state.staffUserIds.length">
            <BuilderSelect dataAttributeAction="'targetUsers'" preview="false">
                <BuilderSelectItem dataAttributeActionValue="'all'" title.translate="All assigned users">All assigned users</BuilderSelectItem>
                <BuilderSelectItem dataAttributeActionValue="'specify'" title.translate="Specific users" id="'staff_users_opt'">Specific users</BuilderSelectItem>
            </BuilderSelect>
        </BuilderRow>
        <BuilderRow label.translate="Specify" level="2" t-if="this.isActiveItem('staff_users_opt')" preview="false">
            <BuilderMany2Many
                model="'appointment.type'"
                m2oField="'staff_user_ids'"
                action="'setStaffUsers'"
                domain="[['id', 'in', this.state.staffUserIds]]"
            />
        </BuilderRow>
    </xpath>
</t>

<t t-inherit="website.BuilderOptions" t-inherit-mode="extension">
	<xpath expr="//t[@id='snippet_specific_options']" position="after">
		<online_appointment_option selector=".s_online_appointment"/>
	</xpath>
</t>

</templates>

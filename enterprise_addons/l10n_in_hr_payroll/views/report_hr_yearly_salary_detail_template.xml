<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <template id="report_hryearlysalary">
        <t t-call="web.html_container">
            <t t-foreach="docs" t-as="o">
                <t t-call="web.internal_layout">
                    <t t-foreach="get_employee(data['form'])" t-as="employee">
                        <div class="page" style="page-break-before: always">
                            <div class="text-start mb-3 p-2" style="background-color: #f9f9f9;">
                                <h3><span t-field="employee.company_id"/></h3>
                                <p>Year - <span t-out="date_to.strftime('%Y')"/></p>
                                <table class="table table-sm table-borderless mb-2 w-100" style="font-size: 12px;">
                                    <tr>
                                        <td><strong>Employee Name :-</strong> <span t-field="employee.name"/></td>
                                        <td class="text-start"><strong>Designation :-</strong> <span t-field="employee.job_id.name"/></td>
                                    </tr>
                                    <tr>
                                        <td><strong>Employee Code :-</strong> <span t-field="employee.registration_number"/></td>
                                        <td class="text-start"><strong>Department :-</strong> <span t-field="employee.department_id.name"/></td>
                                    </tr>
                                </table>
                            </div>
                            <t t-foreach="get_employee_detail_new(employee.id).items()" t-as="structure">
                                <div t-att-style="'page-break-before: always' if not structure_first else ''">
                                    <table class="table table-sm table-borderless w-100 m-0" style="font-size: 10px">
                                        <tbody>
                                            <td class="py-2 px-1"><strong>Salary Components</strong></td>
                                            <tr t-foreach="get_periods(data['form'])" t-as="months" style="border-bottom: 1px solid lightgrey; background-color: #f5ffff;">
                                                <th class="py-2 px-1"><strong><t t-out="structure[0]"/></strong></th>
                                                <t t-foreach="months" t-as="month">
                                                    <th class="text-end py-2 px-1">
                                                        <strong><span t-out="month"/></strong>
                                                    </th>
                                                </t>
                                                <th class="text-end py-2 px-1"><strong>Total</strong></th>
                                            </tr>
                                            <tr t-foreach="structure[1]['allow_list']" t-as="allowance" style="border-bottom: 1px solid lightgrey;">
                                                <t t-if="allowance[0] in {'BASIC','GROSS'}">
                                                    <td class="py-2 px-1"><strong><span t-out="allowance[1][0]"/></strong></td>
                                                    <t t-foreach="allowance[1][1:-1]" t-as="allow">
                                                        <td class="text-end py-2 px-1"><span t-out="allow" t-options="{'widget': 'monetary', 'display_currency': employee.company_id.currency_id}"/></td>
                                                    </t>
                                                </t>
                                                <t t-else="">
                                                    <td class="py-2 px-1"><span t-out="allowance[1][0]"/></td>
                                                    <t t-foreach="allowance[1][1:-1]" t-as="allow">
                                                        <td class="text-end py-2 px-1"><span t-out="allow" t-options="{'widget': 'monetary', 'display_currency': employee.company_id.currency_id}"/></td>
                                                    </t>
                                                </t>
                                                <td t-out="allowance[1][-1:][0]" class="text-end py-2 px-1" t-options="{'widget': 'monetary', 'display_currency': employee.company_id.currency_id}"/>
                                            </tr>
                                            <tr t-foreach="structure[1]['deduct_list']" t-as="deduction" style="border-bottom: 1px solid lightgrey;">
                                                <t t-if="deduction[0] == 'NET'">
                                                    <td class="py-2 px-1"><strong><span t-out="deduction[1][0]"/></strong></td>
                                                </t>
                                                <t t-else="">
                                                    <td class="py-2 px-1"><span t-out="deduction[1][0]"/></td>
                                                </t>
                                                <t t-foreach="deduction[1][1:-1]" t-as="deduct">
                                                    <td class="text-end py-2 px-1"><span t-out="deduct" t-options="{'widget': 'monetary', 'display_currency': employee.company_id.currency_id}"/></td>
                                                </t>
                                                <td t-out="deduction[1][-1:][0]" class="text-end py-2 px-1" t-options="{'widget': 'monetary', 'display_currency': employee.company_id.currency_id}"/>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            </t>
                        </div>
                    </t>
                </t>
            </t>
        </t>
    </template>
</odoo>

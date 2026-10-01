<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <template id="tax_declaration_history">
        <t t-call="web.basic_layout">
            <t t-if="declarations">
                <t t-set="last_declaration" t-value="declarations and declarations[-1]"/>
                <div class="summary-panel">
                    <table class="summary-table">
                        <tr>
                            <td class="summary-left">
                                <table class="tds-head-row">
                                    <div class="d-flex flex-wrap align-items-start justify-content-between">
                                            <div>
                                                <div class="fw-semibold fs-4">TDS Overview</div>
                                                <div class="text-muted small">
                                                    Financial Year: <span class="fw-semibold"><t t-out="financial_year"/>(<t t-out="fy_date_start"/> to <t t-out="fy_date_end"/>)</span>
                                                </div>
                                            </div>
                                        </div>
                                </table>

                                <t t-if="last_declaration">
                                    <table class="tds-kpi-grid">
                                        <tr>
                                            <td class="tds-kpi">
                                                <div class="tds-kpi-label">Total Tax to be Paid</div>
                                                <div class="tds-kpi-value">
                                                    <span t-out="last_declaration['formatted_values']['total_tds_tobe_paid']"/>
                                                </div>
                                            </td>
                                            <td class="tds-kpi">
                                                <div class="tds-kpi-label">Total Tax Paid</div>
                                                <div class="tds-kpi-value">
                                                    <span t-out="last_declaration['formatted_values']['already_paid_tds']"/>
                                                </div>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td class="tds-kpi">
                                                <div class="tds-kpi-label">Remaining Tax</div>
                                                <div class="tds-kpi-value">
                                                    <span t-out="last_declaration['formatted_values']['remaining_tds']"/>
                                                </div>
                                            </td>
                                            <td class="tds-kpi">
                                                <div class="tds-kpi-label">
                                                    <t t-out="last_declaration['schedule_label']"/> Tax (from <t t-out="last_declaration['contract_date_start']"/>)
                                                </div>
                                                <div class="tds-kpi-value text-success">
                                                    <span t-out="last_declaration['formatted_values']['expected_tds']"/>
                                                </div>
                                            </td>
                                        </tr>
                                    </table>
                                </t>
                                <div class="mt-3">
                                    <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
                                        <div class="fw-semibold text-muted small">Contract Timeline (Total Tax to be Paid)</div>
                                        <div class="text-muted small"><t t-out="contract_count"/> contract(s) (<t t-out="version_count"/> employee records)</div>
                                    </div>
                                    <div class="tds-pill-row">
                                        <t t-foreach="declarations" t-as="declaration">
                                            <span
                                                t-attf-class="tds-pill {{ 'tds-pill-ended' if declaration['contract_date_end'] else 'tds-pill-active' }}"
                                                t-att-title="
                                                    (declaration['contract_date_end']
                                                        and (declaration['contract_date_start'] + ' to ' + declaration['contract_date_end'])
                                                        or ('Since ' + declaration['contract_date_start'])
                                                    )
                                                "
                                            >
                                                <span class="tds-pill-name" t-out="declaration['display_name'] or 'N/A'"/>
                                                <span class="tds-pill-sep" aria-hidden="true"></span>
                                                <span class="tds-pill-amt" t-out="declaration['formatted_values']['total_tds_tobe_paid']"/>
                                            </span>
                                        </t>
                                    </div>
                                </div>
                            </td>
                        </tr>
                    </table>

                    <div class="tds-declaration-details">
                        <table class="table table-sm tds-declaration-table" border="0">
                            <thead>
                                <tr class="details-header">
                                    <th class="fw-bold">Details</th>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <th t-out="declaration['display_name'] or 'N/A'"
                                            style="text-align: right; font-weight: 700;"/>
                                    </t>
                                </tr>
                                <tr class="section-title"><td colspan="100">Gross Income</td></tr>
                            </thead>
                            <tbody class="keep">
                                <tr>
                                    <td>Income From Salary</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['total_income']" class="text-end"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td>Income from Previous Employment</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['income_previous_employment']" class="text-end"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td>Income from Other Sources</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['income_from_other_sources']" class="text-end"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td>Income From Let Out Property</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['income_let_out_property']" class="text-end"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td>Interest Earned from Savings Deposit &amp; FD</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['interest_fd_deposit']" class="text-end"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td>Interest Earned from National Savings Certificates</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['interest_national_savings']" class="text-end"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td>Total Gross Income</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['final_income']" class="text-end"/>
                                    </t>
                                </tr>
                            </tbody>

                            <thead>
                                <tr class="section-title"><td colspan="100">Exemptions</td></tr>
                            </thead>
                            <tbody class="keep">
                                <tr>
                                    <td>Standard Deduction</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['standard_deduction']" class="text-end"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td>Conveyance Allowance</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['conveyance_allowance']" class="text-end"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td>80CCD for contributions to the NPS/NPS Vatsalya</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['contribution_nps']" class="text-end"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td>Total Exemption</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['total_exemption']" class="text-end"/>
                                    </t>
                                </tr>
                            </tbody>

                            <thead>
                                <tr class="section-title"><td colspan="100">TDS Computation</td></tr>
                            </thead>
                            <tbody class="keep">
                                <tr>
                                    <td>Total Gross Income</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['final_income']" class="text-end"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td>Total Exemption</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['total_exemption']" class="text-end"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td>Taxable Income</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['taxable_income']" class="text-end"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td>Tax on Taxable Income</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['tax_on_taxable_income']" class="text-end"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td>Rebate Under Section 87A(a)</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['rebate']" class="text-end"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td>Total Tax on Income</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['total_tax_on_income']" class="text-end"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td>Surcharge</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['surcharge']" class="text-end"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td>Health and Education Cess</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['cess']" class="text-end"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td>Total Tax to be Paid</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['total_tds_tobe_paid']" class="text-end"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td>Tax paid by previous employer</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['tax_paid_previous_employer']" class="text-end"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td class="fw-bold">Total Tax Paid (Current Contract)</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['current_version_paid_tds']" class="text-end fw-bold"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td class="fw-bold">Total Tax Paid</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['already_paid_tds']" class="text-end fw-bold"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td class="fw-bold">Total Tax Remaining</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['remaining_tds']" class="text-end fw-bold"/>
                                    </t>
                                </tr>
                                <tr>
                                    <td><t t-out="last_declaration['schedule_label']"/> TDS Payable</td>
                                    <t t-foreach="declarations" t-as="declaration">
                                        <td t-out="declaration['formatted_values']['expected_tds']" class="text-end"/>
                                    </t>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </t>
        </t>
    </template>

    <record id="action_report_tax_declaration_history" model="ir.actions.report">
        <field name="name">Tax Declaration</field>
        <field name="model">hr.employee</field>
        <field name="report_name">l10n_in_hr_payroll.tax_declaration_history</field>
        <field name="paperformat_id" ref="paperformat_tax_declaration_compact"/>
        <field name="report_type">qweb-pdf</field>
    </record>
</odoo>

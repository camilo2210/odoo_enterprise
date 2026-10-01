<?xml version="1.0" encoding="UTF-8"?>
<odoo>
    <!-- Add the report variant -->
    <record id="romanian_ec_sales_report" model="account.report">
        <field name="name">Romanian EC Sales List (D390)</field>
        <field name="name@ro">Listă de vânzări CE din România (D390)</field>
        <field name="country_id" ref="base.ro"/>
        <field name="root_report_id" ref="account_reports.generic_ec_sales_report"/>
        <field name="load_more_limit" eval="80"/>
        <field name="search_bar" eval="True"/>
        <field name="filter_journals" eval="True"/>
        <field name="custom_handler_model_id" ref="model_l10n_ro_ec_sales_report_handler"/>
        <field name="column_ids">
            <record id="account_financial_report_ec_sales_country" model="account.report.column">
                <field name="name">Country Code</field>
                <field name="name@ro">Cod țară</field>
                <field name="expression_label">country_code</field>
                <field name="figure_type">string</field>
                <field name="sortable" eval="True"/>
            </record>
            <record id="account_financial_report_ec_sales_vat" model="account.report.column">
                <field name="name">VAT Number</field>
                <field name="name@ro">Număr de TVA</field>
                <field name="expression_label">vat_number</field>
                <field name="figure_type">string</field>
                <field name="sortable" eval="True"/>
            </record>
            <record id="account_financial_report_ec_sales_tax" model="account.report.column">
                <field name="name">Code</field>
                <field name="name@ro">Cod</field>
                <field name="expression_label">sale_type_shortcut</field>
                <field name="figure_type">string</field>
                <field name="sortable" eval="True"/>
            </record>
            <record id="account_financial_report_ec_sales_amount" model="account.report.column">
                <field name="name">Amount</field>
                <field name="name@ro">Sumă</field>
                <field name="expression_label">balance</field>
                <field name="sortable" eval="True"/>
            </record>
        </field>
        <field name="line_ids">
            <record id="ro_ec_sales_report_line" model="account.report.line">
                <field name="name">EC Sales Report</field>
                <field name="name@ro">Raport de vânzări CE</field>
                <field name="code">RO_EC</field>
                <field name="groupby">partner_id_and_sale_type</field>
                <field name="foldability">always_unfolded</field>
                <field name="expression_ids">
                    <record id="ro_ec_sales_report_line_country_code" model="account.report.expression">
                        <field name="label">country_code</field>
                        <field name="engine">custom</field>
                        <field name="auditable">True</field>
                        <field name="formula">_report_engine_ec_sales_report</field>
                        <field name="subformula">country_code</field>
                    </record>
                    <record id="ro_ec_sales_report_line_vat_number" model="account.report.expression">
                        <field name="label">vat_number</field>
                        <field name="engine">custom</field>
                        <field name="auditable">True</field>
                        <field name="formula">_report_engine_ec_sales_report</field>
                        <field name="subformula">vat_number</field>
                    </record>
                    <record id="ro_ec_sales_report_line_sale_type_shortcut" model="account.report.expression">
                        <field name="label">sale_type_shortcut</field>
                        <field name="engine">custom</field>
                        <field name="auditable">True</field>
                        <field name="formula">_report_engine_ec_sales_report</field>
                        <field name="subformula">sale_type_shortcut</field>
                    </record>
                    <record id="ro_ec_sales_report_line_balance" model="account.report.expression">
                        <field name="label">balance</field>
                        <field name="engine">custom</field>
                        <field name="auditable">True</field>
                        <field name="formula">_report_engine_ec_sales_report</field>
                        <field name="subformula">balance</field>
                    </record>
                </field>
            </record>
        </field>
    </record>
</odoo>

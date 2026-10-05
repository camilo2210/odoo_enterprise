<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="1">
        <record id="l10n_mx_mail_template_new_payslip" model="mail.template">
            <field name="name">Payroll: New Payslip Document</field>
            <field name="model_id" ref="hr_payroll.model_hr_payslip"/>
            <field name="subject">{{ object.employee_id.name }}, a new payslip is available for you</field>
            <field name="email_from">{{ user.email_formatted }}</field>
            <field name="email_to">{{ object.employee_id.private_email or object.employee_id.work_email }}</field>
            <field name="use_default_to" eval="False"/>
            <field name="description">Sent to employee to notify them about their new payslip</field>
            <field name="body_html" type="html">
    <table border="0" cellpadding="0" cellspacing="0" style="width:100%; margin:0px auto;"><tbody>
        <t t-set="document_access_link" t-value="object.document_access_url"/>
        <t t-set="cfdi_access_link" t-value="object.l10n_mx_edi_cfdi_access_url"/>
        <tr><td valign="top" style="text-align: left; font-size: 14px;">
            Dear <t t-out="object.employee_id.name"></t>, a new payslip is available for you.<br/><br/>
            <t t-if="object.employee_id.user_id">Please find the PDF in your employee portal.<br/><br/></t>
            <div style="text-align: center; padding: 16px 0px 16px 0px; font-size: 14px;">
                <a t-if="document_access_link"
                    t-attf-href="{{ document_access_link }}"
                    target="_blank"
                    style="background-color: #875A7B; padding: 8px 16px 8px 16px; text-decoration: none; color: #fff; border-radius: 5px; font-size:13px;">
                    Your Payslip
                </a>
                <a t-if="cfdi_access_link"
                    t-attf-href="{{ cfdi_access_link }}"
                    target="_blank"
                    style="background-color: #875A7B; margin-left: 10px; padding: 8px 16px 8px 16px; text-decoration: none; color: #fff; border-radius: 5px; font-size:13px;">
                    Your CFDI
                </a>
            </div>
            Have a nice day,<br/>
            The HR Team
        </td></tr>
    </tbody></table>
                </field>
                <field name="lang">{{ object.employee_id.lang }}</field>
                <field name="auto_delete" eval="True"/>
        </record>
    </data>
</odoo>

import ast
import datetime
import json
import uuid
from collections import defaultdict
from markupsafe import Markup
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import Command, _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import AccessError, RedirectWarning, UserError, ValidationError
from odoo.fields import Domain
from odoo.tools import SQL, date_utils, html2plaintext
from odoo.tools.misc import format_date
from odoo.tools.translate import LazyTranslate, LazyGettext
from odoo.addons.account.models.account_move import REVIEW_STATE_SELECTION
from ast import literal_eval

_lt = LazyTranslate(__name__)


PERIODS = [
    ('monthly', 'Monthly'),
    ('2_months', 'Every 2 months'),
    ('trimester', 'Quarterly'),
    ('4_months', 'Every 4 months'),
    ('semester', 'Semi-annually'),
    ('year', 'Annually'),
    ('fiscalyear', 'Fiscal Year'),
]

MONTHS_PER_PERIOD = {
    'year': 12,
    'semester': 6,
    '4_months': 4,
    'trimester': 3,
    '2_months': 2,
    'monthly': 1,
}

CHECK_TYPES = [
    ('check', "Check"),
    ('file', "Upload Document"),
]

LIMIT_CHECK_ENTRIES = 21


def check_company_domain_account_return(self, companies):
    company_ids = models.to_record_ids(companies)
    if not companies:
        return [('company_ids', '=', False)]

    return [('company_ids', 'in', company_ids)]


class AccountReturnType(models.Model):
    _name = "account.return.type"
    _inherit = ['mail.thread']
    _description = "Accounting Return Type"

    name = fields.Char(string="Name", required=True, translate=True, tracking=True)
    category = fields.Selection(
        string="Type",
        selection=[
            ('account_return', "Tax Return"),
            ('audit', "Audit"),
        ],
        default='account_return',
        required=True,
        tracking=True,
    )
    active = fields.Boolean(compute="_compute_active", compute_sql="_compute_sql_active", inverse="_inverse_active", compute_sudo=True)
    active_fallback = fields.Boolean(default=True)
    # In this case we need a selection field because in DB a False boolean is just not set, in this case we need a differenciation of Null an False
    active_selection = fields.Selection(
        selection=[
            ('False', "False"),
            ('True', "True"),
        ],
        company_dependent=True,
    )
    report_id = fields.Many2one(string="Report", comodel_name='account.report', index='btree', tracking=True)
    is_tax_return_type = fields.Boolean(string="Is a Tax Return Return Type", compute="_compute_report_return_type")
    is_ec_sales_list_return_type = fields.Boolean(string="Is an EC Sales List Return Type", compute="_compute_report_return_type")

    auto_generate = fields.Boolean(string="Auto Generated", compute='_compute_auto_generate', copy=False, readonly=False, store=True)
    country_id = fields.Many2one(comodel_name='res.country', string="Country", tracking=True, store=True, compute="_compute_country_id", readonly=False)
    payment_partner_id = fields.Many2one(comodel_name='res.partner', string="Payment Partner",
        tracking=True, domain="[('parent_id', '=', False)]")
    payment_partner_bank_id = fields.Many2one(
        comodel_name='res.partner.bank', string="Payment Partner Bank", tracking=True,
        compute='_compute_payment_partner_bank_id', inverse="_inverse_payment_partner_bank_id",
        store=True, readonly=False, domain="[('partner_id', '=', payment_partner_id)]"
    )
    tax_closing_rounding_profit_account_id = fields.Many2one(
        comodel_name='account.account',
        string="Tax Closing Rounding Profit Account",
        company_dependent=True,
        help="Account on which a rounding gain of the tax closing entry is posted.",
    )
    tax_closing_rounding_loss_account_id = fields.Many2one(
        comodel_name='account.account',
        string="Tax Closing Rounding Loss Account",
        company_dependent=True,
        help="Account on which a rounding loss of the tax closing entry is posted.",
    )
    states_workflow = fields.Selection(
        selection=[
            ('generic_state_review', "Reviewed"),
            ('generic_state_review_submit', "Reviewed, Submitted"),
            ('generic_state_tax_report', "Reviewed, Submitted, Paid"),
            ('generic_state_only_pay', "Paid"),
        ],
        string="States",
        help="Determines the workflow of the return.",
        compute="_compute_states_workflow",
        readonly=False,
        store=True,
        required=True,
        precompute=True,
    )

    deadline_periodicity = fields.Selection(
        selection=PERIODS,
        string="Periodicity",
        tracking=True,
        company_dependent=True,
    )
    default_deadline_periodicity = fields.Selection(selection=PERIODS, string="Default Periodicity")
    deadline_start_date = fields.Date(
        string="Start Date",
        help="Used to compute covered period based on the selected periodicity.",
        tracking=True,
        company_dependent=True,
    )
    default_deadline_start_date = fields.Date(string="Default Start Date")
    deadline_days_delay = fields.Integer(
        string="Deadline",
        help="By default, Odoo applies its own deadline for returns (shown as 0). Entering a value here will override it and be used as the new deadline.",
        tracking=True,
        company_dependent=True,
    )
    default_deadline_days_delay = fields.Integer(string="Default Deadline")
    company_advance_tax_payment_account_id = fields.Many2one(
        comodel_name='account.account',
        company_dependent=True,
        check_company=True,
        ondelete='restrict',
    )
    company_tax_payable_account_id = fields.Many2one(
        comodel_name='account.account',
        company_dependent=True,
        check_company=True,
        ondelete='restrict',
    )
    company_tax_receivable_account_id = fields.Many2one(
        comodel_name='account.account',
        company_dependent=True,
        check_company=True,
        ondelete='restrict',
    )
    advance_tax_payment_account_id = fields.Many2one(
        comodel_name='account.account',
        string="Advance Account",
        compute=lambda self: self._compute_closing_account('advance_tax_payment_account_id'),
        depends=['company_advance_tax_payment_account_id'],
        depends_context=('company',),
        compute_sql=lambda self, table: self._compute_sql_closing_account(table, 'advance_tax_payment_account_id'),
        inverse=lambda self: self._inverse_closing_account('advance_tax_payment_account_id'),
        compute_sudo=True,
        help="Downpayments posted on this account will be considered by the Tax Closing Entry.",
    )
    tax_payable_account_id = fields.Many2one(
        comodel_name='account.account',
        string="Payable Account",
        compute=lambda self: self._compute_closing_account('tax_payable_account_id'),
        depends=['company_tax_payable_account_id'],
        depends_context=('company',),
        compute_sql=lambda self, table: self._compute_sql_closing_account(table, 'tax_payable_account_id'),
        inverse=lambda self: self._inverse_closing_account('tax_payable_account_id'),
        compute_sudo=True,
        domain="[('account_type', '=', 'liability_payable'), ('non_trade', '=', True)]",
        help="Tax current account used as a counterpart to the Tax Closing Entry when in favor of the authorities.",
    )
    tax_receivable_account_id = fields.Many2one(
        comodel_name='account.account',
        string="Receivable Account",
        compute=lambda self: self._compute_closing_account('tax_receivable_account_id'),
        depends=['company_tax_receivable_account_id'],
        depends_context=('company',),
        compute_sql=lambda self, table: self._compute_sql_closing_account(table, 'tax_receivable_account_id'),
        inverse=lambda self: self._inverse_closing_account('tax_receivable_account_id'),
        compute_sudo=True,
        domain="[('account_type', '=', 'asset_receivable'), ('non_trade', '=', True)]",
        help="Tax current account used as a counterpart to the Tax Closing Entry when in favor of the company.",
    )
    tax_closing_account_placeholder = fields.Char(compute="_compute_tax_closing_account_placeholder")
    is_master_data = fields.Boolean(compute="_compute_is_master_data")
    is_country_in_active_country = fields.Boolean(string="Is Country Fiscal Active", compute_sql='_compute_sql_is_country_in_active_country', compute='_compute_is_country_in_active_country', compute_sudo=False)

    @api.model_create_multi
    def create(self, vals_list):
        self._check_no_active_use_in_data_files(vals_list)

        return_types = super().create(vals_list)

        all_companies = self.env['res.company'].sudo().search([])
        return_types.sudo()._set_default_values(all_companies)

        return return_types

    def _load_records(self, data_list, update=False):
        return_types = super()._load_records(data_list, update=update)

        all_companies = self.env['res.company'].sudo().search([])
        for company in all_companies:
            if not company.vat_disabled:
                continue
            company._toggle_account_return_types_on_vat_disabled(return_types)

        return return_types

    @api.model
    def _check_no_active_use_in_data_files(self, vals_list):
        """ account.return.type's active field should never be directly written to in data files. If someone does that, only the active company
        will receive the data, as a company-dependent value in active_selection. To prevent mistakes (especially with forward-ports),
        this check is called in write() and create(), making sure active isn't used in the provided values when a module is being installed.
        """
        if install_filename := self.env.context.get('install_filename'):
            if any('active' in vals for vals in vals_list):
                raise UserError(_(
                    "'active' field of account.return.type shouldn't be directly written to in data files. Use active_fallback. (Detected while loading %(file_path)s)",
                    file_path=install_filename,
                ))

    @api.depends_context('company_id')
    @api.depends('active_selection', 'active_fallback')
    def _compute_active(self):
        for record in self:
            record.active = record.active_selection == 'True' if record.active_selection else record.active_fallback

    def _compute_sql_active(self, table):
        return SQL("COALESCE(%s = 'True', %s)", table.active_selection, table.active_fallback)

    @api.depends_context('company')
    def _compute_is_country_in_active_country(self):
        for record in self:
            record.is_country_in_active_country = record.country_id in self.env.company.account_enabled_tax_country_ids

    def _compute_sql_is_country_in_active_country(self, table):
        return SQL("country_id IN %s", tuple(self.env.company.account_enabled_tax_country_ids.ids))

    @api.onchange('active')
    def _inverse_active(self):
        for record in self:
            record.active_selection = str(bool(record.active))

    @api.depends('payment_partner_id')
    def _compute_payment_partner_bank_id(self):
        banks_by_partner = dict(self.env['res.partner.bank']._read_group(
            domain=[('partner_id', 'in', self.payment_partner_id.ids)],
            groupby=['partner_id'],
            aggregates=['id:array_agg'],
        ))

        for return_type in self:
            bank_ids = banks_by_partner.get(return_type.payment_partner_id, [])
            return_type.payment_partner_bank_id = bank_ids[0] if len(bank_ids) == 1 else False

    def _inverse_payment_partner_bank_id(self):
        for return_type in self:
            if return_type.payment_partner_bank_id:
                return_type.payment_partner_id = return_type.payment_partner_bank_id.partner_id

    def _set_default_values(self, companies):
        for company in companies:
            for return_type in self.with_company(company):
                return_type.deadline_periodicity = return_type.deadline_periodicity or return_type.default_deadline_periodicity
                return_type.deadline_start_date = return_type.deadline_start_date or return_type.default_deadline_start_date
                return_type.deadline_days_delay = return_type.deadline_days_delay or return_type.default_deadline_days_delay

    @api.depends('report_id')
    def _compute_report_return_type(self):
        tax_report = self.env.ref('account.generic_tax_report')
        generic_ec_sales_report = self.env.ref('account_reports.generic_ec_sales_report')
        for record in self:
            report = record.report_id
            record.is_tax_return_type = report and tax_report in (report, report.root_report_id)
            record.is_ec_sales_list_return_type = report and generic_ec_sales_report in (report, report.root_report_id)

    def _compute_closing_account(self, field_name):
        """ The accounts belong to the company tree root rather than to the individual branch."""
        for return_type in self:
            return_type[field_name] = return_type.with_company(self.env.company.root_id)[f'company_{field_name}']

    def _inverse_closing_account(self, field_name):
        """ Store the edit on the company tree's root, where _compute_closing_account reads it back."""
        for return_type in self:
            return_type.with_company(self.env.company.root_id).sudo()[f'company_{field_name}'] = return_type[field_name]

    def _compute_sql_closing_account(self, table, field_name):
        """Compute the root company closing account value in sql."""
        table = table._with_model(self.with_company(self.env.company.root_id))
        return table[f'company_{field_name}']

    @api.depends('is_tax_return_type')
    def _compute_tax_closing_account_placeholder(self):
        for return_type in self:
            return_type.tax_closing_account_placeholder = False if return_type.is_tax_return_type else self.env._("No closing entry")

    @api.depends('report_id.country_id')
    def _compute_country_id(self):
        for return_type in self:
            return_type.country_id = return_type.report_id.country_id if not return_type.country_id and return_type.report_id.country_id else return_type.country_id

    @api.constrains('country_id')
    def _constrains_country_id(self):
        for return_type in self:
            if return_type.report_id.country_id and return_type.report_id.country_id != return_type.country_id:
                raise ValidationError(_("The return type country must be the same as the report country"))

    @api.constrains('company_tax_payable_account_id', 'company_tax_receivable_account_id')
    def _constrains_payable_receivable_account(self):
        for return_type in self:
            payable = return_type.company_tax_payable_account_id
            receivable = return_type.company_tax_receivable_account_id
            if payable and payable.account_type != 'liability_payable':
                raise ValidationError(self.env._("You must select a payable account for 'Tax Payable Account'."))
            if receivable and receivable.account_type != 'asset_receivable':
                raise ValidationError(self.env._("You must select a receivable account for 'Tax Receivable Account'."))
            if (payable and not payable.non_trade) or (receivable and not receivable.non_trade):
                raise ValidationError(self.env._("You must use non-trade accounts for tax returns."))

    @api.depends('category')
    def _compute_auto_generate(self):
        for return_type in self:
            return_type.auto_generate = return_type.category == 'account_return'

    @api.depends('report_id', 'category')
    def _compute_states_workflow(self):
        for return_type in self:
            if return_type.is_ec_sales_list_return_type:
                return_type.states_workflow = 'generic_state_review_submit'
            elif return_type.category == 'audit':
                return_type.states_workflow = 'generic_state_review'
            elif return_type.is_tax_return_type:
                return_type.states_workflow = 'generic_state_tax_report'
            else:
                return_type.states_workflow = 'generic_state_review'

    def _compute_is_master_data(self):
        xml_id = self.get_external_id()
        for record in self:
            record.is_master_data = bool(xml_id.get(record.id))

    def write(self, vals):
        self._check_no_active_use_in_data_files([vals])

        if 'active' in vals:
            self.report_id.active = vals['active']

            for return_type in self:
                self._generate_or_refresh_all_returns(self.env.company, return_type)

        if new_states_workflow := vals.get('states_workflow'):
            self.env['account.return'].flush_model()

            for record in self.filtered(lambda r: r.states_workflow and r.states_workflow != new_states_workflow):
                orig_terminal_state = self.env['account.return']._fields[record.states_workflow].selection[-1][0]
                new_terminal_state = self.env['account.return']._fields[new_states_workflow].selection[-1][0]
                allowed_new_states = {new_state for new_state, _dummy in self.env['account.return']._fields[new_states_workflow].selection}

                need_to_force_terminal_sql = SQL(
                    "state = %(orig_terminal_state)s AND NOT(is_completed AND (state IN %(allowed_new_states)s OR state IS NULL))",
                    orig_terminal_state=orig_terminal_state,
                    allowed_new_states=tuple(allowed_new_states),
                )

                self.env.cr.execute(SQL(
                    """
                        WITH updated_states AS (
                            UPDATE account_return
                            SET
                                %(new_states_workflow)s = CASE
                                    WHEN %(need_to_force_terminal_sql)s
                                        THEN %(new_terminal_state)s
                                    ELSE
                                        state
                                    END,
                                state = CASE
                                    WHEN %(need_to_force_terminal_sql)s
                                        THEN %(new_terminal_state)s
                                    ELSE
                                        state
                                    END,
                                %(old_states_workflow)s = NULL,
                                is_completed=is_completed OR (%(need_to_force_terminal_sql)s) OR state = %(new_terminal_state)s
                            WHERE
                                type_id = %(type_id)s
                            RETURNING state
                        )

                        SELECT DISTINCT state
                        FROM updated_states
                    """,
                    type_id=record.id,
                    need_to_force_terminal_sql=need_to_force_terminal_sql,
                    new_states_workflow=SQL.identifier(new_states_workflow),
                    old_states_workflow=SQL.identifier(record.states_workflow),
                    new_terminal_state=new_terminal_state,
                ))

                states = self.env.cr.fetchall()
                if any(state not in allowed_new_states | {None} for (state,) in states):
                    raise UserError(self.env._(
                        "Some returns made for return type '%s' keep an inconsistent state after changing the workflow. "
                        "This likely comes from a missing upgrade script.",
                        record.name
                    ))

                self.env['account.return']._invalidate_cache(fnames=[record.states_workflow, new_states_workflow, 'is_completed', 'state'])

        return super().write(vals)

    def _can_return_exist(self, company, tax_unit=False):
        """ Returns whether a return can exist for this type with the provided company and tax units. This is used to know which returns need
        to be deleted when a change of configuration has occurred.
        """
        is_foreign_vat = self.report_id and company.account_fiscal_country_id.code != self.report_id.country_id.code

        is_tax_unit_main_comp = not tax_unit or tax_unit.main_company_id == company

        all_branch_companies_with_same_vat = company._get_branches_with_same_vat()
        sorted_branch_companies_with_same_vat = sorted(all_branch_companies_with_same_vat, key=lambda comp: len(comp.parent_path.split('/')))
        is_main_branch = not company.parent_id or company == sorted_branch_companies_with_same_vat[0]

        return is_foreign_vat or (is_tax_unit_main_comp and is_main_branch)

    @api.model
    def _cron_generate_or_refresh_all_returns(self):
        now = fields.Datetime.now()
        date_upper_bound = now - relativedelta(days=1)  # -1 day to cope for precision
        root_companies = self.env['res.company'].sudo().search([
            ('parent_id', '=', False),
            ('account_opening_date', '!=', False),
            '|', ('account_last_return_cron_refresh', '=', False), ('account_last_return_cron_refresh', '<', date_upper_bound),
        ], limit=2)

        if root_companies:
            to_treat = root_companies[0]
            self._generate_or_refresh_all_returns(to_treat)
            to_treat.account_last_return_cron_refresh = now

            if len(root_companies) > 1:
                cron = self.env.ref('account_reports.ir_cron_generate_account_return')
                cron._trigger()

            else:
                self._send_submission_reminder()

    @api.model
    def _send_submission_reminder(self):
        if not (mail_template := self.env.ref('account_reports.email_template_tax_return_deadline', raise_if_not_found=False)):
            return

        returns_to_submit = self.env['account.return'].search([
            ('state', 'not in', ('submitted', 'paid')),
            ('date_deadline', '=', fields.Date.context_today(self) + relativedelta(days=7)),
        ]).filtered('is_tax_return')
        for account_return in returns_to_submit:
            for user in self.env.ref('account.group_account_manager').user_ids.filtered(lambda user: set(user.company_ids) & set(account_return.company_ids)):
                mail_template.with_context(partner=user.partner_id).send_mail(account_return.id)

    @api.model
    def _generate_or_refresh_all_returns(self, root_companies, return_types=None):
        """
        Generates or update all returns for every companies
        It calls _generate_all_returns which can be overridden to add new return types.
        the _generate_all_returns function is called for every root companies, non domestic tax units and for every foreign_vat fpos

        At the end it tries to delete returns that should not exists anymore due to configuration changes
        """
        root_companies = root_companies.filtered(lambda x: x.account_opening_date)
        if not root_companies:
            return

        all_tax_units_root_domain = [('company_ids', 'child_of', root_companies.ids)]
        all_tax_units = self.env['account.tax.unit'].sudo().search([*all_tax_units_root_domain])

        all_domestic_tax_units = self.env['account.tax.unit']
        for company in root_companies:
            fiscal_country = company.account_fiscal_country_id
            domestic_tax_unit = all_tax_units.filtered(lambda x: x.country_id == fiscal_country and company in x.company_ids)  # At most 1
            self._generate_all_returns(fiscal_country.code, company, tax_unit=domestic_tax_unit, return_types=return_types)
            all_domestic_tax_units += domestic_tax_unit

        for tax_unit in (all_tax_units - all_domestic_tax_units):
            self._generate_all_returns(tax_unit.country_id.code, tax_unit.main_company_id, tax_unit, return_types)

        # Create returns for foreign VAT fiscal positions
        fpos_root_company_domain = [('company_id', 'child_of', root_companies.ids)]
        all_foreign_vat_fpos = self.env['account.fiscal.position'].sudo().search([('foreign_vat', '!=', False), *fpos_root_company_domain])
        for company, fiscal_positions in all_foreign_vat_fpos.grouped(lambda x: x.company_id).items():
            for country_code in {fpos.country_id.code for fpos in fiscal_positions}:
                self._generate_all_returns(country_code, company, None, return_types)

        # Post generation -> we need to vacuum all returns that should not exist anymore
        return_root_company_domain = [('company_ids', 'in', root_companies.ids)]
        all_return_that_might_be_deleted = self.env['account.return'].sudo().search([
            ('date_lock', '=', False),
            ('is_completed', '=', False),
            ('manually_created', '=', False),
            *return_root_company_domain,
        ])
        returns_to_unlink = self.env['account.return']
        for return_to_check in all_return_that_might_be_deleted:
            if (
                not return_to_check.company_id.account_opening_date
                or not return_to_check.type_id._can_return_exist(return_to_check.company_id, return_to_check.tax_unit_id)
                or return_to_check.date_deadline < return_to_check.company_id.account_opening_date
            ):
                returns_to_unlink |= return_to_check
        returns_to_unlink.sudo().unlink()

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None, return_types=None):
        """
        Hook to override to enable the generation of new return types.

        :param country_code: the country code for which we want to generate returns. It can be fpos country_code or main_company country_code
        :param main_company: the main company for which we generate returns
        """

        # Generate ec sales reports
        generic_ec_sales_report = self.env.ref('account_reports.generic_ec_sales_report')
        ec_sales_return_type = self.env['account.return.type'].search(
            [
                ('country_id.code', '=', country_code),
                ('auto_generate', '=', False),
                '|', ('report_id.root_report_id', '=', generic_ec_sales_report.id), ('report_id', '=', generic_ec_sales_report.id)
            ]
        )
        if ec_sales_return_type:
            self._generate_ec_sales_returns(main_company, tax_unit, ec_sales_return_type)

        if self.env.context.get('only_refresh_conditional_types'):
            return

        if main_company.sudo().account_fiscal_country_id.code == country_code:
            search_domain = Domain.AND([
                Domain('auto_generate', '=', True),
                Domain.OR([
                    Domain('country_id', '=', False),
                    Domain('country_id.code', '=', country_code),
                ])
            ])
        else:
            # For foreign vat we want to search strictly on country as the others without country should already be generated
            search_domain = Domain.AND([
                Domain('country_id.code', '=', country_code),
                Domain('auto_generate', '=', True)
            ])
        if return_types:
            search_domain = Domain.AND([
                search_domain,
                Domain('id', 'in', return_types.ids)
            ])
        for return_type_to_generate in self.env['account.return.type'].sudo().with_company(main_company).search(search_domain):
            return_type_to_generate._try_create_returns_for_fiscal_year(main_company, tax_unit=tax_unit)

    @api.onchange('category')
    def _onchange_category(self):
        for return_type in self:
            if return_type.category == 'audit':
                return_type.with_company(self.env.company).deadline_periodicity = 'year'

    def _try_create_returns_for_fiscal_year(self, main_company, tax_unit, allow_duplicates=False, bypass_period_check=False):
        """
        Creates or updates the tax returns (possibly deleting the 'new' ones, if needed) for the provided main_company and tax_unit, so that all the
        returns are created from the start of the current fiscal year, up to one year after the current date.

        This functions runs multiple operations in sudo(), and updates all the companies of the database. It is important in order to handle more
        complex configuration changes, where branches or tax units structure would have been modified.

        forced_date_from and forced_date_to can be specified to generate returns only in a specific time interval.
        Either both must be specified or none.
        """
        self.ensure_one()
        if self.report_id.filter_multi_company != 'tax_units':
            tax_unit = False

        today = datetime.date.today()
        next_year = today + relativedelta(years=1)

        has_forced_dates = self.env.context.get('forced_date_from') and self.env.context.get('forced_date_to')
        if has_forced_dates:
            date_from = fields.Date.from_string(self.env.context['forced_date_from'])
            date_to = fields.Date.from_string(self.env.context['forced_date_to'])
        else:
            date_from = today - relativedelta(years=1)
            date_to = today

        if not self._can_return_exist(main_company, tax_unit):
            returns_to_unlink = self.env['account.return'].sudo().search([
                ('company_id', '=', main_company.id),
                ('date_lock', '=', False),
                ('is_completed', '=', False),
                ('type_id', '=', self.id),
                ('date_to', '>=', date_from),
                ('date_from', '<=', date_to),
                ('manually_created', '=', False),
            ])
            returns_to_unlink.sudo().unlink()
            return

        # We do not want to traverse children if we are using a tax_unit or using a fiscal_position
        if not tax_unit and not main_company.parent_id and main_company.child_ids:
            # Also create returns for the branch sub-trees with different VAT numbers as main_company
            other_main_companies = self.env['res.company']
            to_treat = [(main_company.vat, main_company)]
            while to_treat:
                (vat_from_parent, current_company) = to_treat.pop()

                for child_company in current_company.child_ids:
                    if child_company.vat and child_company.vat != vat_from_parent and child_company.account_return_periodicity and child_company.account_return_reminder_day:
                        other_main_companies |= child_company
                    to_treat.append((child_company.vat, child_company))

            for other_main_company in other_main_companies:
                if other_main_company.account_opening_date:
                    self._try_create_returns_for_fiscal_year(other_main_company, tax_unit)

        expected_companies = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, self.report_id)
        date_pointer = date_from
        periods = []
        deadline_date = date_pointer
        type_xml_id = self.get_external_id()[self.id]
        if self.env.context.get('force_periodicity_violation'):
            periods.append((date_from, date_to))
        else:
            while date_pointer < date_to and (deadline_date <= next_year or bypass_period_check):
                period_date_from, period_date_to = self._get_period_boundaries(main_company, date_pointer)
                deadline_date = self.env['account.return']._evaluate_deadline(main_company, self, type_xml_id, period_date_from, period_date_to)
                if (main_company.account_opening_date or date.min) <= deadline_date <= next_year or bypass_period_check:
                    periods.append((period_date_from, period_date_to))
                date_pointer = period_date_to + relativedelta(days=1)

        existing_returns = self.env['account.return'].sudo().with_context(active_test=False).search([
            ('company_id', '=', main_company.id),  # We don't want to use the check_company_domain here
            ('type_id', '=', self.id),
            ('date_to', '>=', date_from),
            ('date_from', '<=', date_to),
        ])
        if existing_returns and not allow_duplicates:
            existing_periods = {(account_return.date_from, account_return.date_to): self.env['account.return'].sudo() for account_return in existing_returns}
            for account_return in existing_returns:
                existing_periods[account_return.date_from, account_return.date_to] |= account_return
            same_periods = set(periods) & set(existing_periods.keys())

            # For existing period that won't be changed, we check the company structure
            for same_period in same_periods:
                same_period_returns = existing_periods[same_period]
                for same_period_return in same_period_returns:
                    if same_period_return.company_id == main_company and not same_period_return.is_completed and not same_period_return.date_lock:
                        if same_period_return.tax_unit_id != tax_unit:
                            same_period_return.tax_unit_id = tax_unit
                        elif same_period_return.company_ids != expected_companies:
                            same_period_return.company_ids = expected_companies

            periods = list(set(periods) - same_periods)  # We don't need to create periods that are already created and good
            periods.sort(key=lambda period: period[0])

            # Get the one that are wrong and delete them if possible
            # In case of period switch we need to resolve it
            unmatched_existing_periods = set(existing_periods.keys()) - same_periods
            unmatched_existing_periods_posted_returns = self.env['account.return']
            unmatched_existing_periods_unposted_returns = self.env['account.return']
            for period in unmatched_existing_periods:
                if not existing_periods[period].date_lock and not existing_periods[period].is_completed:
                    unmatched_existing_periods_unposted_returns |= existing_periods[period]
                else:
                    unmatched_existing_periods_posted_returns |= existing_periods[period]

            # We can safely unlink these as they are not posted. We will create new returns for these periods
            unmatched_existing_periods_unposted_returns.filtered(lambda r: not r.manually_created).sudo().unlink()

            # So now we are only left with existing one that cannot be unlinked
            # We should create new returns for periods after the last posted return
            if unmatched_existing_periods_posted_returns:
                most_recent_posted_return = max(unmatched_existing_periods_posted_returns, key=lambda ret: ret.date_to)
                # We need to remove all periods to create where the date_from is less or equal than the most_recent_posted_return date_to
                new_periods = [period for period in periods if period[0] > most_recent_posted_return.date_to]
                periods = new_periods

        # Now we can create those new returns
        create_vals_list = []
        for period_from, period_to in periods:
            create_vals_list.append({
                'name': self._get_return_name(main_company, period_from, period_to),
                'type_id': self.id,
                'company_id': main_company.id,
                'date_from': period_from,
                'date_to': period_to,
                'tax_unit_id': tax_unit.id if tax_unit else False,
                'manually_created': bool(self.env.context.get('manually_created')),
            })

        account_returns = self.env['account.return'].sudo().create(create_vals_list)
        account_returns._update_translated_name()
        return account_returns

    def _try_create_return_for_period(self, date_in_period, main_company, tax_unit, allow_duplicates=False):
        if self.report_id.filter_multi_company != 'tax_units':
            tax_unit = False

        period_start, period_end = self._get_period_boundaries(main_company, date_in_period)
        existing_return = self.env['account.return'].with_context(active_test=False).search([
            *self.env['account.return']._check_company_domain(main_company),
            ('tax_unit_id', '=', tax_unit.id if tax_unit else None),
            ('date_from', '=', period_start),
            ('date_to', '=', period_end),
            ('type_id', '=', self.id),
        ])

        # We should update those companies if they are wrong
        expected_companies = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, self.report_id)
        if existing_return.company_ids != expected_companies:
            existing_return.company_ids = expected_companies

        if not existing_return or allow_duplicates:
            account_return = self.env['account.return'].create([{
                'name': self._get_return_name(main_company, period_start, period_end),
                'date_from': period_start,
                'date_to': period_end,
                'type_id': self.id,
                'company_id': main_company.id,
                'tax_unit_id': tax_unit.id if tax_unit else None,
            }])
            account_return._update_translated_name()

    def _generate_ec_sales_returns(self, main_company, tax_unit, ec_sales_return_type):
        """Generates EC Sales list return for the 3 last months if intracom tags are used"""
        custom_handler = self.env[ec_sales_return_type.report_id._get_custom_handler_model()]
        tax_tags_info = custom_handler._get_ec_sales_tax_tags()
        if tax_tags_info:
            today = fields.Date.context_today(self)
            months_offset = ec_sales_return_type._get_periodicity_months_delay(main_company)
            company_ids = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, ec_sales_return_type.report_id)
            ec_sales_tag_ids = {tax_tag for sale_type in tax_tags_info.values() for tax_tag in sale_type}

            # Generate EC sales returns for the past periods, as well as the current and next one (if data exists).
            ranges = (-1, 4) if months_offset == 1 else (-1, 1)
            periods = [today - relativedelta(months=months_offset * i) for i in range(*ranges)]

            # Map each period to whether it has move lines
            periods_has_move_lines_map = {
                period_bounds: bool(self.env['account.move.line'].search(
                    domain=Domain([
                        ('tax_tag_ids', 'in', ec_sales_tag_ids),
                        ('company_id', 'in', company_ids.ids),
                        ('date', '>=', period_bounds[0]),
                        ('date', '<=', period_bounds[1]),
                        ('parent_state', '=', 'posted'),
                    ]),
                    limit=1,
                ))
                for period_bounds in (
                    ec_sales_return_type._get_period_boundaries(main_company, period)
                    for period in periods
                )
            }

            for (start, end), has_lines in periods_has_move_lines_map.items():
                if has_lines:
                    ec_sales_return_type._try_create_return_for_period(start, main_company, tax_unit)

    def _get_return_name(self, main_company, period_from=None, period_to=None, all_lang=False):
        main_company = main_company.sudo()
        country_code = ""
        if self.report_id and self.report_id.country_id and main_company.account_fiscal_country_id != self.report_id.country_id:
            if self.report_id and self.report_id.country_id:
                country_code = f"({self.report_id.country_id.code})"
            else:
                country_code = f"({main_company.account_fiscal_country_id.code})"

        if not all_lang:
            return self.env._(
                "%(return_type_name)s %(period_suffix)s %(country_code)s",
                return_type_name=self.name,
                period_suffix=self._get_period_name(main_company, period_from=period_from, period_to=period_to),
                country_code=country_code,
            )
        else:
            return_dict = {}
            installed_langs = self.env['res.lang'].get_installed()
            for lang_code, lang_name in installed_langs:
                return_dict[lang_code] = self.with_context(lang=lang_code).env._(
                    "%(return_type_name)s %(period_suffix)s %(country_code)s",
                    return_type_name=self.with_context(lang=lang_code).name,
                    period_suffix=self._get_period_name(main_company, period_from=period_from, period_to=period_to, lang_code=lang_code),
                    country_code=country_code,
                )

            return return_dict

    @api.model
    def _get_period_name(self, main_company=None, period_from=None, period_to=None, start_day=1, start_month=1, lang_code=None):
        def infer_periodicity(period_from, period_to):
            def match(dt_from, dt_to):
                return (dt_from, dt_to) == (period_from, period_to)

            if match(fields.Date.start_of(period_from, 'year'), fields.Date.end_of(period_to, 'year')):
                return 'year'
            elif match(*date_utils.get_month(period_to)):
                return 'monthly'
            else:
                return 'other'

        if not start_day or not start_month:
            if not main_company:
                raise ValidationError(self.env._("Main company must be provided if start_day and start_month are not provided"))
            start_day, start_month = self._get_start_date_elements(main_company)

        period_suffix = ""
        if period_from and period_to:
            if isinstance(period_from, str):
                period_from = fields.Date.to_date(period_from)

            if isinstance(period_to, str):
                period_to = fields.Date.to_date(period_to)

            if start_day != 1 or start_month != 1:
                period_suffix = f"{format_date(self.env, period_from, lang_code=lang_code)} - {format_date(self.env, period_to, lang_code=lang_code)}"
            else:
                inferred_periodicity = infer_periodicity(period_from, period_to)
                if inferred_periodicity == 'year':
                    period_suffix = f"{period_from.year}"
                elif inferred_periodicity == 'monthly':
                    period_suffix = format_date(self.env, period_from, date_format='LLLL yyyy', lang_code=lang_code)
                elif period_from == fields.Date.start_of(period_from, 'month') and period_to == fields.Date.end_of(period_to, 'month'):
                    period_suffix = f"{format_date(self.env, period_from, date_format='LLL yyyy', lang_code=lang_code)} - {format_date(self.env, period_to, date_format='LLL yyyy', lang_code=lang_code)}"
                else:
                    period_suffix = f"{format_date(self.env, period_from, lang_code=lang_code)} - {format_date(self.env, period_to, lang_code=lang_code)}"
        return period_suffix

    def _get_periodicity(self, company):
        return self.with_company(company).sudo().deadline_periodicity or company.sudo().account_return_periodicity

    def _get_start_date(self):
        return self.sudo().deadline_start_date or fields.Date.from_string('2025-01-01')

    def _get_periodicity_months_delay(self, company, date=None):
        """ Returns the number of months separating two returns
        """
        periodicity = self._get_periodicity(company)
        if periodicity == 'fiscalyear':
            if date:
                fy_dates = company.compute_fiscalyear_dates(date)
                start_date = fy_dates['date_from']
                end_date = fy_dates['date_to']
                delta = relativedelta(end_date + relativedelta(days=1), start_date)
                return delta.years * 12 + delta.months

            # Without a date, we cant know which fiscal year we are trying to get the length of
            # To fallback, we find the longest fiscal year defined for this company
            months = 12
            fiscalyears = self.env['account.fiscal.year'].search([('company_id', '=', company.id)])
            for fiscalyear in fiscalyears:
                delta = relativedelta(fiscalyear.date_to + relativedelta(days=1), fiscalyear.date_from)
                fiscal_year_months = delta.years * 12 + delta.months
                if fiscal_year_months > months:
                    months = fiscal_year_months
            return months

        return MONTHS_PER_PERIOD[periodicity]

    def _get_start_date_elements(self, main_company):
        start_date = self.with_company(main_company)._get_start_date()
        return start_date.day, start_date.month

    def _get_period_boundaries(self, company_id, date, override_period_months=None, override_start_date=None):
        """ Returns the boundaries of the period containing the provided date
        for this return type as a tuple (start, end).

        This function needs to stay consistent with the one inside Javascript in the filters for the tax report
        """
        if self._get_periodicity(company_id) == 'fiscalyear':
            fy_dates = company_id.compute_fiscalyear_dates(date)
            return fy_dates['date_from'], fy_dates['date_to']

        period_months = override_period_months if override_period_months else self._get_periodicity_months_delay(company_id, date=date)

        if override_start_date:
            start_day = override_start_date.day
            start_month = override_start_date.month
        else:
            start_day, start_month = self._get_start_date_elements(company_id)

        return self.env['account.report']._compute_period_range(date, period_months, start_day, start_month)

    @api.depends_context('company')
    @api.depends('name', 'report_id')
    def _compute_display_name(self):
        has_foreign_fiscal_pos = bool(self.env['account.fiscal.position'].search_count([
            *self.env['account.fiscal.position']._check_company_domain(self.env.company.id),
            ('foreign_vat', '!=', False),
        ], limit=1))
        if not has_foreign_fiscal_pos:
            return super()._compute_display_name()

        for return_type in self:
            if has_foreign_fiscal_pos and return_type.country_id:
                return_type.display_name = f'{return_type.name} ({return_type.country_id.code})'
            else:
                return_type.display_name = return_type.name


class AccountReturn(models.Model):
    _name = "account.return"
    _inherit = ['mail.thread.main.attachment', 'mail.activity.mixin']
    _description = "Accounting Return"
    _order = "is_completed, date_deadline, name, id"
    _check_company_domain = check_company_domain_account_return

    active = fields.Boolean(string="Active", default=True, tracking=True)
    name = fields.Char(string="Name", required=True, translate=True, tracking=True)
    date_from = fields.Date(string="Date From", required=True, tracking=True)
    date_to = fields.Date(string="Date To", required=True, tracking=True)
    period_match_periodicity = fields.Boolean(string="Is Period Matching Periodicity", compute="_compute_period_match_periodicity")
    type_id = fields.Many2one(comodel_name='account.return.type', string="Return Type", required=True)

    # IMPORTANT: To change the state of a return you should always use the field state as it will rewrite the value in the correct field implementation using 'get_state_field'
    state = fields.Char(string="State", compute="_compute_state", inverse="_inverse_state", store=True)
    next_state = fields.Char(string="Next State", compute="_compute_next_state")
    generic_state_tax_report = fields.Selection(
        string="Generic State",
        selection=[
            ('reviewed', 'Reviewed'),
            ('submitted', 'Submitted'),
            ('paid', 'Paid'),
        ],
        help="The state of the return for generic tax report flows",
        tracking=True,
    )
    generic_state_only_pay = fields.Selection(
        string="Generic State Only Pay",
        selection=[
            ('paid', 'Paid'),
        ],
        help="The state of the return for report flows when only payment is needed",
        tracking=True,
    )
    generic_state_review_submit = fields.Selection(
        string="Generic State Review Submit",
        selection=[
            ('reviewed', 'Reviewed'),
            ('submitted', 'Submitted'),
        ],
        help="The state of the return for report flows when review and submission are needed",
        tracking=True,
    )
    generic_state_review = fields.Selection(
        string="Generic State Review",
        selection=[
            ('reviewed', 'Reviewed'),
        ],
        help="The default state for audit and custom generated return types",
        tracking=True,
    )
    is_completed = fields.Boolean(string="Is Completed", default=False, tracking=True)  # Set to true when all steps are done
    company_id = fields.Many2one(comodel_name='res.company', string="Company", required=True)
    tax_unit_id = fields.Many2one(comodel_name='account.tax.unit', string="Tax Unit")
    company_ids = fields.Many2many(comodel_name='res.company', string="Companies", compute="_compute_company_ids", compute_sudo=True, store=True, precompute=True)
    closing_move_ids = fields.One2many(comodel_name='account.move', inverse_name='closing_return_id', tracking=True)
    attachment_ids = fields.Many2many(comodel_name='ir.attachment', bypass_search_access=True)
    type_external_id = fields.Char(compute="_compute_type_external_id")
    date_deadline = fields.Date(string="Deadline", compute="_compute_deadline", store=True)
    date_lock = fields.Date(string="Lock Date")
    date_submission = fields.Date(string="Submission Date")
    check_ids = fields.One2many(comodel_name='account.return.check', inverse_name='return_id', string="Checks")
    check_count = fields.Integer(string="Checks Count", compute="_compute_check_count")
    unresolved_check_count = fields.Integer(string="Issues", compute="_compute_unresolved_check_count")
    resolved_check_count = fields.Integer(string="Passed", compute="_compute_resolved_check_count")
    manually_created = fields.Boolean(string="Manually Created")

    # Tax return fields
    total_amount_to_pay = fields.Monetary(currency_field='amount_to_pay_currency_id')
    period_amount_to_pay = fields.Monetary(currency_field='amount_to_pay_currency_id')
    amount_to_pay_currency_id = fields.Many2one(comodel_name='res.currency', compute='_compute_amount_to_pay_currency_id', compute_sql='_compute_sql_amount_to_pay_currency_id', compute_sudo=True)
    show_amount_to_pay = fields.Boolean(compute='_compute_show_amount_to_pay')

    # view helper fields
    days_to_deadline = fields.Integer(compute='_compute_days_to_deadline')
    is_report_set = fields.Boolean(compute='_compute_is_report_set')
    has_move_entries = fields.Boolean(compute='_compute_has_move_entries')
    report_opened_once = fields.Boolean(help="Has the report been opened once", default=False)
    report_name = fields.Char(string="Report Name", related="type_id.report_id.display_name")
    show_companies = fields.Boolean(compute="_compute_show_companies")
    show_companies_mismatch_warning = fields.Boolean(compute="_compute_show_companies_mismatch_warning")
    is_main_company_active = fields.Boolean(compute="_compute_is_main_company_active")
    return_type_category = fields.Selection(related="type_id.category")
    visible_states = fields.Json(string="Visible States", compute="_compute_visible_states")
    show_submit_button = fields.Boolean(compute="_compute_show_submit_button")
    is_tax_return = fields.Boolean(related="type_id.is_tax_return_type")
    is_ec_sales_list_return = fields.Boolean(related="type_id.is_ec_sales_list_return_type")

    # Audit
    audit_status = fields.Selection(
        selection=[
            ('ongoing', "Ongoing"),
            ('done', "Done"),
            ('paused', "Paused"),
        ],
        default='ongoing',
        required=True,
        tracking=True,
    )

    audit_account_status_ids = fields.One2many(string="Account Status", comodel_name='account.audit.account.status', inverse_name='audit_id')
    audit_balances_count = fields.Integer(string="Balances Count", compute="_compute_audit_balances_count")
    audit_balances_completed_count = fields.Integer(string="Completed Balances Count", compute="_compute_audit_balances_completed_count")
    cycle_ids = fields.Many2many(
        comodel_name='account.return.audit.cycle',
        string="Cycles",
        tracking=True,
    )

    def _update_translated_name(self):
        specified_lang = self.env.context.get('update_returns_translation_lang')

        for account_return in self:
            type_id = account_return.type_id
            if specified_lang:
                translated_name_dict = {specified_lang: type_id.with_context(lang=specified_lang)._get_return_name(
                    account_return.company_id,
                    account_return.date_from,
                    account_return.date_to,
                    all_lang=False,
                )}

            else:
                translated_name_dict = type_id._get_return_name(
                    account_return.company_id,
                    account_return.date_from,
                    account_return.date_to,
                    all_lang=True,
                )

            for lang_code, translated_name in translated_name_dict.items():
                account_return.with_context(lang=lang_code).name = translated_name

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        account_status_create_vals = []
        for record in records:
            if record.return_type_category == 'audit':
                accounts = self.env['account.account'].search_fetch(
                    domain=self.env['account.account']._check_company_domain(record.company_ids),
                    field_names=['id'],
                )
                eve_of_date_from = record.date_from - relativedelta(days=1)
                date_from, date_to = record.type_id._get_period_boundaries(self.env.company, eve_of_date_from)
                previous_return = self.env['account.return'].search(
                    domain=[
                        ('date_from', '=', date_from),
                        ('date_to', '=', date_to),
                        ('type_id', '=', record.type_id.id),
                    ],
                    limit=1,
                )
                previous_accounts_with_status = self.env['account.account']
                if previous_return:
                    previous_accounts_with_status = self.env['account.audit.account.status'].search(
                        domain=[
                            ('audit_id', '=', previous_return.id),
                            ('status', '!=', False),
                        ],
                    ).account_id

                query_line = self.env['account.move.line']._search([
                    ('date', '>=', record.date_from),
                    ('date', '<=', record.date_to),
                    ('parent_state', '=', 'posted'),
                ], limit=1)
                query_line.add_where(SQL('account_account.id = account_move_line.account_id'))

                query_account = self.env['account.account']._search([
                    ('company_ids', 'in', record.company_ids.ids),
                    ('code', '!=', False),
                ])
                query_account.add_where(SQL('EXISTS(%s)', query_line.select()))
                account_ids_used_during_period = {account[0] for account in self.env.execute_query(query_account.select())}

                allowed_account_ids = set(previous_accounts_with_status.ids) | account_ids_used_during_period
                account_status_create_vals += [
                    {
                        'audit_id': record.id,
                        'account_id': account['id'],
                        'status': 'todo' if account.id in allowed_account_ids else False,
                    } for account in accounts
                ]
        self.env['account.audit.account.status'].create(account_status_create_vals)
        return records

    def write(self, vals):
        result = super().write(vals)
        for record in self:
            if record.type_id.states_workflow in vals:
                if record.date_from <= fields.Date.end_of(fields.Date.context_today(record), "month"):
                    record.refresh_checks()

            if 'audit_status' in vals:
                if record.audit_status in ('ongoing', 'paused'):
                    record.state = False

            if 'cycle_ids' in vals:
                record.refresh_checks()

        return result

    @api.ondelete(at_uninstall=False)
    def _unlink_if_not_manually_created_new(self):
        if not self.env.user.has_group('account.group_account_user') and not self.env.su:
            raise UserError(self.env._("Only an Accountant can delete a return."))
        if any(not account_return.manually_created or account_return.state for account_return in self) and not self.env.su:
            raise UserError(self.env._("Only manually created returns in 'new' state can be deleted."))

    @api.model
    def action_refresh_all_returns(self):
        root_companies = self.env['res.company'].sudo().search([
            ('account_opening_date', '!=', False),
            ('id', 'parent_of', self.env.companies.ids)
        ])
        self.env['account.return.type']._generate_or_refresh_all_returns(root_companies)

    @api.model
    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        return_type_delay = return_type.with_company(company).deadline_days_delay
        delay = return_type_delay if return_type_delay else company.account_return_reminder_day
        return date_to + relativedelta(days=delay)

    @api.depends('date_to', 'type_id.deadline_days_delay', 'is_completed')
    def _compute_deadline(self):
        for account_return in self:
            if account_return.is_completed:
                continue

            account_return.date_deadline = account_return._evaluate_deadline(
                account_return.company_id,
                account_return.type_id,
                account_return.type_external_id,
                account_return.date_from,
                account_return.date_to
            )

    @api.model
    def _get_company_ids(self, main_company, tax_unit, report):
        if report.filter_multi_company != 'tax_units':
            tax_unit = False

        companies = tax_unit.company_ids if tax_unit else self.env['res.company'].sudo().search([('id', 'child_of', main_company.id)])

        if report:
            previous_options = {'tax_unit': tax_unit.id if tax_unit else 'company_only'}
            options = report.sudo().with_context(allowed_company_ids=companies.ids).with_company(main_company.id).get_options(previous_options=previous_options)
            return self.env['res.company'].browse(report.get_report_company_ids(options))

        return self.env['res.company'].browse(companies.ids)  # Drop sudo and avoid leaking elevated permissions

    @api.depends('company_id', 'tax_unit_id', 'type_id')
    def _compute_company_ids(self):
        company_ids_map = defaultdict(lambda: self.env['account.return'])
        for record in self:
            company_ids_map[record.company_id, record.tax_unit_id, record.type_id.report_id] |= record

        for (company, tax_unit, report), returns in company_ids_map.items():
            returns.company_ids = self._get_company_ids(company, tax_unit, report)

    @api.depends_context('allowed_company_ids')
    @api.depends('company_ids')
    def _compute_show_companies(self):
        for record in self:
            # We use _get_company_ids() instead of company_ids to avoid cache pollution issues (the ORM team is working on it).
            # ir.rule filters records out during cache insertion, so cached values may differ from those in the database.
            # As a result, users with branch-only access might see company_ids without the parent company.
            record.show_companies = (len(self.env.companies) > 1 or
                                     len(record._get_company_ids(record.company_id, record.tax_unit_id, record.type_id.report_id)) > 1)

    def _check_all_branches_allowed(self):
        for account_return in self:
            report = account_return.type_id.report_id
            if account_return._get_company_ids(account_return.company_id, False, report) - self.env.user.company_ids:
                report.show_error_branch_allowed()

    @api.depends_context('allowed_company_ids')
    @api.depends('company_ids')
    def _compute_show_companies_mismatch_warning(self):
        for record in self:
            record.show_companies_mismatch_warning = bool(record.company_ids - self.env.companies)

    @api.depends_context('allowed_company_ids')
    @api.depends('company_ids')
    def _compute_is_main_company_active(self):
        for account_return in self:
            account_return.is_main_company_active = account_return.company_id in self.env.companies

    @api.depends('is_tax_return', 'closing_move_ids', 'state', 'type_id.states_workflow')
    def _compute_show_amount_to_pay(self):
        for record in self:
            states = [state for state, _label in record._get_all_states()]
            if record.is_tax_return:
                record.show_amount_to_pay = record.closing_move_ids
            elif record.state and 'paid' in states:
                # This assumes it cannot have two times the same state name in the same flow at different steps.
                index_of_paid = states.index('paid')
                index_of_current_state = states.index(record.state)
                record.show_amount_to_pay = index_of_current_state >= index_of_paid
            else:
                record.show_amount_to_pay = False

    @api.depends('type_id')
    def _compute_state(self):
        for record in self:
            if state_field := record.type_id.states_workflow:
                record.state = record[state_field]
            else:
                record.state = False

    @api.depends('state')
    def _compute_next_state(self):
        for record in self:
            states = record._get_all_states()
            state_keys = [s[0] for s in states]
            if not record.state:
                record.next_state = state_keys[0]
                continue
            next_state_index = state_keys.index(record.state) + 1
            record.next_state = state_keys[next_state_index] if next_state_index < len(state_keys) else False

    def _inverse_state(self):
        for record in self:
            record[record.type_id.states_workflow] = record.state

    @api.depends('type_id', 'state')
    def _compute_visible_states(self):
        for record in self:
            selection = self._fields[record.type_id.states_workflow]._description_selection(self.env)
            state_keys = [s[0] for s in selection]
            current_idx = state_keys.index(record.state) if record.state in state_keys else -1
            record.visible_states = [
                {
                    'name': state,
                    'label': label,
                    'active': record.is_completed or i <= current_idx,
                    'alert_type': False,
                    'error_msg': False,
                }
                for i, (state, label) in enumerate(selection)
            ]

    @api.depends('tax_unit_id', 'company_id')
    def _compute_amount_to_pay_currency_id(self):
        for record in self:
            record.amount_to_pay_currency_id = record.tax_unit_id.main_company_id.sudo().currency_id or record.company_id.sudo().currency_id

    def _compute_sql_amount_to_pay_currency_id(self, table):
        return SQL("COALESCE(%s, %s)", table.tax_unit_id.main_company_id.currency_id, table.company_id.currency_id)

    @api.depends('check_ids')
    def _compute_check_count(self):
        for record in self:
            record.check_count = len(record.check_ids)

    @api.depends('state', 'check_ids.state', 'check_ids.result')
    def _compute_unresolved_check_count(self):
        for record in self:
            failed_count = 0
            for check in record.check_ids:
                failed_count += 1 if check.result in ('todo', 'anomaly') else 0

            record.unresolved_check_count = failed_count

    @api.depends('check_ids', 'unresolved_check_count', 'state')
    def _compute_resolved_check_count(self):
        for record in self:
            record.resolved_check_count = len(record.check_ids) - record.unresolved_check_count

    @api.depends('type_id')
    def _compute_type_external_id(self):
        external_id_per_type = self.type_id.get_external_id()
        for record in self:
            record.type_external_id = external_id_per_type.get(record.type_id.id, None)

    @api.depends('type_id')
    def _compute_is_report_set(self):
        for record in self:
            record.is_report_set = record.type_id.report_id

    @api.depends('closing_move_ids')
    def _compute_has_move_entries(self):
        for record in self:
            record.has_move_entries = record.closing_move_ids

    @api.depends('date_deadline')
    def _compute_days_to_deadline(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.days_to_deadline = (record.date_deadline - today).days if record.date_deadline else 0

    @api.depends('audit_account_status_ids')
    def _compute_audit_balances_count(self):
        for record in self:
            record.audit_balances_count = len(record.audit_account_status_ids.filtered('status'))

    @api.depends('audit_account_status_ids')
    def _compute_audit_balances_completed_count(self):
        for record in self:
            record.audit_balances_completed_count = len(record.audit_account_status_ids.filtered(lambda r: r.status in ('reviewed', 'supervised')))

    @api.depends('type_id', 'next_state', 'unresolved_check_count')
    def _compute_show_submit_button(self):
        for record in self:
            record.show_submit_button = (
                record.next_state == 'submitted'
                or (
                    record.type_id.states_workflow in ('generic_state_review_submit', 'generic_state_tax_report')
                    and record.next_state == 'reviewed'
                    and not record.unresolved_check_count
                )
            )

    @api.depends('date_from', 'date_to', 'type_id', 'company_id')
    def _compute_period_match_periodicity(self):
        for record in self:
            aligned_date_from, aligned_date_to = record.type_id._get_period_boundaries(record.company_id, record.date_from)
            record.period_match_periodicity = record.date_from == aligned_date_from and record.date_to == aligned_date_to

    def _create_mail_tracking_values(self, initial_value, new_value, col_name, col_info):
        # override to force 'State' label to different 'states_workflow' fields
        # as various fields may be used for the workflow review process, as
        # designed by the 'states_workflow' field that gives the field to check
        tracking_values = super()._create_mail_tracking_values(initial_value, new_value, col_name, col_info)
        if len(self) != 1:
            return tracking_values
        state_string = self.env['ir.model.fields'].get_field_string('account.return')['state']
        toupdate_field_name = self.type_id.states_workflow
        if col_name == toupdate_field_name:
            tracking_values['field_label'] = state_string
        return tracking_values

    @api.model
    def _get_return_from_report_options(self, options):
        report = self.env['account.report'].browse(options['report_id'])
        sender_company = report._get_sender_company_for_export(options)
        domain = [
            ('company_id', '=', sender_company.id),
            ('date_from', '=', options['date']['date_from']),
            ('date_to', '=', options['date']['date_to']),
            ('type_id.report_id', '=', report.id),
        ]

        if return_type_id := options.get('return_periodicity', {}).get('return_type_id'):
            domain.append(('type_id', '=', return_type_id))

        return self.env['account.return'].search(domain, limit=1)

    @api.model
    def get_next_returns_ids(self, journal_id=False, additional_domain=None, allow_multiple_by_types=False):
        """
        Return all the return for the current company to post next
        """

        domain = [
            ('is_completed', '=', False),
            *(additional_domain or []),
        ]

        if journal_id:
            journal = self.env['account.journal'].browse(journal_id)
            domain += self.env['account.return']._check_company_domain(journal.company_id)

        future_returns_by_type = self.search_fetch(
            domain=domain,
            field_names=['name', 'date_deadline', 'type_id', 'id'],
        ).grouped('type_id')

        next_returns_ids = []
        for recordset in future_returns_by_type.values():
            if not allow_multiple_by_types:
                next_returns_ids.append(recordset[0].id)
            else:
                for record in recordset:
                    next_returns_ids.append(record.id)

        return next_returns_ids

    @api.model
    def get_next_return_for_dashboard(self, journal_id=False):
        today = fields.Date.context_today(self)
        thirty_days_later = fields.Date.add(today, days=30)

        additional_domain = [
            ('return_type_category', '=', 'account_return'),
            ('date_deadline', '<=', thirty_days_later),
        ]
        return_ids = self.get_next_returns_ids(journal_id=journal_id, additional_domain=additional_domain, allow_multiple_by_types=True)

        account_returns = self.browse(return_ids)
        dashboard_return_dicts = []
        grouped_by_type = defaultdict(self.env['account.return'].browse)

        for account_return in account_returns:
            return_type = account_return.type_id
            grouped_by_type[return_type] |= account_return

        for return_type, returns in grouped_by_type.items():
            first_return = min(returns, key=lambda x: x.date_deadline)

            dashboard_return_dicts.append({
                'id': first_return.id,
                'date_deadline': first_return.date_deadline,
                'name': return_type.name,
                'type_id': return_type.id,
                'matched_returns_count': len(returns),
            })

        return dashboard_return_dicts

    @api.model
    def action_open_tax_return_view(self, additional_return_domain=None, additional_context=None):
        if not additional_context:
            additional_context = {}

        return_action = self.env['ir.actions.act_window']._for_xml_id('account_reports.action_view_account_return')

        if additional_return_domain:
            return_action['domain'] = additional_return_domain
        if additional_context:
            context = ast.literal_eval(return_action['context'])
            context.update(additional_context)
            return_action['context'] = str(context)
        return return_action

    def action_open_audit_return(self):
        self.ensure_one()
        audit_action = self.with_context(active_id=self.id, active_model=self._name).env["ir.actions.act_window"]._for_xml_id('account_reports.action_view_account_audit_checks')
        return {
            **audit_action,
            'domain': [('return_id', '=', self.id)],
            'context': {
                'account_return_view_id': self.env.ref('account_reports.account_return_kanban_view').id,
                'search_default_groupby_cycle': 1,
                'active_model': 'account.return',
                'active_id': self.id,
                'max_number_opened_groups': 100000,
            },
        }

    def action_open_audit_settings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Edit Working File'),
            'res_model': 'account.return',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('account_reports.account_audit_form_view').id,
            'target': 'new',
        }

    def _get_pay_wizard(self):
        """
        To be overridden in l10n which want to open a specific wizard on pay
        """
        wizard = self.env['account.return.payment.wizard'].create({
            'return_id': self.id,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _("Payment"),
            'res_model': 'account.return.payment.wizard',
            'res_id': wizard.id,
            'views': [(False, 'form')],
            'target': 'new',
        }

    ####################################################################################################
    ####  State Actions
    ####################################################################################################

    def action_validate(self):
        """
        Validating return consists of:
        - Review the checks with optionally bypassing failing ones
        - Mark Audit Return as completed
        - Set Lock date and generate closing entry
        """
        self.ensure_one()

        if self.return_type_category == 'audit':
            self.state = 'reviewed'
            return self._mark_completed()

        self._proceed_with_locking()

    def _proceed_with_locking(self):
        """
        Called at the end of the locking process.
        It creates:
        - closing entries if it is a tax report
        - generates attachments specified in `_generate_locking_attachments`
        - change state to 'reviewed' as it's last step in validation process

        """
        self.ensure_one()

        domain = [
            ('company_id', '=', self.company_id.id),
            ('type_id', '=', self.type_id.id),
            ('date_deadline', '<', self.date_deadline),
            ('date_lock', '=', False),
            ('is_completed', '=', False),
            ('return_type_category', '!=', 'audit'),
        ]
        count = self.env['account.return'].search_count(domain, limit=1)
        if count:
            raise UserError(_("You cannot lock this return as there are previous returns that are waiting to be posted."))

        if report := self.type_id.report_id:
            options = {**self._get_closing_report_options(), 'export_mode': 'file'}

            report.with_context(allowed_company_ids=self.company_ids.ids)._generate_carryover_external_values(options)
            state_keys = [s[0] for s in self._get_all_states()]
            if 'submitted' not in state_keys:
                self._generate_locking_attachments(options)
            if self.is_tax_return:
                # Create the tax closing move
                self._generate_tax_closing_entries(options)

                # Reset any tax lock date exceptions
                self.env['account.lock_exception'].search([
                    ('company_id', 'in', self.company_ids.ids),
                    ('state', '=', 'active'),
                    ('lock_date_field', '=', 'tax_lock_date'),
                ]).sudo().action_revoke()

                # Create default expressions for next period if necessary
                main_company = self.tax_unit_id.main_company_id or self.company_id
                if (report.country_id and report.country_id == main_company.account_fiscal_country_id and
                        (not main_company.tax_lock_date or self.date_to > main_company.tax_lock_date)):
                    for company in self.company_ids:
                        self.env['account.report'].with_company(company)._generate_default_external_values(self.date_from, self.date_to, True)
                        company.sudo().tax_lock_date = self.date_to

                # Generate the carryover values.
                payable_accounts, receivable_accounts = self._get_tax_closing_payable_and_receivable_accounts()
                self.period_amount_to_pay = self._evaluate_period_amount_to_pay_from_tax_closing_accounts(payable_accounts, receivable_accounts)
                self.total_amount_to_pay = self._evaluate_total_amount_to_pay_from_tax_closing_accounts(receivable_accounts)

        self.date_lock = fields.Date.context_today(self)

        self.state = 'reviewed'
        if self.type_id.states_workflow == 'generic_state_review':
            return self._mark_completed()

    def _get_tax_closing_payable_and_receivable_accounts(self):
        """The accounts this return settles on, used to evaluate the amounts left to pay."""
        payable_accounts = self.env['account.account']
        receivable_accounts = self.env['account.account']
        for company in self.company_ids:
            payable_accounts |= self.type_id.with_company(company).tax_payable_account_id
            receivable_accounts |= self.type_id.with_company(company).tax_receivable_account_id
        return payable_accounts, receivable_accounts

    def _evaluate_period_amount_to_pay_from_tax_closing_accounts(self, payable_accounts, receivable_accounts):
        amount = -sum(
            aml.balance
            for aml in self.closing_move_ids.line_ids
            if aml.account_id in payable_accounts + receivable_accounts
        )

        return self.amount_to_pay_currency_id.round(amount)

    def _evaluate_total_amount_to_pay_from_tax_closing_accounts(self, receivable_accounts):
        recoverable_amount_to_pay = self.env['account.move.line'].sudo()._read_group(
            [
                ('date', '<=', self.date_to),
                ('account_id', 'in', receivable_accounts.ids),
                ('company_id', 'in', self.company_ids.ids),
                ('move_id.state', '=', 'posted'),
                ('id', 'not in', self.closing_move_ids.line_ids.ids),
            ],
            aggregates=['balance:sum'],
        )[0][0]
        return self.amount_to_pay_currency_id.round(-recoverable_amount_to_pay + self.period_amount_to_pay)

    def _generate_locking_attachments(self, options):
        self.ensure_one()
        self._add_attachment(self.type_id.report_id.export_to_pdf(options))

    def _add_attachment(self, file_data):
        self.ensure_one()
        data = file_data['file_content']
        attachment = self.env['ir.attachment'].create({
            'name': file_data['file_name'],
            'raw': data,
            'type': 'binary',
            'description': file_data['file_name'],
            'res_model': self._name,
            'res_id': self.id,
        })
        self.attachment_ids = [Command.link(attachment.id)]
        return attachment

    def action_submit(self):
        self.ensure_one()
        if self.next_state == 'reviewed':
            self.action_validate()
        self._check_all_branches_allowed()
        return self._prepare_submission()

    def _prepare_submission(self):
        return self._proceed_with_submission()

    def _proceed_with_submission(self, options_to_inject=None):
        self.state = 'submitted'
        self.date_submission = fields.Date.context_today(self)
        if self.type_id.report_id:
            options = {**self._get_closing_report_options(), **(options_to_inject or {}), 'export_mode': 'file'}
            self._generate_locking_attachments(options)
        return self._on_post_submission_event()

    def _on_post_submission_event(self):
        if self.type_id.states_workflow == 'generic_state_review_submit':
            return self._mark_completed()

        if self.type_id.states_workflow in ('generic_state_only_pay', 'generic_state_tax_report'):
            return self.action_pay()

    def action_pay(self):
        self.ensure_one()
        is_positive_amount = self.amount_to_pay_currency_id.compare_amounts(self.period_amount_to_pay, 0) > 0
        if is_positive_amount or not self.state:
            return (self._get_pay_wizard() or self._action_finalize_payment())
        return self._action_finalize_payment()

    def _action_finalize_payment(self):
        self.ensure_one()
        self.state = 'paid'
        if self.type_id.states_workflow in ('generic_state_only_pay', 'generic_state_tax_report'):
            return self._mark_completed()

    def _get_all_states(self):
        self.ensure_one()
        return self._fields[self.type_id.states_workflow]._description_selection(self.env)

    ####################################################################################################
    ####  Revert Actions
    ####################################################################################################

    def action_archive(self):
        super(AccountReturn, self.filtered(lambda record: not record.state)).action_archive()

    def action_unarchive(self):
        self.ensure_one()
        if self.return_type_category == 'account_return':
            domain = [
                ('id', '!=', self.id),
                ('company_id', '=', self.company_id.id),
                ('type_id', '=', self.type_id.id),
                ('date_from', '=', self.date_from),
                ('date_to', '=', self.date_to),
                ('return_type_category', '=', self.return_type_category),
                ('active', '=', True),
            ]
            existing_active_return = self.env['account.return'].search(domain, limit=1)
            if existing_active_return:
                raise UserError(_("An active return already exists for the same period."))
        super().action_unarchive()

    def _reset_checks_for_states(self, states):
        checks_to_reset = self.check_ids.filtered(lambda check: check.state in states)
        checks_to_reset.write({
            'refresh_result': True,
            'approver_ids': False,
            'supervisor_id': False,
        })
        for account_return in checks_to_reset.return_id:
            account_return.message_post(body=_("All checks and approvers have been reset"))

    def action_reset_tax_return_common(self):
        self.ensure_one()
        if not self.is_tax_return:
            return True

        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_("Only an Accounting Administrator can reset a tax return"))

        # Check if it is the last return locked
        domain = [
            ('company_id', '=', self.company_id.id),
            ('type_id', '=', self.type_id.id),
            ('date_lock', '!=', False),
            ('date_deadline', '>', self.date_deadline),
        ]
        if self.env['account.return'].search_count(domain, limit=1):
            raise UserError(_("You cannot reset this return to new, as another return has been locked at a later date."))

        # delete carryover if possible
        if report := self.type_id.report_id:

            if not report.country_id or report.country_id == self.company_id.account_fiscal_country_id:
                # Check for locked return
                violated_lock_dates = []
                for company in self.company_ids:
                    violated_lock_dates = company._get_lock_date_violations(
                        self.date_to,
                        fiscalyear=False,
                        sale=False,
                        purchase=False,
                        tax=True,
                        hard=True,
                    )
                    if violated_lock_dates:
                        raise UserError(_("The operation is refused as it would impact an already issued tax statement. "
                                        "Please change the following lock dates to proceed: %(lock_date_info)s.",
                                        lock_date_info=self.env['res.company']._format_lock_dates(violated_lock_dates)))

            carryover_values = self.env['account.report.external.value'].search(
                [
                    ('carryover_origin_report_line_id', 'in', report.line_ids.ids),
                    ('date', '=', self.date_to),
                    ('company_id', 'in', self.company_ids.ids),
                ]
            )

            carryover_impacted_period = self.type_id._get_period_boundaries(self.company_id, self.date_to + relativedelta(days=1))

            violated_lock_dates = self.company_id._get_lock_date_violations(
                carryover_impacted_period[1], fiscalyear=False, sale=False, purchase=False, tax=True, hard=True,
            ) if carryover_values else None

            if violated_lock_dates:
                raise UserError(_("You cannot reset this closing entry to draft, as it would delete carryover values impacting the tax report of a locked period. "
                                "Please change the following lock dates to proceed: %(lock_date_info)s.",
                                lock_date_info=self.env['res.company']._format_lock_dates(violated_lock_dates)))

            carryover_values.unlink()
            self.total_amount_to_pay = 0
            self.period_amount_to_pay = 0

        # Unreconcile closing entries
        move_lines = self.closing_move_ids.line_ids._all_reconciled_lines()
        move_lines.remove_move_reconcile()

        # Find Reconciliation moves and unlink them
        payable_accounts, receivable_accounts = self._get_tax_closing_payable_and_receivable_accounts()
        reconciliation_moves = (move_lines.move_id - self.closing_move_ids).filtered(
            lambda m: len(m.line_ids) == 2
            and (m.line_ids.account_id & receivable_accounts)
            and (m.line_ids.account_id & payable_accounts)
        )
        reconciliation_moves.button_draft()
        reconciliation_moves.unlink()

        self.date_lock = False
        self._reset_common()
        return True

    def action_reset_custom_return(self):
        self._reset_common()
        return True

    def action_reset_annual_closing(self):
        self.ensure_one()

        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_("Only an Accounting Administrator can reset an annual closing"))

        self._reset_common()
        return True

    def action_reset_2_states(self):
        self.ensure_one()

        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_("Only an Accounting Administrator can reset a return"))

        self._reset_common()
        return True

    def _reset_common(self):
        states = self._get_all_states()
        states_to_reset = [False] + [state for state, _label in states]
        self._reset_checks_for_states(states_to_reset)
        self.state = False
        self._mark_uncompleted()
        self.report_opened_once = False
        self.attachment_ids.unlink()
        self.date_submission = False

        if self.closing_move_ids:
            self.closing_move_ids.button_draft()
            self.closing_move_ids.unlink()

    ####################################################################################################
    ####  Other Actions
    ####################################################################################################
    def action_open_attachments(self):
        action = self.action_open_account_return()
        action['context']['open_attachments_in_chatter'] = True
        return action

    def action_mark_completed(self):
        self.ensure_one()
        return self._mark_completed()

    def _mark_completed(self):
        self.ensure_one()
        self.is_completed = True
        if self.return_type_category == 'audit':
            self.audit_status = 'done'
        if not self.env.context.get('in_checks_view'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'sticky': False,
                    'message': _("Return Completed"),
                    'next': {
                        'type': 'ir.actions.client',
                        'tag': 'action_return_refresh',
                        'params': {
                            'return_ids': self.ids,
                            'next_action': {'type': 'ir.actions.act_window_close'},
                        },
                    }
                }
            }

    def action_mark_uncompleted(self):
        self.ensure_one()
        if not self.is_completed:
            raise UserError(_("You can only unarchive a completed return."))
        self._mark_uncompleted()

    def _mark_uncompleted(self):
        self.ensure_one()
        self.is_completed = False
        if self.return_type_category == 'audit':
            self.audit_status = 'ongoing'

    def action_export_working_files(self):
        self.ensure_one()
        report = self.env.ref('account_reports.trial_balance_report').with_company(self.company_id.id)
        options = report.get_options({
            'selected_variant_id': report.id,
            'date': {
                'date_from': self.date_from,
                'date_to': self.date_to,
            },
            'show_account': True,
            'show_currency': True,
            'show_last_annotations': True,
            'unfold_all': True,
            'report_title': self.name.strip(),
        })

        results = dict(self.env['account.return.check']._fields['result']._description_selection(self.env))
        options['working_file_export_checks'] = [{
            'cycle_name': cycle.name,
            'checks': [{
                'name': check.name,
                'message': html2plaintext(check.message or ''),
                'notes': html2plaintext(check.notes or ''),
                'badge_label': results[check.result],
                'badge_state': check.result,
            } for check in checks]
        } for cycle, checks in self.check_ids.grouped('cycle_id').items()]

        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'file_generator': 'export_to_pdf',
            },
        }

    def action_view_entry(self):
        self.ensure_one()
        name = _("Closing Entries") if len(self.closing_move_ids) > 1 else _("Closing Entry")
        return self.closing_move_ids._get_records_action(name=name)

    def _get_report_client_action(self, report):
        """ Returns the stored account_report client action for this report or its root report. """
        report_ids = [report.id] + report.root_report_id.ids

        return self.env['ir.actions.client'].sudo().search(
            [('tag', '=', 'account_report')],
            order='path desc, id asc',
        ).filtered(lambda a: literal_eval(a.context or '{}').get('report_id') in report_ids)[:1]

    def action_open_report(self):
        self.ensure_one()
        if self.has_access('write'):
            self.report_opened_once = True
        report = self.type_id.report_id
        client_action = self._get_report_client_action(report)
        action = client_action._get_action_dict() if client_action else {
            'type': 'ir.actions.client',
            'name': report.display_name,
            'tag': 'account_report',
            'context': {'report_id': report.id},
        }
        action['params'] = {'options': self._get_closing_report_options(), 'ignore_session': True}
        return action

    def _get_closing_report_options(self):
        report = self.type_id.report_id

        period_type = 'return_period'
        periodicity = self.type_id._get_periodicity(self.company_id)
        if (periodicity == 'fiscalyear' and not report.use_fiscal_periods) or (periodicity == 'year' and report.use_fiscal_periods) or not self._period_match_periodicity():
            period_type = 'custom'

        options = {
            'date': {
                'date_from': fields.Date.to_string(self.date_from),
                'date_to': fields.Date.to_string(self.date_to),
                'period_type': period_type,
            },
            'selected_variant_id': report.id,
            'sections_source_id': report.id,
            'tax_unit': 'company_only' if not self.tax_unit_id else self.tax_unit_id.id,
            'selected_return_type_id': self.type_id.id,
        }
        current_company = self.env.company
        company_ids = self.company_ids.ids
        return report.sudo().with_context(allowed_company_ids=company_ids).with_company(current_company).get_options(previous_options=options)

    def _period_match_periodicity(self):
        aligned_date_from, aligned_date_to = self.type_id._get_period_boundaries(self.company_id, self.date_from)
        return self.date_from == aligned_date_from and self.date_to == aligned_date_to

    def action_send_email_instructions(self, wizard, template):
        self.ensure_one()

        compose_form = self.env.ref('mail.email_compose_message_wizard_form')

        ctx = {
            'default_model': 'account.return',
            'default_res_ids': self.ids,
            'default_template_id': template.id if template else False,
            'default_composition_mode': 'comment',
            'default_partner_ids': self._get_return_mail_recipients(),
            'mail_notify_author': True,
            'reply_to_force_new': False,
            'default_email_layout_xmlid': 'mail.mail_notification_layout_with_responsible_signature',
            'account_return_finalize_payment': True,
        }

        if (wizard and 'qr_code' in wizard):
            ctx.update({
                'qr_data': wizard._get_b64_qr_data(),
                'communication': wizard.communication
            })

        return {
            'name': template.name if template else 'Tax payment',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx,
        }

    def _get_return_mail_recipients(self):
        mail = self.env['mail.mail'].search([
            ('model', '=', 'account.return'),
            ('record_company_id', '=', self.company_id.id),
        ], order='create_date desc', limit=1)
        return mail.partner_ids.ids or self.env.user.partner_id.ids

    ####################################################################################################
    ####  Tax Closing
    ####################################################################################################
    def _generate_tax_closing_entries(self, options):
        """
        Generates and compute a closing move for every companies of the return.
        :param options: report options
        :return: The closing moves.
        """
        closing_moves_to_create = self._generate_tax_closing_entries_create_values(options)
        moves = self.env['account.move'].sudo().create(closing_moves_to_create)

        # If the lock date has been set before the return is submitted, we don't want the tax lock date check to raise
        bypass_lock = self.company_ids[-1]._get_user_lock_date('tax_lock_date') == self.date_to

        moves.with_context(account_bypass_tax_closing_lock_check=bypass_lock).action_post()

    def _generate_tax_closing_entries_create_values(self, options):
        self.ensure_one()

        closing_move_to_create = []
        for company in self.company_ids:
            line_ids_vals, tax_group_subtotal = self.sudo()._compute_tax_closing_entry(company, options)
            line_ids_vals += self.sudo()._add_tax_group_closing_items(tax_group_subtotal)
            closing_move_to_create.append({
                'company_id': company.id,  # Important to specify together with the journal, for branches
                'journal_id': company._get_tax_closing_journal().id,
                'date': self.date_to,
                'closing_return_id': self.id,
                'ref': self.name,
                'line_ids': line_ids_vals,
            })

        return closing_move_to_create

    def _ensure_tax_closing_accounts_configured(self, company):
        """Raises a RedirectWarning when the accounts the closing entry needs are not configured on the return type."""
        self.ensure_one()

        if (
            self.type_id.with_company(company).tax_payable_account_id
            and self.type_id.with_company(company).tax_receivable_account_id
        ):
            return

        raise RedirectWarning(
            self.env._('Please specify the accounts necessary for the tax closing entry.'),
            {
                'type': 'ir.actions.act_window',
                'name': self.env._("Tax Return Type"),
                'res_model': 'account.return.type',
                'res_id': self.type_id.id,
                'view_mode': 'form',
                'views': [[False, 'form']],
            },
            self.env._('Configure accounts'),
        )

    def _compute_tax_closing_entry(self, company, options):
        """Compute the tax closing entry.

        This method returns the one2many commands to balance the tax accounts for the selected period, and
        a dictionnary that will help balance the different accounts set per tax group.
        """
        self.env.flush_all()

        company_options = {
            **options,
            'forced_domain': options.get('forced_domain', []) + [('company_id', '=', company.id)]
        }

        query = self.type_id.report_id._get_report_query(
            company_options,
            'strict_range',
            domain=self._get_vat_closing_entry_additional_domain(),
        )

        # Check whether it is multilingual, in order to get the translation from the JSON value if present
        tax_name = self.env['account.tax']._field_to_sql('tax', 'name')

        query = SQL(
            """
            SELECT "account_move_line".tax_line_id as tax_id,
                    tax.tax_group_id as tax_group_id,
                    %(tax_name)s as tax_name,
                    "account_move_line".account_id,
                    COALESCE(SUM("account_move_line".balance), 0) as amount
            FROM account_tax tax, account_tax_repartition_line repartition, %(table_references)s
            WHERE %(search_condition)s
              AND tax.id = "account_move_line".tax_line_id
              AND repartition.id = "account_move_line".tax_repartition_line_id
              AND repartition.use_in_tax_closing
            GROUP BY tax.tax_group_id, "account_move_line".tax_line_id, tax.name, "account_move_line".account_id
            """,
            tax_name=tax_name,
            table_references=query.from_clause,
            search_condition=query.where_clause,
        )
        self.env.cr.execute(query)
        results = self.env.cr.dictfetchall()
        results = self._postprocess_vat_closing_entry_results(company, company_options, results)

        if results:
            self._ensure_tax_closing_accounts_configured(company)

        tax_group_ids = [r['tax_group_id'] for r in results]
        tax_groups = defaultdict(lambda: defaultdict(list))
        for tg, result in zip(self.env['account.tax.group'].browse(tax_group_ids), results):
            tax_groups[tg][result.get('tax_id')].append(
                (result.get('tax_name'), result.get('account_id'), result.get('amount'))
            )

        # then loop on previous results to
        #    * add the lines that will balance their sum per account
        #    * make the total per tax group's account triplet
        # (if 2 tax groups share the same 3 accounts, they should consolidate in the vat closing entry)
        move_vals_lines = []
        tax_group_subtotal = defaultdict(float)
        currency = company.currency_id
        closing_accounts = self._get_tax_closing_accounts(company)
        for values in tax_groups.values():
            total = 0
            for value in values.values():
                for tax_name, account_id, amt in value:
                    # Line to balance
                    move_vals_lines.append(Command.create({
                        'name': tax_name,
                        'debit': abs(amt) if amt < 0 else 0,
                        'credit': amt if amt > 0 else 0,
                        'account_id': account_id
                    }))
                    total += amt

            if not currency.is_zero(total):
                # Add total to correct group
                tax_group_subtotal[closing_accounts] += total

        # If the tax report is completely empty, we add two 0-valued lines, using the first in in and out
        # account id we find on the taxes.
        if not move_vals_lines:
            rep_ln_in = self.env['account.tax.repartition.line'].search([
                *self.env['account.tax.repartition.line']._check_company_domain(company),
                ('account_id.active', '=', True),
                ('repartition_type', '=', 'tax'),
                ('document_type', '=', 'invoice'),
                ('tax_id.type_tax_use', '=', 'purchase'),
            ], limit=1)
            rep_ln_out = self.env['account.tax.repartition.line'].search([
                *self.env['account.tax.repartition.line']._check_company_domain(company),
                ('account_id.active', '=', True),
                ('repartition_type', '=', 'tax'),
                ('document_type', '=', 'invoice'),
                ('tax_id.type_tax_use', '=', 'sale'),
            ], limit=1)

            if rep_ln_out.account_id and rep_ln_in.account_id:
                move_vals_lines = [
                    Command.create({
                        'name': _('Tax Received Adjustment'),
                        'debit': 0.0,
                        'credit': 0.0,
                        'account_id': rep_ln_out.account_id.id,
                    }),

                    Command.create({
                        'name': _('Tax Paid Adjustment'),
                        'debit': 0.0,
                        'credit': 0.0,
                        'account_id': rep_ln_in.account_id.id,
                    })
                ]

        return move_vals_lines, tax_group_subtotal

    def _vat_closing_entry_results_rounding(self, company, options, results, rounding_accounts, vat_results_summary):
        """
        Apply the rounding from the tax report by adding a line to the end of the query results
        representing the sum of the roundings on each line of the tax report.
        """
        # Ignore if the rounding accounts cannot be found
        if not rounding_accounts.get('profit') or not rounding_accounts.get('loss'):
            return results

        total_amount = 0.0
        tax_group_id = None

        for line in results:
            total_amount += line['amount']
            # The accounts on the tax group ids from the results should be uniform,
            # but we choose the greatest id so that the line appears last on the entry.
            tax_group_id = line['tax_group_id']

        report = self.env['account.report'].browse(options['report_id'])

        for line in report._get_lines(options):
            model, record_id = report._get_model_info_from_id(line.id)

            if model != 'account.report.line':
                continue

            for (operation_type, report_line_id, column_expression_label) in vat_results_summary:
                for column in line.columns:
                    if record_id != report_line_id or column.expression_label != column_expression_label:
                        continue

                    # We accept 3 types of operations:
                    # 1) due and 2) deductible - This is used for reports that have lines for the payable vat and
                    # lines for the reclaimable vat.
                    # 3) total - This is used for reports that have a single line with the payable/reclaimable vat.
                    if operation_type in {'due', 'total'}:
                        total_amount += column.no_format
                    elif operation_type == 'deductible':
                        total_amount -= column.no_format

        currency = company.currency_id
        total_difference = currency.round(total_amount)

        if not currency.is_zero(total_difference):
            results.append({
                'tax_name': _('Difference from rounding taxes'),
                'amount': total_difference * -1,
                'tax_group_id': tax_group_id,
                'account_id': rounding_accounts['profit'].id if total_difference < 0 else rounding_accounts['loss'].id,
            })

        return results

    def _postprocess_vat_closing_entry_results(self, company, options, results):
        # Override this to, for example, apply a rounding to the lines of the closing entry
        return results

    def _get_vat_closing_entry_additional_domain(self):
        return []

    def _get_tax_closing_accounts(self, company):
        """ Resolve the (advance, receivable, payable) accounts the closing entry is keyed on."""
        return (
            self.type_id.with_company(company).advance_tax_payment_account_id.id,
            self.type_id.with_company(company).tax_receivable_account_id.id,
            self.type_id.with_company(company).tax_payable_account_id.id,
        )

    def _create_tax_payable_receivable_line(self, total, payable_account_id, receivable_account_id):
        return Command.create({
            'name': _('Payable tax amount') if total < 0 else _('Receivable tax amount'),
            'debit': total if total > 0 else 0,
            'credit': abs(total) if total < 0 else 0,
            'account_id': payable_account_id if total < 0 else receivable_account_id,
        })

    def _get_carryover_accounts_to_balance(self, key):
        return [(key[0], self.env._('Balance tax advance payment account'))]

    def _add_tax_group_closing_items(self, tax_group_subtotal):
        """Transform the parameter tax_group_subtotal dictionnary into one2many commands.

        Used to balance the tax group accounts for the creation of the vat closing entry.
        """
        def _get_closing_account_balance(account_id):
            return self.env['account.move.line']._read_group(
                [
                    ('date', '<=', self.date_to),
                    ('account_id', '=', account_id),
                    ('company_id', '=', self.company_id.id),
                    ('parent_state', '=', 'posted'),
                ],
                aggregates=['balance:sum'],
            )[0][0]

        currency = self.company_id.currency_id
        line_ids_vals = []
        # keep track of already balanced account, as one can be used in several tax group
        account_already_balanced = []
        for key, value in tax_group_subtotal.items():
            total = value
            receivable_account_id = key[1]
            payable_account_id = key[2]

            for account_id, label in self._get_carryover_accounts_to_balance(key):
                if not account_id or account_id in account_already_balanced:
                    continue
                balance = _get_closing_account_balance(account_id)
                if not currency.is_zero(balance):
                    line_ids_vals.append(Command.create({
                        'name': label,
                        'debit': abs(balance) if balance < 0 else 0,
                        'credit': abs(balance) if balance > 0 else 0,
                        'account_id': account_id,
                    }))
                total += balance
                account_already_balanced.append(account_id)

            # Balance on the receivable/payable tax account
            if not currency.is_zero(total):
                line_ids_vals.append(self._create_tax_payable_receivable_line(total, payable_account_id, receivable_account_id))
        return line_ids_vals

    ####################################################################################################
    ####  Checks
    ####################################################################################################

    def refresh_checks(self):
        """
        Recompute all checks for every return in self of the current state
        """
        # Lock the return records before processing to ensure only one worker can
        # modify them at a time, preventing race conditions in parallel execution.
        locked_returns = self.try_lock_for_update()
        if not self.env['account.return.check'].has_access('write') or not locked_returns:
            return

        to_create = []
        to_unlink = self.env['account.return.check']
        for record in locked_returns:
            if record.company_id not in self.env.companies:  # We do not run checks if the main company is not selected
                continue

            if record._should_run_checks():
                check_codes_to_ignore = set(record.check_ids.filtered(lambda x: x.state != record.state).mapped('code'))
                rslt = record._run_checks(check_codes_to_ignore)
                rslt += record._execute_template_checks(check_codes_to_ignore)

                checks_by_code = record.check_ids.grouped(lambda x: x.code)
                codes_refreshed = set()
                for vals in rslt:
                    codes_refreshed.add(vals['code'])
                    if existing_check := checks_by_code.get(vals['code']):
                        # If a user has updated `result`, we no longer updates its value automatically.
                        if not existing_check.refresh_result:
                            vals.pop('result', None)
                        existing_check.with_user(SUPERUSER_ID).write(vals)
                    else:
                        to_create.append({**vals, 'state': record.state, 'return_id': record.id})

                obsolete_check_codes = checks_by_code.keys() - (codes_refreshed | check_codes_to_ignore)
                if obsolete_check_codes:
                    to_unlink |= record.check_ids.filtered(lambda c: c.code in obsolete_check_codes)
        if to_create:
            self.env['account.return.check'].with_user(SUPERUSER_ID).create(to_create)
        to_unlink.unlink()

    def _should_run_checks(self):
        # To override in order to run checks in other custom-made states
        self.ensure_one()
        return not self.state

    def _execute_template_checks(self, codes_to_ignore):
        def filter_template(template):
            return template.code not in codes_to_ignore \
                and (not template.country_ids or self.company_id.account_fiscal_country_id in template.country_ids)

        def get_action_based_on_account_domain(domain):
            account_domain_context = {}
            if len(domain) == 1:
                field_name, _operator, value = domain[0]
                if field_name == 'account_type':
                    # More user-friendly to activate the side panel filter instead of the audit filter in the search bar
                    account_types = value if isinstance(value, list) else [value]
                    account_domain_context = {
                        'searchpanel_default_account_type': account_types,
                    }

            if not account_domain_context:
                account_domain_context = {
                    'search_default_audit_account_ids': True,
                    'audit_account_ids': self.env['account.account'].search(domain).ids,
                }

            balance_list_view = self.env.ref('account_reports.account_audit_account_balances_list_view')
            balance_search_view = self.env.ref('account_reports.account_audit_account_balances_search_view')

            return {
                'type': 'ir.actions.act_window',
                'name': template.name,
                'views': [(balance_list_view.id, 'list'), [False, 'form']],
                'search_view_id': [balance_search_view.id, 'search'],
                'view_mode': 'list',
                'res_model': model._name,
                'context': {
                    'working_file_id': self.id,
                    **account_domain_context,
                },
            }

        return_type = self.type_id
        check_templates = self.env['account.return.check.template']
        check_template_domain = [('return_type', '=', return_type.id)]
        if self.return_type_category == 'audit':
            check_template_domain.append(('cycle_id', 'in', self.cycle_ids.ids))

            if 'equity' in self.cycle_ids.mapped('code'):
                # Little hack to have it in every l10n-specific audits as well, without needing to redefine it every time
                interco_reco = self.env.ref('account_reports.account_return_check_template_intercompany_account_reconciliation', raise_if_not_found=False)
                if interco_reco:  # In case it's been manually deleted
                    check_templates |= interco_reco

        check_templates |= self.env['account.return.check.template'].search(check_template_domain)

        existing_checks_from_template = self.check_ids.filtered(lambda r: r.template_id)
        existing_check_by_template_id = {
            check.template_id: check for check in existing_checks_from_template
        }

        vals_list = []

        for template in check_templates.filtered(filter_template):
            action = template.action_id
            vals_dict = {
                'code': template.code,
                'name': template.name,
                'message': template.description,
                'type': template.type,
                'action': False,
            }

            if action:
                action_record = self.env[action.sudo().type].browse(action.sudo().id)
                vals_dict['action'] = action_record._get_action_dict()

            if template not in existing_check_by_template_id:
                vals_dict.update({
                    'template_id': template.id,
                })
            elif existing_check_by_template_id[template].type != template.type:
                # If the existing check type does not match we have to reset the result
                vals_dict['result'] = 'todo'
                if existing_check_by_template_id[template].type == 'file' and existing_check_by_template_id[template].attachment_ids:
                    existing_check_by_template_id[template].attachment_ids.unlink()

            if template.activity_type:
                current_template_activities = self.activity_ids.filtered(lambda act: act.summary == template.name)
                activities_to_unlink = current_template_activities.filtered(lambda act: act.state != 'done')
                activities_kept = current_template_activities - activities_to_unlink
                activities_to_unlink.unlink()
                if not activities_kept:
                    self.activity_schedule(activity_type_id=template.activity_type.id, summary=template.name, note=template.description)

            if template.type == 'check' and template.model:
                ir_model = self.env['ir.model']._get(template.model)
                model = self.env[template.model]
                domain = []
                if template.domain:
                    evaluation_context = self._get_evaluation_context()
                    domain = self.env['account.return.check']._parse_expression(template.domain, evaluation_context)

                if model._name == 'account.account':
                    query_account = self.env['account.account']._search(domain)
                    account_status = self.env['account.audit.account.status'].search([('audit_id', '=', self.id), ('account_id', 'in', query_account)])
                    status_priority = {'anomaly': 0, 'todo': 1, 'reviewed': 2, 'supervised': 3}
                    minimum_status = min(
                        (entry.status or 'reviewed' for entry in account_status),
                        key=lambda s: status_priority[s]
                    ) if account_status else 'reviewed'

                    vals_dict.update({'result': minimum_status})

                    if not template.action_id:
                        vals_dict['action'] = get_action_based_on_account_domain(domain)

                else:
                    domain = template._transform_custom_check_template_domain([
                        *domain,
                        ('date', '>=', fields.Date.to_string(self.date_from)),
                        ('date', '<=', fields.Date.to_string(self.date_to)),
                        ('company_id', 'in', self.company_ids.ids),
                    ])
                    entries = model.sudo().search(domain, limit=LIMIT_CHECK_ENTRIES)
                    if entries:
                        if action := template._get_default_check_action_from_model():
                            action['domain'] = [
                                *action.get('domain', []),
                                *domain
                            ]
                        else:
                            action = {
                                'type': 'ir.actions.act_window',
                                'name': template.name,
                                'view_mode': 'list',
                                'res_model': model._name,
                                'domain': domain,
                                'views': [[False, 'list'], [False, 'form']],
                            }
                        action['context'] = {
                            'working_file_id': self.id,
                            **action.get('context', {}),
                        }
                        vals_dict.update({
                            'action': action,
                            'records_count': len(entries),
                            'records_model': ir_model.id,
                            'result': 'anomaly',
                        })
                    else:
                        vals_dict.update({
                            'records_count': 0,
                            'result': 'reviewed'
                        })

            vals_list.append(vals_dict)

        return vals_list

    def _run_checks(self, check_codes_to_ignore):
        """
        To override in l10n for specific checks by type
        """
        self.ensure_one()
        checks = []
        report_country = self.type_id.report_id.country_id
        europe_country_group = self.env.ref('base.europe')
        if report_country.code in europe_country_group.mapped('country_ids.code'):
            checks += self._check_suite_eu_vat_report(check_codes_to_ignore)

        if self.is_tax_return:
            checks += self._check_suite_common_vat_report(check_codes_to_ignore)
        elif self.is_ec_sales_list_return:
            checks += self._check_suite_common_ec_sales_list(check_codes_to_ignore)
        if self.type_external_id == 'account_reports.annual_corporate_tax_return_type':
            checks += self._check_suite_annual_closing(check_codes_to_ignore)

        return checks

    def _get_company_required_fields(self):
        self.ensure_one()
        company = self.company_id
        return [company.vat, company.country_id, company.phone, company.email]

    def _check_suite_common_vat_report(self, check_codes_to_ignore):
        checks = []
        # check company configuration
        exists_check_company_data = self.check_ids.filtered(lambda c: c.code == 'check_company_data')
        invalid_fields_count = sum(1 for field in self._get_company_required_fields() if not field)
        if 'check_company_data' not in check_codes_to_ignore and (invalid_fields_count or exists_check_company_data):
            review_action = {
                'type': 'ir.actions.act_window',
                'name': _('Set your company data'),
                'res_model': 'res.company',
                'res_id': self.company_id.id,
                'views': [(self.env.ref('account.res_company_form_view_onboarding').id, "form")],
                'target': 'new',
            }

            checks.append({
                'name': _lt("Company data"),
                'message': _lt(
                    "Missing company details (like %(vat_label)s or country) can cause errors in your report, "
                    "such as using the wrong tax rate, wrongly exempting transactions.",
                    vat_label=self.company_id.partner_id.vat_label,
                ),
                'code': 'check_company_data',
                'records_count': invalid_fields_count,
                'action': review_action,
                'result': 'anomaly' if invalid_fields_count else 'reviewed',
            })

        if 'check_match_all_bank_entries' not in check_codes_to_ignore:
            checks.append(self._check_match_all_bank_entries(
                    code='check_match_all_bank_entries',
                    name=_lt("Bank Matching"),
                    message=_lt("Bank reconciliation helps identify missing invoices or bills that may affect taxes."),
                )
            )

        if self.company_id.tax_exigibility and 'check_caba_sequence' not in check_codes_to_ignore:
            checks.append(self._check_caba_sequence(
                    code='check_caba_sequence',
                    name=_lt("Cash Basis sequences"),
                    message=_lt("All the Journal Entries used to record received taxes amounts in the Cash Basis journal are in sequence."),
                )
            )

        if 'check_draft_entries' not in check_codes_to_ignore:
            check_codes_to_ignore.add('check_draft_entries')
            checks.append(self._check_draft_entries(
                    code='check_draft_entries',
                    name=_lt("Drafts & Reviews"),
                    message=_lt("Review invoices, bills and entries which are either in draft or marked as Anomaly/To Review."),
                    exclude_entries=True,
                )
            )

        if 'check_bills_attachment' not in check_codes_to_ignore:
            domain = [
                ('attachment_ids', '=', False),
                ('message_main_attachment_id', '=', False),
                ('move_type', '=', 'in_invoice'),
                ('company_id', 'in', self.company_ids.ids),
                ('date', '<=', fields.Date.to_string(self.date_to)),
                ('date', '>=', fields.Date.to_string(self.date_from)),
                ('state', '=', 'posted'),
            ]
            bills_without_attachments_count = self.env['account.move'].sudo().search_count(domain, limit=LIMIT_CHECK_ENTRIES)

            review_action = {
                'type': 'ir.actions.act_window',
                'name': _("Bill Attachments"),
                'view_mode': 'list',
                'res_model': 'account.move',
                'domain': domain,
                'views': [[self.env.ref('account_reports.view_audit_check_invoices_list').id, 'list'], [False, 'form']],
            }

            checks.append({
                'name': _lt("Bill attachments"),
                'code': 'check_bills_attachment',
                'message': _lt("Each bill should have its own document attached as a proof in case of audit."),
                'records_count': bills_without_attachments_count,
                'records_model': self.env['ir.model']._get('account.move').id,
                'action': review_action if bills_without_attachments_count else None,
                'result': 'anomaly' if bills_without_attachments_count else 'reviewed',
            })

        if 'check_tax_countries' not in check_codes_to_ignore:
            self.env['account.move'].flush_model()
            self.env['account.fiscal.position'].flush_model()
            self.env['res.partner'].flush_model()
            self.env['res.country.group'].flush_model()

            self.env.cr.execute(SQL(
                """
                SELECT ARRAY_AGG(move.id)
                FROM account_move move
                JOIN account_fiscal_position fpos
                    ON fpos.id = move.fiscal_position_id
                JOIN res_partner partner
                    ON partner.id = move.commercial_partner_id
                WHERE
                    move.state = 'posted'
                    AND move.company_id IN %(company_ids)s
                    AND move.move_type IN %(invoice_types)s
                    AND move.date >= %(date_from)s
                    AND move.date <= %(date_to)s
                    AND (fpos.country_id IS NOT NULL OR fpos.country_group_id IS NOT NULL)
                    AND (fpos.country_id IS NULL OR partner.country_id IS NULL OR fpos.country_id != partner.country_id)
                    AND (
                        fpos.country_group_id IS NULL
                        OR partner.country_id IS NULL
                        OR NOT EXISTS (
                            SELECT 1
                            FROM res_country_res_country_group_rel group_rel
                            WHERE group_rel.res_country_id = partner.country_id
                            AND group_rel.res_country_group_id = fpos.country_group_id
                        )
                    )
                """,
                company_ids=tuple(self.company_ids.ids),
                invoice_types=tuple(self.env['account.move'].get_invoice_types()),
                date_from=fields.Date.to_string(self.date_from),
                date_to=fields.Date.to_string(self.date_to),
            ))

            country_error_move_ids = self.env.cr.fetchone()[0]
            country_error_moves_count = len(country_error_move_ids or [])

            review_action = {
                'type': 'ir.actions.act_window',
                'view_mode': 'list',
                'res_model': 'account.move',
                'domain': [('id', 'in', country_error_move_ids)],
                'views': [[self.env.ref('account_reports.view_audit_check_invoices_list').id, 'list'], [False, 'form']],
            }

            checks.append({
                'name': _lt("Tax Rate & Country Consistency"),
                'code': 'check_tax_countries',
                'message': _lt("Ensures that applied taxes and fiscal positions match the customer or vendor country location."),
                'records_count': country_error_moves_count,
                'records_model': self.env['ir.model']._get('account.move').id,
                'action': review_action if country_error_move_ids else None,
                'result': 'anomaly' if country_error_move_ids else 'reviewed',
            })

        if 'check_inactive_tags' not in check_codes_to_ignore:
            domain = [
                ('date', '<=', fields.Date.to_string(self.date_to)),
                ('date', '>=', fields.Date.to_string(self.date_from)),
                ('company_id', 'in', self.company_ids.ids),
                ('parent_state', '=', 'posted'),
                ('tax_tag_ids', 'any', [
                    ('applicability', '=', 'taxes'),
                    ('active', '=', False),
                    '|', ('country_id', '=', False), ('country_id', '=', self.type_id.country_id.id),
                ]),
            ]
            nb_inactive_tag = self.env['account.move.line'].search_count(domain)
            if nb_inactive_tag or self.check_ids.filtered(lambda check: check.code == 'check_inactive_tags'):
                # This check is not created if there is no inactive tag and is never deleted
                review_action = {
                    'type': 'ir.actions.act_window',
                    'name': _("Journal Items with Archived Tax Grids"),
                    'view_mode': 'list',
                    'res_model': 'account.move.line',
                    'domain': domain,
                    'views': [[False, 'list'], [False, 'form']],
                }
                checks.append({
                    'name': _lt("Archived Tax Grids"),
                    'code': 'check_inactive_tags',
                    'message': _lt('Some journal items appear to point to obsolete report lines. '
                                   'Check them, and correct their tax grids if necessary.'),
                    'records_count': nb_inactive_tag,
                    'records_model': self.env['ir.model']._get('account.move.line').id,
                    'action': review_action,
                    'result': 'anomaly' if nb_inactive_tag else 'reviewed',
                })

        if 'check_vat_reconciliation' not in check_codes_to_ignore:
            action = {
                'name': self.env._("Journal Items"),
                'type': 'ir.actions.act_window',
                'res_model': 'account.move.line',
                'view_mode': 'pivot',
                'views': [(False, 'pivot')],
                'context': {
                    'active_test': False,
                    'pivot_row_groupby': ['tax_ids', 'account_id'],
                    'pivot_column_groupby': ['fiscal_position_id', 'commercial_partner_country'],
                    'search_default_posted': True,
                    'search_default_sales': True,
                    'search_default_purchases': True,
                    'search_default_date_between': True,
                    'date_from': self.date_from,
                    'date_to': self.date_to,
                },
            }

            checks.append({
                'name': _lt("Tax Reconciliation"),
                'message': _lt("Audit journal items and accounts to ensure they are correctly assigned to taxes."),
                'code': 'check_vat_reconciliation',
                'result': 'todo',
                'action': action,
            })

        return checks

    def _check_suite_annual_closing(self, check_codes_to_ignore):
        def get_unknown_partner_aml_ids(internal_type):
            report = self.env.ref("account_reports.aged_payable_report") if internal_type == 'liability_payable' else self.env.ref("account_reports.aged_receivable_report")
            options = report.get_options({
                'date': {
                    'date_to': self.date_to,
                },
            })
            query = report._get_report_query(options, 'strict_range', domain=[('account_id.account_type', '=', internal_type), ('partner_id', '=', False)])
            return [r[0] for r in self.env.execute_query(query.select(SQL("account_move_line.id")))]

        def has_overdue_aged_balance(internal_type):
            report = self.env.ref("account_reports.aged_payable_report") if internal_type == 'liability_payable' else self.env.ref("account_reports.aged_receivable_report")
            options = report.get_options({
                'date': {
                    'date_to': self.date_to,
                },
            })
            threshold_date = self.date_to - relativedelta(days=60)
            aging_date_field = SQL.identifier('invoice_date') if options['aging_based_on'] == 'base_on_invoice_date' else SQL.identifier('date_maturity')
            query = report._get_report_query(options, 'strict_range', domain=[('account_id.account_type', '=', internal_type)])
            query.add_where(SQL("COALESCE(account_move_line.%s, account_move_line.date) <= %s", aging_date_field, threshold_date))
            query.limit = 1
            return self.env.execute_query(query.select(SQL("1")))

        checks = []
        if 'check_bank_reconcile' not in check_codes_to_ignore:
            checks.append(self._check_match_all_bank_entries(
                    code='check_bank_reconcile',
                    name=_lt("Bank Reconciliation"),
                    message=_lt("Reconcile all bank account transactions up to year-end."),
                )
            )

        if 'check_draft_entries' not in check_codes_to_ignore:
            checks.append(self._check_draft_entries(
                    code='check_draft_entries',
                    name=_lt("No draft entries"),
                    message=_lt("Review and post draft invoices, bills and entries in the period, or change their accounting date."),
                )
            )

        if 'check_unkown_partner_receivables' not in check_codes_to_ignore:
            aml_ids = get_unknown_partner_aml_ids('asset_receivable')
            action = {
                'type': 'ir.actions.act_window',
                'name': self.env._("Unknown partner receivables"),
                'view_mode': 'list',
                'res_model': 'account.move.line',
                'domain': [('id', 'in', aml_ids)],
                'views': [[False, 'list']],
            }
            checks.append({
                'name': _lt("Aged receivables per partner"),
                'message': _lt("Review receivables without a partner."),
                'code': 'check_unkown_partner_receivables',
                'action': action if aml_ids else None,
                'result': 'anomaly' if aml_ids else 'reviewed',
            })

        if 'check_overdue_receivables' not in check_codes_to_ignore:
            has_overdue_receivables = has_overdue_aged_balance('asset_receivable')
            action = None
            if has_overdue_receivables:
                action = self.env['account.return.check'].action_audit_report(self.id, "account_reports.action_account_report_ar")
            checks.append({
                'name': _lt("Overdue receivables"),
                'message': _lt(
                    "Review overdue receivables aged over 60 days and assess the need for an allowance for doubtful "
                    "accounts or expected credit loss provision, as per IFRS 9 guidelines."
                ),
                'code': 'check_overdue_receivables',
                'action': action,
                'result': 'anomaly' if has_overdue_receivables else 'reviewed',
            })

        if 'check_total_receivables' not in check_codes_to_ignore:
            checks.append({
                'name': _lt("Total Receivables"),
                'message': _lt("Verify that the total aged receivables equals the customer account balance."),
                'code': 'check_total_receivables',
                'result': 'reviewed',
            })

        if 'check_unkown_partner_payables' not in check_codes_to_ignore:
            aml_ids = get_unknown_partner_aml_ids('liability_payable')
            action = {
                'type': 'ir.actions.act_window',
                'name': self.env._("Unknown partner payables"),
                'view_mode': 'list',
                'res_model': 'account.move.line',
                'domain': [('id', 'in', aml_ids)],
                'views': [[False, 'list']],
            }
            checks.append({
                'name': _lt("Aged payables per partner"),
                'message': _lt("Review payables without a partner."),
                'code': 'check_unkown_partner_payables',
                'action': action if aml_ids else None,
                'result': 'anomaly' if aml_ids else 'reviewed',
            })

        if 'check_overdue_payables' not in check_codes_to_ignore:
            has_overdue_payables = has_overdue_aged_balance('liability_payable')
            action = None
            if has_overdue_payables:
                action = self.env['account.return.check'].action_audit_report(self.id, "account_reports.action_account_report_ap")
            checks.append({
                'name': _lt("Overdue payables"),
                'message': _lt("Review overdue payables aged over 60 days and assess the need for an allowance for uncertain liabilities."),
                'code': 'check_overdue_payables',
                'action': action,
                'result': 'anomaly' if has_overdue_payables else 'reviewed',
            })

        if 'check_total_payables' not in check_codes_to_ignore:
            checks.append({
                'name': _lt("Total payables"),
                'message': _lt("Verify that the total aged payables equals the vendor account balance."),
                'code': 'check_total_payables',
                'result': 'reviewed',
            })

        if 'check_deferred_entries' not in check_codes_to_ignore:
            domain = [
                ('company_id', 'in', self.company_ids.ids),
                ('date', '<=', fields.Date.to_string(self.date_to)),
                ('date', '>=', fields.Date.to_string(self.date_from)),
                ('deferred_original_move_ids', '!=', False),
            ]
            deferred_entries_count = self.env['account.move'].sudo().search_count(domain, limit=LIMIT_CHECK_ENTRIES)
            if not deferred_entries_count:
                checks.append({
                    'name': _lt("Deferred Entries"),
                    'message': _lt(
                        "Odoo manages your deferred entries automatically. No deferred entries were found for this period. "
                        "Ensure your start and end dates are correctly set on your bills and invoices."
                    ),
                    'code': 'check_deferred_entries',
                    'records_count': deferred_entries_count,
                    'records_model': self.env['ir.model']._get('account.move').id,
                    'result': 'todo',
                })

        if 'manual_adjustments' not in check_codes_to_ignore:
            checks.append({
                'name': _lt("Manual Adjustments"),
                'message': _lt("Complete any necessary manual adjustments and internal checks."),
                'code': 'manual_adjustments',
                'result': 'todo',
            })

        if 'earnings_allocation' not in check_codes_to_ignore:
            action = self.env['account.return.check'].action_audit_report(self.id, "account_reports.action_account_report_bs")
            checks.append({
                'name': _lt("Earnings Allocation"),
                'message': _lt("After adjustements, transfer the undistributed Profits/Losses to an equity account."),
                'code': 'earnings_allocation',
                'action': action,
                'result': 'todo',
            })

        if self.company_id.tax_exigibility and 'check_caba_sequence' not in check_codes_to_ignore:
            checks.append(self._check_caba_sequence(
                    code='check_caba_sequence',
                    name=_lt("Cash Basis sequences"),
                    message=_lt("All the Journal Entries used to record received taxes amounts in the Cash Basis journal are in sequence."),
                )
            )

        return checks

    def _check_suite_eu_vat_report(self, check_codes_to_ignore):
        checks = []
        self._generic_vies_vat_check(check_codes_to_ignore, checks)
        check_codes_to_ignore.add('check_partner_vies')
        return checks

    def _generic_vies_vat_check(self, check_codes_to_ignore, checks):
        is_l10n_eu_account_vies_installed = 'l10n_eu_account_vies' in self.env['ir.module.module']._installed()
        use_vies = is_l10n_eu_account_vies_installed and self.company_id.vat_check_vies
        if 'check_partner_vies' not in check_codes_to_ignore and use_vies:
            european_country_group = self.env.ref('base.europe')
            invalid_vies_partners = self.env['account.move'].sudo()._read_group(
                domain=[
                    ('partner_id.country_id', 'in', european_country_group.country_ids.ids),
                    ('partner_id.country_id', '!=', self.company_id.account_fiscal_country_id.id),
                    ('partner_id.vies_valid', '=', False),
                    ('company_id', 'in', self.company_ids.ids),
                    ('date', '<=', fields.Date.to_string(self.date_to)),
                    ('date', '>=', fields.Date.to_string(self.date_from)),
                    ('fiscal_position_id.vat_required', '=', True),
                ],
                aggregates=['partner_id:recordset'],
            )[0][0]

            invalid_vies_partners_count = len(invalid_vies_partners)
            checks.append({
                'name': _lt("Valid VAT Numbers"),
                'code': 'check_partner_vies',
                'message': _lt(
                    'All customer VAT numbers are valid under %s.',
                    Markup('<a href="https://ec.europa.eu/taxation_customs/vies" target="_blank">')
                    + _lt('VIES')
                    + Markup('</a>'),
                ),
                'records_count': invalid_vies_partners_count,
                'records_model': self.env['ir.model']._get('res.partner').id,
                'action': (
                    invalid_vies_partners._get_records_action(name=self.env._("Valid VAT Numbers"))
                    if invalid_vies_partners_count
                    else None
                ),
                'result': 'anomaly' if invalid_vies_partners_count else 'reviewed',
            })

    def _check_suite_common_ec_sales_list(self, check_codes_to_ignore):
        checks = []

        options = self._get_closing_report_options()
        is_using_taxes = 'ec_sales_taxes_to_include' in options

        if 'goods_service_classification' not in check_codes_to_ignore or 'reverse_charge_mentioned' not in check_codes_to_ignore:

            if is_using_taxes:
                ec_sales_tax_or_tag_domain = ('tax_ids', 'in', options.get('ec_sales_taxes_to_include', []))
            else:
                tax_tag_ids = list({
                    tag
                    for sale_type in options['sales_report_operation_types'].values()
                    for tag in sale_type['tax_tag_ids']
                })
                ec_sales_tax_or_tag_domain = ('tax_tag_ids', 'in', tax_tag_ids)

            ec_sales_aml_domain = [
                *self.type_id.report_id._get_options_domain(options, 'strict_range'),
                ec_sales_tax_or_tag_domain,
            ]

            if 'goods_service_classification' not in check_codes_to_ignore:
                checks.append({
                    'name': _lt("Goods and services classification"),
                    'message': _lt("Review the tax code and ensure each transaction is correctly classified as a supply of goods or services."),
                    'code': 'goods_service_classification',
                    'result': 'todo',
                    'action': {
                        'type': 'ir.actions.act_window',
                        'name': _("Journal Items"),
                        'res_model': 'account.move.line',
                        'domain': ec_sales_aml_domain,
                        'views': [(False, 'list')],
                    },
                })

            if 'reverse_charge_mentioned' not in check_codes_to_ignore:
                checks.append({
                    'name': _lt("Reverse charge mention"),
                    'message': _lt('Make sure the "Reverse Charge" mention appears on all invoices.'),
                    'code': 'reverse_charge_mentioned',
                    'result': 'todo',
                    'action': {
                        'type': 'ir.actions.act_window',
                        'name': _("Invoices"),
                        'res_model': 'account.move',
                        'domain': [('line_ids', 'any', ec_sales_aml_domain)],
                        'views': [(False, 'list'), (False, 'form')],
                    },
                })

        if any(code not in check_codes_to_ignore for code in ('eu_cross_border', 'no_partners_without_vat')):
            warnings = {}
            custom_handler = self.env[self.type_id.report_id._get_custom_handler_model()]

            ec_sales_report = self.env['account.report'].browse(options['report_id'])

            engine_results = custom_handler._report_engine_ec_sales_report(
                options,
                'strict_range',
                ec_sales_report.line_ids[0].expression_ids.grouped('formula'),
                'partner_id',
            )

            custom_handler._report_engine_ec_sales_report(
                options,
                'strict_range',
                ec_sales_report.line_ids[0].expression_ids.grouped('formula'),
                None,
                warnings=warnings,
            )

            partner_ids = self.env['res.partner'].browse([partner_id for formula_res in engine_results.values() for partner_id, _ec_results in formula_res])

            if 'eu_cross_border' not in check_codes_to_ignore:
                cross_border_failure = 'account_reports.sales_report_warning_non_ec_country' in warnings or 'account_reports.sales_report_warning_same_country' in warnings

                cross_border_action = False
                if cross_border_failure:
                    options['same_country_warning'] = self.company_id.country_id.code
                    same_country_action = custom_handler.get_warning_act_window(options, {'type': 'same_country', 'model': 'partner'})
                    non_ec_country_action = custom_handler.get_warning_act_window(options, {'type': 'non_ec_country', 'model': 'partner'})
                    cross_border_action = {
                        **same_country_action,
                        'name': _("Partners in Wrong Country"),
                        'domain': ['|', *same_country_action['domain'], *non_ec_country_action['domain']],
                    }

                checks.append({
                    'name': _lt("Only intra-EU customers"),
                    'message': _lt("Exclude any domestic or extra-EU sales from the EC Sales List."),
                    'code': 'eu_cross_border',
                    'result': 'anomaly' if cross_border_failure else 'reviewed',
                    'action': cross_border_action,
                })

            if 'no_partners_without_vat' not in check_codes_to_ignore:
                no_vat_partners = partner_ids.filtered(lambda partner: not partner.vat)
                checks.append({
                    'name': _lt("VAT Numbers"),
                    'message': _lt("All customers have a VAT number."),
                    'code': 'no_partners_without_vat',
                    'result': 'anomaly' if no_vat_partners else 'reviewed',
                    'action': (
                        no_vat_partners._get_records_action(name=self.env._("Partners without VAT"))
                        if no_vat_partners else None
                    ),
                })

            if 'no_duplicate_vat' not in check_codes_to_ignore:
                vat_count = defaultdict(int)
                duplicate_vats = set()

                for formula_res in engine_results.values():
                    for partner_id, partner_info in formula_res:
                        vat_key = f"{partner_info['country_code']}{partner_info['vat_number']}"
                        vat_count[vat_key] += 1
                        if vat_count[vat_key] == 2:
                            duplicate_vats.add(vat_key)

                action = custom_handler._get_duplicate_vat_partners(list(duplicate_vats))
                checks.append({
                    'name': _lt("Duplicate VAT"),
                    'message': _lt("All customers have a different VAT number."),
                    'code': 'no_partners_with_duplicate_vat',
                    'result': 'anomaly' if duplicate_vats else 'reviewed',
                    'action': action if duplicate_vats else None
                })

            if 'no_service_sales_to_xi_customers' not in check_codes_to_ignore and not is_using_taxes:
                xi_partner_with_service_sales = [
                    partner_id
                    for partner_id, partner_info in next(iter(engine_results.values()))
                    if partner_info.get('country_code') == 'XI' and partner_info.get('services')
                ]

                if xi_partner_with_service_sales:
                    services_tags = self.env['account.account.tag'].browse(custom_handler._get_ec_sales_tax_tags().get('services'))
                    checks.append({
                        'name': _lt("Service Sales to North-Irish Customers"),
                        'message': _lt(
                            "Inconsistent tax on service sale to Northern Ireland. Such services must be treated "
                            "strictly as a third country (non-EU) transaction, and should not use intra-community taxes."
                        ),
                        'code': 'no_service_sales_to_xi_customers',
                        'result': 'anomaly',
                        'action': {
                            'type': 'ir.actions.act_window',
                            'name': self.env._("North-Irish customers with intra-com service sales"),
                            'res_model': 'account.move',
                            'domain': [
                                ('partner_id', 'in', xi_partner_with_service_sales),
                                ('state', '=', 'posted'),
                                ('date', '<=', self.date_to),
                                ('date', '>=', self.date_from),
                                ('company_id', 'in', self.company_ids.ids),
                                ('line_ids', 'any', [('tax_tag_ids', 'in', services_tags.ids)])
                            ],
                            'view_mode': 'list',
                            'views': [[False, 'list'], [False, 'form']],
                        },
                    })

        self._generic_vies_vat_check(check_codes_to_ignore, checks)

        return checks

    def _check_match_all_bank_entries(self, code, name, message):
        domain = [
            ('is_reconciled', '=', False),
            ('state', '!=', 'cancel'),
            ('company_id', 'in', self.company_ids.ids),
            ('date', '<=', fields.Date.to_string(self.date_to)),
            ('date', '>=', fields.Date.to_string(self.date_from)),
        ]

        unreconciled_bank_entries_count = self.env['account.bank.statement.line'].sudo().search_count(domain, limit=LIMIT_CHECK_ENTRIES)

        review_action = {
            'type': 'ir.actions.act_window',
            'name': str(name),  # If it is _lt, we need to stringify it because it cannot be json dumped
            'view_mode': 'list',
            'res_model': 'account.bank.statement.line',
            'domain': domain,
            'views': [[False, 'kanban']],
        }

        return {
            'name': name,
            'message': message,
            'code': code,
            'records_count': unreconciled_bank_entries_count,
            'records_model': self.env['ir.model']._get('account.bank.statement.line').id,
            'action': review_action if unreconciled_bank_entries_count else None,
            'result': 'anomaly' if unreconciled_bank_entries_count else 'reviewed',
        }

    def action_open_account_return(self):
        self.ensure_one()
        if not self.check_ids:
            self.refresh_checks()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Tax Return'),
            'res_model': 'account.return.check',
            'view_mode': 'kanban',
            'context': {
                'active_model': self._name,
                'active_id': self.id,
                'active_ids': [self.id],
                'account_return_view_id': self.env.ref('account_reports.account_return_kanban_view').id,
                'max_number_opened_groups': 100000,
                'open_attachments_in_chatter': True,
            },
            'domain': [['return_id', '=', self.id]],
            'views': [(self._get_checks_kanban_view_id(), 'kanban')],
        }

    def _get_checks_kanban_view_id(self):
        """
        Can be overidden to allow some conditional extension to the check view.
        """
        self.ensure_one()
        return self.env.ref('account_reports.account_return_check_kanban_view').id

    def _check_draft_entries(self, code, name, message, exclude_entries=False):
        domain = [
            '|',
            ('state', '=', 'draft'),
            ('review_state', 'in', ['anomaly', 'todo']),
            ('company_id', 'in', self.company_ids.ids),
            ('date', '<=', fields.Date.to_string(self.date_to)),
            ('date', '>=', fields.Date.to_string(self.date_from)),
        ]
        if exclude_entries:
            domain += [
                '|',
                ('move_type', '!=', 'entry'),
                ('line_ids.tax_ids', '!=', False)
            ]
        draft_entries_count = self.env['account.move'].sudo().search_count(domain, limit=LIMIT_CHECK_ENTRIES)

        review_action = {
            'type': 'ir.actions.act_window',
            'name': str(name),  # If it is _lt, we need to stringify it because it cannot be json dumped
            'view_mode': 'list',
            'res_model': 'account.move',
            'domain': domain,
            'views': [[self.env.ref('account_reports.view_audit_check_invoices_list').id, 'list'], [False, 'form']],
        }

        return {
            'name': name,
            'code': code,
            'message': message,
            'records_count': draft_entries_count,
            'records_model': self.env['ir.model']._get('account.move').id,
            'action': review_action if draft_entries_count else None,
            'result': 'anomaly' if draft_entries_count else 'reviewed',
        }

    def _check_caba_sequence(self, code, name, message):
        caba_journal = self.company_id.tax_cash_basis_journal_id
        domain = [
            ('state', '=', 'posted'),
            ('company_id', 'in', self.company_ids.ids),
            ('date', '<=', fields.Date.to_string(self.date_to)),
            ('date', '>=', fields.Date.to_string(self.date_from)),
            ('journal_id', '=', caba_journal.id),
            ('tax_cash_basis_rec_id', '!=', False),
        ]
        needs_resequence = bool(
            self.env['account.move'].sudo().search_count(
                domain + [('made_sequence_gap', '=', 'true')],
                limit=1,
            ))

        review_action = {
            'type': 'ir.actions.act_window',
            'name': str(name),  # If it is _lt, we need to stringify it because it cannot be json dumped
            'view_mode': 'list',
            'res_model': 'account.move',
            'domain': domain,
            'views': [[self.env.ref('account_reports.view_audit_check_invoices_list').id, 'list'], [False, 'form']],
        } if needs_resequence else None

        return {
            'name': name,
            'code': code,
            'message': message,
            'records_count': 0,
            'records_model': self.env['ir.model']._get('account.move').id,
            'action': review_action,
            'result': 'anomaly' if needs_resequence else 'reviewed',
        }

    def get_kanban_view_and_search_view_id(self):
        if self.return_type_category == 'audit':
            kanban_view_xml_id = 'account_reports.account_audit_kanban_view'
            search_view_xml_id = 'account_reports.account_audit_search_view'
        else:
            kanban_view_xml_id = 'account_reports.account_return_kanban_view'
            search_view_xml_id = 'account_reports.account_return_search_view'
        return (self.env.ref(kanban_view_xml_id).id, self.env.ref(search_view_xml_id).id)

    @api.model
    def _get_nth_working_day(self, from_date, n):
        """
        Calculate the date of the Nth working day starting from a given date.

        A working day is defined as a weekday (Monday to Friday).
        Weekends (Saturday and Sunday) are skipped.

        :param from_date : The start date (inclusive).
        :param n : The Nth working day to find (e.g., n=1 returns the first working day on or after `from_date`).

        :returns: The date of the Nth working day after `from_date`.
        :rtype: datetime.date
        :raises UserError: if n is less than 1
        """

        def is_working_day(day):
            return day.isoweekday() <= 5

        if n <= 0:
            raise UserError(self.env._("n must be a positive integer."))

        current_date = from_date
        n -= int(is_working_day(current_date))
        while n > 0:
            current_date += relativedelta(days=1)
            n -= int(is_working_day(current_date))
        return current_date

    def _get_evaluation_context(self):
        def generate_journals_options():
            options = self.env.ref('account_reports.trial_balance_report').get_options({})
            journals = options.get('journals', [])
            for journal in journals:
                journal['selected'] = journal['type'] == 'cash'
            return journals

        self.ensure_one()

        company = self.company_id
        return {
            'active_id': self.id,
            'active_ids': [self.id],
            'active_model': self._name,
            'return_start_date': fields.Date.to_string(self.date_from),
            'return_end_date': fields.Date.to_string(self.date_to),
            'return_last_month_start': fields.Date.to_string(fields.Date.start_of(self.date_to, 'month')),
            'ref': lambda xml_id: self.env.ref(xml_id).id,
            'internal_transfer_account_id': company.transfer_account_id.id,
            'currency_exchange_difference_account_ids': (company.income_currency_exchange_account_id + company.expense_currency_exchange_account_id).ids,
            'company_currency_id': company.currency_id.id,
            'company_country_code': company.account_fiscal_country_id.code,
            'company_id': company.id,
            'cash_journal_options': generate_journals_options(),
        }


class AccountReturnCheck(models.Model):
    _name = "account.return.check"
    _description = "Accounting Return Check"
    _order = "name, id"

    code = fields.Char(string="Check ID", required=True)
    type = fields.Selection(
        selection=CHECK_TYPES,
        string="Type",
        default='check',
        required=True,
    )
    template_id = fields.Many2one(
        comodel_name='account.return.check.template',
        string="Template",
        ondelete='set null',
    )

    # Refreshed fields
    name = fields.Char(string="Name", required=True, translate=True)
    message = fields.Html(string="Description", translate=True)
    state = fields.Char(string="Return State To Check For")
    records_count = fields.Integer(readonly=True)
    records_name = fields.Char(compute='_compute_records_name', compute_sudo=True)  # sudo is necessary because we're accessing ir.model
    records_model = fields.Many2one(string="Model", comodel_name='ir.model')
    action = fields.Json()
    result = fields.Selection(
        selection=REVIEW_STATE_SELECTION,
        default='todo',
        required=True,
    )
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        string="Attachment",
        bypass_search_access=True,
    )

    # Return related
    return_id = fields.Many2one(comodel_name='account.return', string="Account Return", required=True, index=True, ondelete="cascade")
    is_return_active = fields.Boolean(related="return_id.active")
    return_state = fields.Char(string="Return State", related="return_id.state", store=True)
    return_name = fields.Char(string="Return Name", related="return_id.name")
    date_deadline = fields.Date("Deadline", related="return_id.date_deadline")
    is_main_company_active = fields.Boolean(related="return_id.is_main_company_active")

    # Editable fields
    refresh_result = fields.Boolean(default=True)
    approver_ids = fields.Many2many(
        comodel_name='res.users',
        string="Approved By",
        readonly=True,
        context={"active_test": False},
    )
    supervisor_id = fields.Many2one(comodel_name='res.users', string="Supervised By", readonly=True)
    approver_supervisor_ids = fields.Many2many(
        comodel_name='res.users',
        string="Approvers and Supervisor",
        compute='_compute_approver_supervisor_ids',
        context={"active_test": False},
    )
    notes = fields.Text(string="Notes")

    cycle_id = fields.Many2one(related="template_id.cycle_id")

    _unique_code_per_return = models.Constraint(
        'UNIQUE(return_id, code)',
        'You can only have a unique check code for each return.'
    )

    @api.model_create_multi
    def create(self, vals_list):
        new_vals_list = [
            {key: self.env._(value) if isinstance(value, LazyGettext) else value  # pylint: disable=E8502
             for key, value in vals_dict.items()}
            for vals_dict in vals_list
        ]

        records = super().create(new_vals_list)

        # Left part is the check field name and right part is the template field name
        translatable_fields = [('name', 'name'), ('message', 'description')]
        all_langs = self.env['res.lang'].get_installed()
        for vals_dict, record in zip(vals_list, records):
            for lang_code, _lang_name in all_langs:
                # When trying to write a value on an translatable html field, It will try to translate it to other languages.
                # This is an issue since we want to manually set the value for every langauge.
                # By using delay_translate=True, we can avoid the automatic translation and set the value for each language
                # as long as `update_field_translations` is never called.
                record = record.with_context(lang=lang_code, delay_translations=True)
                for check_field, template_field in translatable_fields:
                    if record.template_id:
                        record[check_field] = record.template_id[template_field]
                    elif (value := vals_dict.get(check_field)) and isinstance(value, LazyGettext):
                        record[check_field] = value._translate(lang=lang_code)

        return records

    def write(self, vals):
        for check in self:
            user = self.env.user
            if 'supervisor_id' in vals and not user.has_groups('account.group_account_manager'):
                raise AccessError(self.env._("Only an accounting administrator can set/unset a supervisor."))

            if 'result' in vals:
                if check.return_state:
                    raise UserError(self.env._("You're only allowed to change the check state when the return hasn't been reviewed."))

                if user.id != SUPERUSER_ID:
                    result_selection = dict(self._fields['result']._description_selection(self.env))
                    check.refresh_result = False
                    check.return_id._track_add(
                        {check.return_id.id: {'result': result_selection[check.result]}},
                        end_values={check.return_id.id: {'result': result_selection[vals['result']]}},
                        fields_info={'result': {'type': 'char', 'string': self.env._("Check State")}},
                        body=Markup("<i>{check_name}</i> {check_updated}").format(
                            check_updated=self.env._("check updated"),
                            check_name=check.name,
                        ),
                    )

                if vals['result'] in ('anomaly', 'todo'):
                    check.approver_ids = False
                    # Writing on supervisor_id is only allowed for account admin, we don't want to raise
                    # an access error to a bookmaker if nothing is unset.
                    if check.supervisor_id:
                        check.supervisor_id = False
                elif vals['result'] == 'reviewed':
                    check.approver_ids |= user
                    # Same as above
                    if check.supervisor_id:
                        check.supervisor_id = False
                elif vals['result'] == 'supervised':
                    check.supervisor_id = user

        cleaned_vals = {
            key: self.env._(value) if isinstance(value, LazyGettext) else value  # pylint: disable=E8502
            for key, value in vals.items()
        }
        result = super().write(cleaned_vals)

        for check in self:
            if 'type' in vals and check.type != vals['type']:
                if not check.refresh_result:
                    check.action_invalidate_check()

            type = vals.get('type', check.type)
            if type != 'file' and check.attachment_ids:
                check.attachment_ids.unlink()

            if 'attachment_ids' in vals and type == 'file':
                check.refresh_result = not bool(check.attachment_ids)

        return result

    @api.depends('records_model')
    @api.depends_context('lang')
    def _compute_records_name(self):
        for check in self:
            check.records_name = check.records_model.name if check.records_model else self.env._("Missing")

    @api.depends('approver_ids', 'supervisor_id')
    def _compute_approver_supervisor_ids(self):
        for check in self:
            check.approver_supervisor_ids = check.approver_ids | check.supervisor_id

    @api.model
    def _parse_expression(self, value, context):
        """
        This parser extracts the expression such as context, domain, or params from string.

        The parser's main role is to interpret these values and apply transformations to specific keys using the evaluation context.
        This approach ensures safety by only evaluating values through the evaluation context, avoiding arbitrary code execution.
        Only predefined context actions (e.g., ref()) are allowed.
        """
        try:
            tree = ast.parse(value, mode="eval")
        except (SyntaxError, ValueError):
            raise ValidationError(_("Invalid code"))

        transformer = CheckActionExpressionTransformer(context)
        transformed_tree = transformer.visit(tree)
        return ast.literal_eval(transformed_tree)

    def action_review(self):
        """
        Preprocess and return the action that must be triggered when clicking a check.
        Actions to review can either come from data or from code, the ones from data will have their domains and contexts as strings.
        Therefore, we need to evaluate them with an additional context see: _get_evaluation_context.
        """
        self.ensure_one()

        if self.action:
            action = {
                **self.action
            }

            evaluation_context = self.return_id._get_evaluation_context()

            if 'context' in self.action and isinstance(self.action['context'], str):
                action['context'] = self._parse_expression(self.action['context'], evaluation_context)

            if 'domain' in self.action and isinstance(self.action['domain'], str):
                action['domain'] = self._parse_expression(self.action['domain'], evaluation_context)

            if 'params' in self.action and isinstance(self.action['params'], str):
                action['params'] = self._parse_expression(self.action['params'], evaluation_context)

            if self.template_id:
                if self.template_id.additional_action_domain:
                    action['domain'] = [
                        *(action.get('domain', []) or []),
                        *self._parse_expression(self.template_id.additional_action_domain, evaluation_context),
                    ]

                if self.template_id.additional_action_context:
                    action['context'] = {
                        **(action.get('context', {}) or {}),
                        **self._parse_expression(self.template_id.additional_action_context, evaluation_context),
                    }

                if self.template_id.additional_action_params and action.get('type') == 'ir.actions.client':
                    action['params'] = {
                        **(action.get('params', {}) or {}),
                        **self._parse_expression(self.template_id.additional_action_params, evaluation_context),
                    }

            action['active_id'] = self.return_id.id
            action['active_model'] = self.return_id._name

            return action

    @api.model
    def action_audit_custom_target(self, audit_id, target):
        """
        Hook defining which action is opened when an audit check is clicked.
        Can be extended by localizations to provide target-specific behavior.
        """
        pass

    @api.model
    def action_audit_report(self, audit_id, action_xml_id):
        action_ref = action_xml_id and self.env.ref(action_xml_id, raise_if_not_found=False)
        if not action_ref:
            return
        action_dict = action_ref._get_action_dict()
        if audit_id:
            audit = self.env['account.return'].browse(audit_id)
            additional_options = self.env.context.get('additional_options', {})
            action_dict['params'] = {
                'options': {
                    'date': {
                        'date_from': audit.date_from,
                        'date_to': audit.date_to,
                    },
                    **additional_options,
                },
                'ignore_session': True,
            }
        return action_dict

    def action_open_document(self):
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self.attachment_ids.id}",
            "target": "download",
        }

    def action_unlink_attachments(self):
        self.ensure_one()
        self.attachment_ids.unlink()
        self.refresh_result = True
        return True


class AccountReturnCheckTemplate(models.Model):
    _name = "account.return.check.template"
    _description = "Account Return Check Template"

    name = fields.Char(string="Title", required=True, translate=True)
    code = fields.Char(string="Code", default=lambda r: f"_template_check_{uuid.uuid4()}", copy=False)
    return_type = fields.Many2one(comodel_name='account.return.type', string="Tax Return/Audit", required=True)
    country_ids = fields.Many2many(comodel_name='res.country', string='Applicable Countries')
    cycle_id = fields.Many2one(
        comodel_name='account.return.audit.cycle',
        string="Cycle",
        required=True,
        default=lambda self: self.env.ref('account_reports.audit_cycle_other', raise_if_not_found=False),
    )
    type = fields.Selection(
        selection=CHECK_TYPES,
        default='check',
        required=True,
    )

    action_id = fields.Many2one(
        comodel_name='ir.actions.actions',
        string="Action on Click",
        help="Overrides the default action based on the model and domain.",
    )
    additional_action_domain = fields.Char(string="Additional Action Domain")
    additional_action_context = fields.Char(string="Additional Action Context")
    additional_action_params = fields.Char(string="Additional Action Params")
    activity_type = fields.Many2one(comodel_name='mail.activity.type', string="Activities")

    description = fields.Text(string="Description", translate=True)
    model = fields.Selection(
        selection=[
            ('account.move.line', "Journal Item"),
            ('account.move', "Journal Entry"),
            ('account.bank.statement.line', "Bank Statement Line"),
            ('account.payment', "Payments"),
            ('account.account', "Accounts"),
        ],
        string="Model",
    )
    domain = fields.Char(string="Domain")

    def _get_default_check_action_from_model(self):
        if self.model == 'account.bank.statement.line':
            return {
                'type': 'ir.actions.act_window',
                'name': _("Bank Matching"),
                'res_model': 'account.bank.statement.line',
                'view_mode': 'kanban,list',
                'search_view_id': self.env.ref('account_accountant.view_bank_statement_line_search_bank_rec_widget').id,
                'views': [[self.env.ref('account_accountant.view_bank_statement_line_kanban_bank_rec_widget').id, 'kanban'], [False, 'list']],
                'domain': [('state', '!=', 'cancel')],
            }

        return False

    def _transform_custom_check_template_domain(self, domain):
        """
        Transform complex Python domains that cannot be represented directly in XML for specific check templates.
        """
        return domain


class CheckActionExpressionTransformer(ast.NodeTransformer):
    def __init__(self, evaluation_context):
        self.evaluation_context = evaluation_context

    def visit_Name(self, node):
        if node.id in self.evaluation_context:
            return ast.Constant(self.evaluation_context[node.id])
        return node

    def get_call_args(self, ast_arguments):
        args = []
        for ast_arg in ast_arguments:
            args.append(ast.literal_eval(self.visit(ast_arg)))
        return args

    def visit_Call(self, node):
        if node.func.id in self.evaluation_context:
            return ast.Constant(self.evaluation_context[node.func.id](*self.get_call_args(node.args)))


class AccountReturnAuditCycle(models.Model):
    _name = 'account.return.audit.cycle'
    _description = 'Account Return Audit Cycle'
    _order = 'name, id'

    name = fields.Char(string="Name", required=True, translate=True)
    code = fields.Char(string="Code", required=True)

    _code_uniq = models.Constraint(
        'unique (code)',
        'Audit cycles codes must be unique.',
    )

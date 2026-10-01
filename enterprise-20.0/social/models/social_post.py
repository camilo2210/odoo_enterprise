# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from markupsafe import Markup

from odoo import _, api, fields, models, modules
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain


class SocialPost(models.Model):
    """ A social.post represents a post that will be published on multiple social.accounts at once.
    It doesn't do anything on its own except storing the global post configuration (message, images, ...).

    This model inherits from `social.post.template` which contains the common part of both
    (all fields related to the post content like the message, the images...). So we do not
    duplicate the code by inheriting from it. We can generate a `social.post` from a
    `social.post.template` with `action_generate_post`.

    When posted, it actually creates several instances of social.live.posts (one per social.account)
    that will publish their content through the third party API of the social.account. """

    _name = 'social.post'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'social.post.template']
    _description = 'Social Post'
    _order = 'create_date desc'

    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('posting', 'Posting'),
        ('posted', 'Posted')],
        string='Status', default='draft', readonly=True, required=True, copy=False,
        help="The post is considered as 'Posted' when all its sub-posts (one per social account) are either 'Failed' or 'Posted'")
    has_post_errors = fields.Boolean("There are post errors on sub-posts", compute='_compute_has_post_errors')
    account_ids = fields.Many2many(domain="[('id', 'in', account_allowed_ids)]")
    account_allowed_ids = fields.Many2many('social.account', string='Allowed Accounts', compute='_compute_account_allowed_ids',
                                           help='List of the accounts which can be selected for this post.')
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company,
                                 domain=lambda self: [('id', 'in', self.env.companies.ids)])
    media_ids = fields.Many2many('social.media', compute='_compute_media_ids', store=True,
        help="The social medias linked to the selected social accounts.")
    live_post_ids = fields.One2many('social.live.post', 'post_id', string="Posts By Account", readonly=True,
        help="Sub-posts that will be published on each selected social accounts.")
    live_posts_by_media = fields.Char('Live Posts by Social Media', compute='_compute_live_posts_by_media', readonly=True,
        help="Special technical field that holds a dict containing the live posts names by media ids (used for kanban view).")
    scheduled_date = fields.Datetime('Scheduled Date', copy=False)
    has_scheduled_date = fields.Boolean("Has Specific Date", compute='_compute_has_scheduled_date')
    published_date = fields.Datetime('Published Date', readonly=True, copy=False,
        help="When the global post was published. The actual sub-posts published dates may be different depending on the media.")
    # stored for better calendar view performance
    min_calendar_date = fields.Datetime('Min Calendar Date', compute='_compute_calendar_date', store=True, readonly=False)
    max_calendar_date = fields.Datetime('Max Calendar Date', compute='_compute_calendar_date', store=True, readonly=False)
    # technical field used by the calendar view (hatch the social post)
    is_hatched = fields.Boolean(string="Hatched", compute='_compute_is_hatched')
    #UTM
    utm_campaign_id = fields.Many2one('utm.campaign', domain="[('is_auto_campaign', '=', False)]",
        string="Campaign", ondelete="set null", index='btree_not_null')
    # Statistics
    stream_posts_count = fields.Integer("Feed Posts Count", compute='_compute_stream_posts_count')
    likes_count = fields.Integer("Likes", compute='_compute_post_stats')
    comments_count = fields.Integer("Comments", compute='_compute_post_stats')
    shares_count = fields.Integer("Shares", compute='_compute_post_stats')
    click_count = fields.Integer('Number of clicks', compute="_compute_click_count")

    @api.constrains('account_ids')
    def _check_account_ids(self):
        """All social accounts must be in the same company."""
        for post in self.sudo():  # SUDO to bypass multi-company ACLs
            if not (post.account_ids <= post.account_allowed_ids):
                raise ValidationError(_(
                    'Selected accounts (%(account_list)s) do not match the selected company (%(company)s)',
                    account_list=(post.account_ids - post.account_allowed_ids).mapped('name'),
                    company=post.company_id.name
                ))

    @api.depends(lambda self: ['scheduled_date', 'account_ids', *self._scheduled_date_fields().values()])
    def _compute_has_scheduled_date(self):
        for post in self:
            dates = post._get_scheduled_date_per_accounts().values()
            post.has_scheduled_date = any(dates)

    @api.depends('scheduled_date', 'is_split_per_media')
    def _compute_scheduled_date_by_media(self):
        """To be used in sub-modules to compute the media-specific scheduled_date."""
        scheduled_date_fields = self._scheduled_date_fields().values()
        for post in self:
            for field in scheduled_date_fields:
                if not post[field] or not post.is_split_per_media:
                    post[field] = post.scheduled_date

    @api.depends('live_post_ids.likes_count', 'live_post_ids.comments_count', 'live_post_ids.shares_count')
    def _compute_post_stats(self):
        results = self.env['social.live.post']._read_group(
            [('post_id', 'in', self.ids)],
            ['post_id'],
            ['likes_count:sum', 'comments_count:sum', 'shares_count:sum']
        )
        stats_per_post = {
            post: (likes_count, comments_count, shares_count)
            for post, likes_count, comments_count, shares_count in results
        }
        for post in self:
            post.likes_count, post.comments_count, post.shares_count = stats_per_post.get(post, (0, 0, 0))

    @api.depends('account_allowed_ids')
    def _compute_has_active_accounts(self):
        for post in self:
            post.has_active_accounts = bool(post.account_allowed_ids)

    @api.depends('live_post_ids')
    def _compute_stream_posts_count(self):
        for post in self:
            stream_post_domain = post._get_stream_post_domain()
            if stream_post_domain:
                post.stream_posts_count = self.env['social.stream.post'].search_count(
                    stream_post_domain)
            else:
                post.stream_posts_count = 0

    @api.depends('company_id')
    def _compute_account_ids(self):
        super(SocialPost, self)._compute_account_ids()

    @api.depends('company_id')
    def _compute_account_allowed_ids(self):
        """Compute the allowed social accounts for this social post.

        If the company is set on the post, we can attach to it account in the same company
        or without a company. If no company is set on this post, we can attach to it any
        social account.
        """
        all_account_allowed_ids = self.env['social.account'].search([])

        for post in self:
            post.account_allowed_ids = all_account_allowed_ids.filtered_domain(post._get_company_domain())

    @api.depends('live_post_ids.state')
    def _compute_has_post_errors(self):
        for post in self:
            post.has_post_errors = any(live_post.state == 'failed' for live_post in post.live_post_ids)

    @api.depends('account_ids.media_id')
    def _compute_media_ids(self):
        for post in self:
            post.media_ids = post.with_context(active_test=False).account_ids.mapped('media_id')

    @api.depends(lambda self: ['scheduled_date', 'account_ids', 'published_date', *self._scheduled_date_fields().values()])
    def _compute_calendar_date(self):
        for post in self:
            scheduled_dates = post._get_scheduled_date_per_accounts().values()
            if any(scheduled_dates):
                # for account without scheduled dates, use `published_date`
                scheduled_dates = [date or post.published_date for date in scheduled_dates]
                post.min_calendar_date = min(filter(bool, scheduled_dates))
                post.max_calendar_date = max(filter(bool, scheduled_dates))
            else:
                post.min_calendar_date = post.max_calendar_date = post.published_date or post.scheduled_date

    @api.depends('live_post_ids.account_id', 'live_post_ids.display_name')
    def _compute_live_posts_by_media(self):
        """ See field 'help' for more information. """
        for post in self:
            accounts_by_media = {media_id: [] for media_id in post.media_ids.ids}
            for live_post in post.live_post_ids.filtered(lambda lp: lp.account_id.media_id.ids):
                accounts_by_media[live_post.account_id.media_id.id].append(live_post.display_name)
            post.live_posts_by_media = json.dumps(accounts_by_media)

    @api.depends('state')
    def _compute_is_hatched(self):
        for post in self:
            post.is_hatched = post.state == 'draft'

    def _compute_click_count(self):
        if not self.ids:
            self.click_count = 0
            return

        click_data = dict(self.env["link.tracker.click"].sudo()._read_group(
            domain=[('link_id.utm_reference', 'in', [f'{post._name},{post.id}' for post in self])],
            groupby=["link_id.utm_reference"],
            aggregates=["__count"],
        ))
        for post in self:
            post.click_count = click_data.get(f'{post._name},{post.id}', 0)

    @api.model
    def _scheduled_date_fields(self):
        """Return the "scheduled_date" field per media."""
        return {}

    def _get_scheduled_date_per_accounts(self):
        """Return the scheduled dates for each selected accounts."""
        self.ensure_one()
        scheduled_date_fields = self._scheduled_date_fields()
        return {
            account: self[scheduled_date_fields[account.media_type]]
            for account in self.account_ids
            if account.media_type in scheduled_date_fields
        }

    def _prepare_preview_values(self, media):
        values = super(SocialPost, self)._prepare_preview_values(media)
        if self._name == 'social.post':
            live_posts = self.live_post_ids._filter_by_media_types([media])
            # Take first live post for preview. Should always have at least one.
            values['live_post_link'] = live_posts[0].live_post_link if len(live_posts) >= 1 else False
        return values

    @api.depends('display_message', 'state')
    def _compute_display_name(self):
        """ We use the first 20 chars of the message (or "Post" if no message yet).
        We also add "(Draft)" at the end if the post is still in draft state. """
        for post in self:
            post.display_name = self._prepare_post_name(
                post.display_message,
                state=post.state if post.state == 'draft' else False,
            )

    @api.model
    def default_get(self, fields):
        """ When created from the calendar view, we set the post as scheduled at the selected date. """

        result = super(SocialPost, self).default_get(fields)
        default_calendar_date = self.env.context.get('default_min_calendar_date')
        if default_calendar_date and 'scheduled_date' in fields:
            result['scheduled_date'] = default_calendar_date
        return result

    def social_stream_post_action_my(self):
        action = self.env["ir.actions.actions"]._for_xml_id("social.action_social_stream_post")
        action['name'] = _('Feed Posts')
        action['domain'] = self._get_stream_post_domain()
        action['context'] = {
            'search_default_search_my_streams': True,
            'search_default_group_by_stream': True
        }
        return action

    def _check_post_access(self):
        """
        Raise an error if the user cannot post on a social media
        """
        self.check_access("write")  # explicit check
        if any(not post.account_ids for post in self):
            raise UserError(_("Almost ready! Just select which accounts you'd like to post from."))
        message_field_per_media = self._message_fields()
        for post in self:
            for media in post.media_ids.filtered(lambda media: media.max_post_length):
                message_field = message_field_per_media.get(media.media_type)
                if message_field and len(post[message_field] or '') > media.max_post_length:
                    raise ValidationError(_("Oops! Your post is a bit too long. Try shortening it to fit the limit."))

    def action_duplicate(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'social.post',
            'res_id': self.copy().id,
            'context': self.env.context,
        }

    def action_add_to_queue(self):
        """Post or schedule the post.

        Post right way the media without a scheduled date, and schedule
        the posting if there's media with a schedule date.
        """
        self.ensure_one()
        self._check_post_access()
        scheduled_dates = self._get_scheduled_date_per_accounts().values()

        if any(date and date < fields.Datetime.now() for date in scheduled_dates):
            raise UserError(_('You cannot schedule a post in the past.'))

        if any(scheduled_dates):
            self.state = 'scheduled'
            # trigger the CRON for all dates
            cron = self.env.ref('social.ir_cron_post_scheduled')
            cron._trigger(at=set(filter(bool, scheduled_dates)))

        if not all(scheduled_dates):
            self._action_post()

    def action_set_draft(self):
        self._check_post_access()
        self.write({'state': 'draft'})

    def action_post_now(self):
        """Force to post the post right away, ignoring all scheduled dates."""
        self._check_post_access()

        for live_post in self.live_post_ids:
            if live_post.state == 'posting' and live_post.scheduled_date:
                # need to manually set the live post as ready
                # because the CRON will skip live post without a scheduled date
                # in posting state (they are managed by sub-modules, like
                # Instagram and Push Notifications, see `@_cron_publish_scheduled`).
                live_post.state = 'ready'

        self.write(
            {f: False for f in self._scheduled_date_fields().values()}
            | {'scheduled_date': False}
        )
        self._action_post()

    def action_reload(self):
        """Reload the form view.

        Useful when the post is in "posting" state,
        and we want to refresh the view.
        """
        pass

    def action_redirect_to_clicks(self):
        action = self.env["ir.actions.actions"]._for_xml_id("link_tracker.link_tracker_action")
        action['domain'] = [('utm_reference', 'in', [f'{post._name},{post.id}' for post in self])]
        return action

    def _action_post(self):
        """ Called when the post is published on its social.accounts.
        It will create one social.live.post per social.account and call '_post' on each of them. """

        for post in self:
            if post.live_post_ids:
                # live posts already created
                continue

            post.write({
                'state': 'posting',
                'published_date': fields.Datetime.now(),
                'live_post_ids': [
                    (0, 0, live_post)
                    for live_post in post._prepare_live_post_values()]
            })

        if not modules.module.current_test:
            # If there's a link in the message, the Facebook / Twitter API will fetch it
            # to build a preview. But when posting, the SQL transaction will not
            # yet be committed, and so the link tracker associated to this link
            # will not yet exist for the Facebook API and the preview will be
            # broken. So we force the compute of the message field and therefor the
            # creation of the link trackers (flush will compute only stored fields).
            self.mapped('live_post_ids.message')
            self.env.cr.commit()

        for post in self:
            # send the live posts
            failed_posts = self.env['social.live.post']
            for live_post in post.live_post_ids:
                if (
                    live_post.state == 'posting'
                    and live_post.scheduled_date
                    and live_post.scheduled_date <= fields.Datetime.now()
                ):
                    # the live post is now ready to be sent
                    live_post.state = 'ready'

                if live_post.state != 'ready':
                    continue

                try:
                    live_post._post()
                except Exception:  # noqa: BLE001
                    failed_posts |= live_post
            failed_posts.write({
                'state': 'failed',
                'failure_reason': _('Unknown error')
            })

    def _prepare_live_post_values(self):
        self.ensure_one()
        return [{
            'post_id': self.id,
            'account_id': account.id,
            'state': (
                'ready' if not scheduled_date or scheduled_date <= fields.Datetime.now()
                else 'posting'
            )
        } for account, scheduled_date in self._get_scheduled_date_per_accounts().items()]

    @api.model
    def _prepare_post_name(self, message, state=False):
        name = _('Post')
        if message:
            message = message.replace('\n', ' ')  # replace carriage returns as needed name is usually a Char
            if len(message) < 64:
                name = message
            else:
                name = message[:60] + '...'

        if state:
            state_description_values = {elem[0]: elem[1] for elem in self._fields['state']._description_selection(self.env)}
            state_translated = state_description_values.get(state)
            name += f' ({state_translated})'

        return name

    def _get_company_domain(self):
        self.ensure_one()
        if self.company_id:
            return ['|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)]
        return ['|', ('company_id', '=', False), ('company_id', 'in', self.env.companies.ids)]

    def _get_default_accounts_domain(self):
        return self._get_company_domain()


    def _get_stream_post_domain(self):
        return []

    def _check_post_completion(self):
        """ This method will check if all live.posts related to the post are completed ('posted' / 'failed' / 'cancel').
        If it's the case, we can mark the post itself as 'posted'. """

        posts_to_complete = self.filtered(
            lambda post: all(
                live_post.state in ('posted', 'failed', 'cancel')
                for live_post in post.live_post_ids
            )
        )

        for post in posts_to_complete:
            posts_failed = Markup('<br>').join([
                '  - ' + live_post.display_name
                for live_post in post.live_post_ids
                if live_post.state in ('failed', 'cancel')
            ])

            if posts_failed:
                post._message_log(body=_("Message posted partially. These are the ones that couldn't be posted:%s", Markup("<br/>") + posts_failed))
            else:
                post._message_log(body=_("Message posted"))

            if post.live_post_ids.account_id == post.account_ids:
                # all live posts have been sent / failed / canceled
                post.sudo().write({'state': 'posted'})

    @api.model
    def _cron_publish_scheduled(self):
        """ Method called by the cron job that searches for social.posts that were scheduled and need
        to be published and calls _action_post() on them."""

        domain = Domain.FALSE
        for media, scheduled_date_field in self._scheduled_date_fields().items():
            domain |= Domain([
                (scheduled_date_field, '<=', fields.Datetime.now()),
                ('media_ids.media_type', '=', media),
            ])
        self.search(domain & Domain('state', 'in', ('scheduled', 'posting')))._action_post()

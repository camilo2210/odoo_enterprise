# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Sale Subscriptions Loyalty',
    'summary': 'Loyalty points and rewards for subscription renewals',
    'category': 'Sales/Subscriptions',
    'depends': ['sale_loyalty', 'sale_subscription'],
    'auto_install': True,
    'description':
    """
        This module adds loyalty features to the subscription system, by:
        Offering subscriptions with X free sessions or products each month.
        Automatically adding loyalty points to the customer's loyalty card at each renewal.
        Applying discount on the first X months of the subscription.
        Automatically applying available rewards at each renewal (if loyalty points are available).
        Defining if loyalty rules grant points on each subscription renewal.
        Defining if rewards can be applied at each renewal (if there are still enough points).
    """,
    'data': [
        'views/loyalty_reward_views.xml',
        'views/loyalty_rule_views.xml',
        'views/sale_subscription_portal_templates.xml',
    ],
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}

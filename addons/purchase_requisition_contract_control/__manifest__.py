# -*- coding: utf-8 -*-
#
# Summa-SCI - Copyright (2026)

{
    'name': 'Purchase Agreement Contract Control',
    'author': 'Summa SCI',
    'version': '19.0.1.0.0',
    'category': 'Supply Chain/Purchase',
    'summary': 'Select blanket orders on purchase orders without importing all their lines, '
               'and enforce remaining quantities and expiration dates.',
    'description': """
Purchase Agreement Contract Control
===================================

Extends the native Purchase Agreements (blanket orders) workflow:

* Selecting a blanket order on a purchase order keeps the native header defaults
  (vendor, currency, origin, terms...) but no longer imports every agreement line.
  The user adds only the products needed; the agreement price is applied natively.
* The quantity ordered for an agreement product cannot exceed the agreement quantity
  minus the quantity already ordered through other confirmed purchase orders.
* A purchase order cannot be linked to, or confirmed under, an expired agreement.

Rules are enforced at ORM level (constraints) and announced in the form through
onchange warnings. Purchase templates keep their native behaviour.
""",
    'depends': ['purchase_requisition'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'Other proprietary',
}

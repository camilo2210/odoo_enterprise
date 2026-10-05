# -*- coding: utf-8 -*-
# from odoo import http


# class PersonalizedAddon(http.Controller):
#     @http.route('/personalized_addon/personalized_addon', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/personalized_addon/personalized_addon/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('personalized_addon.listing', {
#             'root': '/personalized_addon/personalized_addon',
#             'objects': http.request.env['personalized_addon.personalized_addon'].search([]),
#         })

#     @http.route('/personalized_addon/personalized_addon/objects/<model("personalized_addon.personalized_addon"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('personalized_addon.object', {
#             'object': obj
#         })


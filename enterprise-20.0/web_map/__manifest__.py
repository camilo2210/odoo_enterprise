{
    'name':"Map View",
    'summary':"Defines the map view for odoo enterprise",
    'description':"Allows the viewing of records on a map",
    'category': 'Hidden',
    'depends': ['web_enterprise'],
    'data':[
        "views/res_partner_views.xml",
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
    'assets': {
        'web.assets_backend_lazy': [
            'web_map/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            'web_map/static/lib/**/*',
            'web_map/static/tests/**/*',
        ],
    }
}

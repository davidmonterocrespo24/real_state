# -*- coding: utf-8 -*-
from odoo import http
class RealEstateWebsiteCrm(http.Controller):

    @http.route('/properties', auth='public')
    def properties(self, **kw):

        return http.request.render('real_estate_website_crm.index', {
            'root': '/properties',
            'props': http.request.env['real.estate.property'].search([]),
        })

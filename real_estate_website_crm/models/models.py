# -*- coding: utf-8 -*-

from werkzeug import urls

from odoo import api, fields, models
from odoo.tools.translate import html_translate


class RealEstateProperty(models.Model):
    _name = 'real.estate.property'
    _inherit = ['real.estate.property', 'website.seo.metadata', 'website.published.mixin']

    # website_published = fields.Boolean()

    website_description = fields.Html('Website description', translate=html_translate,
                                      sanitize_attributes=False)

    @api.multi
    def _compute_website_url(self):
        super(RealEstateProperty, self)._compute_website_url()
        for property in self:
            property.website_url = "/property/detail/%s" % property.id

    @api.multi
    def set_open(self):
        self.write({'website_published': False})
        return super(RealEstateProperty, self).set_open()

# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    real_estate_journal = fields.Many2one('account.journal', string='Default Payment Journal')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    real_estate_journal = fields.Many2one('account.journal',
                                          related='company_id.real_estate_journal',
                                          string='Default Payment Journal',
                                          readonly=0)

    module_real_estate_mod_cons = fields.Boolean(string="Property Mod Cons")



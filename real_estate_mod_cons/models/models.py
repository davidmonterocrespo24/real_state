# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class RealEstateModCons(models.Model):
    _name = 'real.estate.mod.cons'
    _description = 'Real Estate Mod Cons'

    name = fields.Char()


class RealEstateProperty(models.Model):
    _inherit = 'real.estate.property'

    mod_cons_ids = fields.Many2many('real.estate.mod.cons', string='Mod Cons')

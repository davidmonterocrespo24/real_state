# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class WizardSetQuota(models.TransientModel):
    _name = 'wizard.set_quota'

    quota = fields.Float(string='Set Quota to')

    @api.multi
    def set_quota(self):
        if self.quota > 0:
            active_id = self.env.context.get('active_id')
            contract = self.env['real.estate.contract'].browse(active_id)

            for quota_id in contract.quota_ids:
                quota_id.amount = self.quota

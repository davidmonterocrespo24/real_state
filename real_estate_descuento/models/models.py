# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class RealEstateDescuento(models.Model):
    _name = 'real.estate.descuento'

    sequence = fields.Char(string='Secuencia.')
    contract_id = fields.Many2one('real.estate.contract', string='Contracto')
    partner_id = fields.Many2one('res.partner', string='Comprador')
    quota_id = fields.Many2one('real.estate.contract.quota', string='Cuota')
    name = fields.Char('Descripcion')
    amount = fields.Float('Monto')
    date = fields.Date('Fecha')
    company_id = fields.Many2one('res.company', string='Compania')

    @api.model
    def create(self, vals):
        #vals['sequence'] = self.env['ir.sequence'].next_by_code('real.estate.descuento')

        return super(RealEstateDescuento, self).create(vals)
    
    @api.multi
    def populate_model(self):
        company = self.env.user.company_id.id
        quota_with_discount = self.env['real.estate.contract.quota'].search([
            ('contract_id.company_id', '=', company),
            ('discount', '!=', 0),
        ], order='contract_id')

        for quota in quota_with_discount:
            contract_id = quota.contract_id
            self.create({
                'contract_id': contract_id.id,
                'partner_id': contract_id.partner_id.id,
                'quota_id': quota.id,
                'name': contract_id.discount_description or '',
                'amount': quota.discount,
                'company': company,
            })


class WizardDescuento(models.TransientModel):
    _inherit = 'wizard.contract.discount'

    @api.multi
    def aplicar_descuento(self):
        contrac_id = self.env.context.get('active_id')
        date = fields.Date.today()

        Quotas = self.env['real.estate.contract.quota'].search([
            ('contract_id', '=', contrac_id)
        ], order='id desc')
        Discount = self.env['real.estate.descuento']

        partner_id = Quotas[0].contract_id.partner_id.id

        descuento = self.amount
        sequence = self.env['ir.sequence'].next_by_code('real.estate.descuento')

        quotas = []
        for quota_id in Quotas:
            if quota_id.amount_paid == quota_id.amount or quota_id.residual == 0:
                continue

            if descuento > quota_id.residual:
                temp = descuento - quota_id.residual
                #descuento aplicar
                da = descuento - temp
                descuento = temp
                #monto = (quota_id.amount - quota_id.amount_paid)
                #amount -= monto

            else:
                da = descuento
                descuento = 0
                #monto = amount
                #amount -= monto

            #quotas.append((1, quota_id.id, {'discount': monto}))
            #_logger.info(quotas)
            Discount.create({
                'sequence': sequence,
                'contract_id': contrac_id,
                'partner_id': partner_id,
                'quota_id': quota_id.id,
                'name': self.name,
                'amount': da, #monto,
                'date': date,
                'company_id': quota_id.contract_id.company_id.id,
            })
            
            quota_id.discount += da
            if descuento <= 0:
                break

        self.env['real.estate.contract'].browse(contrac_id).write({
            'discount_description': self.name
        })

# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api


class RealEstateChangeAccount(models.Model):
    _inherit = 'real.estate.contract'

    penalizacion = fields.Float(string="Penalizacion")
    
    def total_paid(self):
        total = sum([i.amount_paid for i in self.quota_ids])
        return total
    
    def get_payments_for_contract(self):
        payments = self.env['payment.quota.line'].search([
            ('pago_id.contract_id', '=', self.id),
            ('pago_id.state', '=', 'done')
        ])
        
        data = []
        total = 0
        for p in payments:
            data.append({
                'fecha': p.pago_id.date,
                'concepto': p.note,
                'metodo': p.pago_id.forma_pago,
                'total': '{}{:,.2f}'.format(p.pago_id.currency_id.symbol, p.to_pay)
            })
            
            total += p.to_pay
        data.append({
            'fecha': 'Total',
            'concepto': '',
            'metodo': '',
            'total': '{}{:,.2f}'.format(p.pago_id.currency_id.symbol, total) # total
        })
            
        return data
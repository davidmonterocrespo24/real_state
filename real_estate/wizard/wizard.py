# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from num2words import num2words

_logger = logging.getLogger(__name__)


class WizardContractDiscount(models.TransientModel):
    _name = 'wizard.contract.discount'
    _description = 'Wizard Contract Discount'

    name = fields.Char(string='Nota')
    amount = fields.Float(string='Monto')

    @api.multi
    def aplicar_descuento(self):
        contract_id = self.env.context.get('active_id')

        Quotas = self.env['real.estate.contract.quota'].search([
            ('contract_id', '=', contract_id)
        ], order='id desc')

        amount = self.amount

        quotas = []
        for quota_id in Quotas:
            if quota_id.amount_paid == quota_id.amount \
             or quota_id.residual == 0:
                continue

            if amount >= quota_id.residual:
                monto = (quota_id.amount - quota_id.amount_paid)
                amount -= monto
            else:
                monto = amount
                amount -= monto

            quotas.append((1, quota_id.id, {'discount': monto}))

            if amount <= 0:
                break

        self.env['real.estate.contract'].browse(contract_id).write(
            {'quota_ids': quotas, 'discount_description': self.name}
        )
        _logger.info((quotas, contract_id, Quotas))
        # return self.env.ref('real_estate.report_descuento').report_action(self)


class WizardContractCancel(models.TransientModel):
    _name = 'wizard.contract.cancel'

    name = fields.Selection([
            ('Voluntad_Propia', 'Voluntad Propia'),
            ('No_Aplica', 'No Aplica a Prestamo'),
            ('Cambio_Titular', 'Cambio Titular'),
            ('Cambio_Unidad', 'Cambio de Unidad'),
            ('Cambio_Unidad_Etapa', 'Cambio de Unidad y Etapa'),
            ('Otro', 'Otro'),
        ], string="Motivo de Desestimiento")

    amount = fields.Float(string='Monto a Reembolsar')
    
    journal_id = fields.Many2one('account.journal', string='Diario de Pago')
    otro_motivo = fields.Char()
    note = fields.Char(string="Nota para el Pago")

    @api.multi
    def create_nc(self):
        active_id = self.env.context.get('active_id')
        contract = self.env['real.estate.contract'].browse(active_id)
        
        contract.property_id.state = 'available'
        contract.write({'state': 'cancel',
                        'motivo_desestimiento': self.name})
        message = """
            <p><strong>Contrato Desistido por:</strong>{}</p>
            <p><strong>Motivo: </strong>{}</p
        """.format(self.name, self.otro_motivo or '')
        
        if self.amount > 0:   
            currency = contract.property_id.currency_id
            payment_method_id = self.journal_id.inbound_payment_method_ids[0]
            payment_info = {
                'partner_id': contract.partner_id.id,
                'payment_type': 'outbound',
                'partner_type': 'customer',
                'amount': self.amount,
                'currency_id': currency.id,
                'journal_id': self.journal_id.id,
                'payment_date': fields.Date.today(),
                'communication': self.note,
                'payment_method_id': payment_method_id.id,
            }

            payment_id = self.env['account.payment'].create(payment_info)
            message += """
                <p><strong>Se genero un Reembolso por un total de:</strong>{}{:,.2f}</p>
            """.format(currency.name, self.amount)
            
        contract.message_post(body=message)

# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from num2words import num2words

_logger = logging.getLogger(__name__)


class PaymentQuota(models.Model):
    _name = 'payment.quota'
    _description = 'Real Estate Pagos Cuotas'

    def _partner_domain(self):
        domain = []
        Partners = self.env['real.estate.contract'].search([
            ('state', 'not in', ['draft', 'cancel'])
        ]).mapped('partner_id')

        if Partners:
            domain = [('id', 'in', Partners.ids)]

        return domain

    name = fields.Char(string='Pago', readonly=1)
    partner_id = fields.Many2one('res.partner', string='Cliente',
                                 domain=_partner_domain, required=1)

    partner2_id = fields.Many2one('res.partner', string='Co-Comprador',
                                  related='contract_id.partner2_id')
    apoderado = fields.Many2one('res.partner', string='Apoderado',
                                related='contract_id.apoderado')

    contract_id = fields.Many2one('real.estate.contract', required=1)
    property_id = fields.Many2one(related='contract_id.property_id')
    payment_id = fields.Many2one('account.payment', string='Pago asociado')
    company_id = fields.Many2one(
        'res.company', string='Compania',
        default=lambda self: self.env.user.company_id.id
    )
    currency_id = fields.Many2one(related='contract_id.property_currency_id')
    date = fields.Date(default=fields.Date.today())
    amount = fields.Float(string='Monto a pagar', compute='get_amount')
    monto_letra = fields.Char(readonly='1')
    journal_id = fields.Many2one('account.journal', string='Diario/Caja')

    date_transaction = fields.Date('Fecha del Deposito/Transf.')

    forma_pago = fields.Selection([
        ('Efectivo', 'Efectivo'),
        ('Certificado', 'Certificado'),
        ('Deposito', 'Deposito'),
        ('Cheque', 'Cheque'),
        ('Transferencia', 'Transferencia'),
    ], string='Forma de Pago')

    memo = fields.Char('Concepto de Pago')

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('cancel', 'Cancelado'),
        ('done', 'Hecho'),
    ], string='Estado', default='draft')

    quota_ids = fields.One2many('payment.quota.line', 'pago_id')
    mora_ids = fields.One2many('payment.quota.line.mora', 'pago_id')

    tasa = fields.Float(string='Tasa', default=1)
    monto_divisa = fields.Float(string='Monto')

    mora_total = fields.Float(string='Moras Total', compute='get_totals')
    quota_total = fields.Float(string='Cuotas Total', compute='get_totals')
    total = fields.Float(string='Total', compute='get_totals')
    residual = fields.Float(string='Monto Residual', compute='get_totals')

    currency_payment_id = fields.Many2one(
        'res.currency',
        string='Divisa del Pago',
        default=lambda self: self.env.user.company_id.currency_id.id
    )

    @api.depends('quota_ids', 'mora_ids')
    def get_totals(self):
        for r in self:
            mora_total = sum([i.amount for i in r.mora_ids])
            quota_total = sum([i.to_pay for i in r.quota_ids])

            r.mora_total = mora_total
            r.quota_total = quota_total
            r.total = (mora_total + quota_total)
            r.residual = (mora_total + quota_total) - r.amount

    @api.depends('monto_divisa', 'tasa', 'currency_id', 'currency_payment_id')
    def get_amount(self):
        for r in self:
            moneda_cuota = r.currency_id.name
            moneda_pago = r.currency_payment_id.name

            if moneda_cuota == moneda_pago:
                r.amount = r.monto_divisa

            else:
                if moneda_pago == "DOP":

                    r.amount = r.monto_divisa / r.tasa

                else:
                    r.amount = r.monto_divisa * r.tasa

    def amount_word(self, monto):
        amt = str('{0:.2f}'.format(monto))
        amt_lst = amt.split('.')
        amt_word = num2words(int(amt_lst[0]), lang='es')
        lst = amt_word.split(' ')
        lst.append(' con ' + amt_lst[1] + '/' + str(100))
        value = ' '.join(lst)
        value = value.upper()
        return value

    @api.onchange('monto_divisa')
    def onchange_monto_divisa(self):
        CurrencyUSD = self.env['res.currency'].search([('name', '=', 'USD')])

        currency_rate = 1
        if self.currency_id and self.currency_payment_id \
                and self.currency_id.id != self.currency_payment_id.id:
            # si la cuota es en USD y el pago en DOP
            # buscar la tasa del DOLAR
            # ---
            # si la cuota es en DOP y el pago en USD
            # buscar la tasa del DOLAR

            rate = self.env['res.currency.rate'].search(
                [
                    ('name', '<=', self.date),
                    ('currency_id', '=', CurrencyUSD.id)
                ], limit=1
            ).rate
            currency_rate = 1 / rate or 1
        return {'value': {'tasa': currency_rate}}

    def _get_quota_info(self):
        contract = self.contract_id

        amount = self.amount
        _logger.info('MONTO1: %s' %amount)


        if self.env.context.get('monto', 0):
            amount = self.env.context.get('monto', 0)


        _logger.info('MONTO2: %s' %amount)
        extra_ids = []
        quotas_list = []
        moras_list = []

        # no_saldado el valor es True si tiene un residual > 0
        no_saldado = any(contract.quota_ids.mapped('residual'))
        #import pdb
        for quota_id in contract.quota_ids:
            if quota_id.amount_paid == quota_id.amount or quota_id.residual <= 0:
                continue

            moras = self.env['real.estate.line.mora'].search([
                ('contract_id', '=', contract.id),
                ('quota_id', '=', quota_id.id),
                ('date', '<=', self.date),
                ('to_pay', '=', True)])

            for mora in moras:
                amount -= mora.amount

                moras_list.append(
                    [0, 0, {
                        'quota_id': mora.quota_id.id,
                        'name': 'Mora de: %s' % mora.quota_id.name,
                        'pago_id': self,
                        'amount': mora.amount,
                        'date': mora.date,
                    }]
                )

            Extras = self.env['real.estate.concepto.extra'].search([
                ('contract_id', '=', contract.id),
                # ('date_due', '<=', self.date),
                ('paid', '=', False),
                ('id', 'not in', extra_ids)
            ])

            for extra in Extras:
                amount -= extra.amount
                extra_ids.append(extra.id)
                moras_list.append(
                    [0, 0, {
                        'name': extra.name,
                        'pago_id': self,
                        'amount': extra.amount,
                        'date': extra.date_due,
                    }]
                )
            #pdb.set_trace()
            _logger.info((amount, quota_id.residual, amount > quota_id.residual,'VALORES'))
            if amount >= (quota_id.amount - quota_id.amount_paid): # quota_id.residual:
                monto = quota_id.amount - quota_id.amount_paid
                amount -= monto
                note = 'Pago de %s' % quota_id.name

            else:
                monto = amount
                amount -= monto
                note = 'Avance de %s' % quota_id.name

            quotas_list.append(
                [0, 0, {
                    'quota_id': quota_id.id,
                    'amount': quota_id.amount,
                    'to_pay': monto,
                    'pago_id': self,
                    'amount_paid': quota_id.amount_paid,
                    'residual': quota_id.amount - quota_id.amount_paid,
                    'note': note,
                }]
            )

            if amount <= 0:
                break

        if amount > 0:
            self.residual = amount
        #"""
        if not no_saldado:
            Extras = self.env['real.estate.concepto.extra'].search([
                 ('contract_id', '=', contract.id),
                 ('date_due', '<=', self.date),
                 ('paid', '=', False),
                 ('id', 'not in', extra_ids)
            ])

            for extra in Extras:
                amount -= extra.amount
                extra_ids.append(extra.id)
                moras_list.append(
                     [0, 0, {
                         'name': extra.name,
                         'pago_id': self,
                         'amount': extra.amount,
                         'date': extra.date_due,
                     }]
                )

                if amount <= 0:
                    break

        _logger.info(moras_list)
        #"""
        return (quotas_list, moras_list)

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        return {'value': {'contract_id': False, 'property_id': False}}

    @api.onchange('currency_payment_id')
    def _onchange_currency_payment_id(self):
        CurrencyUSD = self.env['res.currency'].search([('name', '=', 'USD')])

        currency_rate = 1
        if self.currency_id and self.currency_payment_id \
                and self.currency_id.id != self.currency_payment_id.id:
            # si la cuota es en USD y el pago en DOP
            # buscar la tasa del DOLAR
            # ---
            # si la cuota es en DOP y el pago en USD
            # buscar la tasa del DOLAR

            rate = self.env['res.currency.rate'].search(
                [
                    ('name', '<=', self.date),
                    ('currency_id', '=', CurrencyUSD.id)
                ], limit=1
            ).rate

            currency_rate = 1 / rate if rate else 1

        return {'value': {'tasa': currency_rate}}

    @api.onchange('tasa')
    def _onchange_tasa(self):
        moneda_cuota = self.currency_id.name
        moneda_pago = self.currency_payment_id.name

        if moneda_cuota == moneda_pago:
            self.amount = self.monto_divisa

        else:
            if moneda_pago == "DOP":
                self.amount = self.monto_divisa / self.tasa

            else:
                self.amount = self.monto_divisa * self.tasa

    @api.onchange('amount')
    def _onchange_amount(self):
        monto_letra = self.amount_word(self.amount)
        self.quota_ids = [(5, 0, 0)]
        self.mora_ids = [(5, 0, 0)]

        data = self._get_quota_info()

        res = {'value': {
            'quota_ids': data[0],
            'monto_letra': monto_letra,
            'mora_ids': data[1],
        }}

        return res

    @api.multi
    def recalc_cuotas(self):
        monto_letra = self.amount_word(self.amount)
        self.quota_ids = [(5, 0, 0)]
        self.mora_ids = [(5, 0, 0)]

        data = self._get_quota_info()

        _logger.info(('VALORES:', data))
        res = {'value': {
            'quota_ids': data[0],
            'monto_letra': monto_letra,
            'mora_ids': data[1],
        }}

        self.quota_ids = data[0]
        self.mora_ids = data[1]
        self.monto_letra = monto_letra
        return res

    @api.multi
    def action_done(self):
        if not self.payment_id:
            payment = self.generate_payment()
            self.write({'state': 'done', 'payment_id': payment.id})
        else:
            self.payment_id.write({
                'amount': self.monto_divisa,
            'currency_id':  self.currency_payment_id.id,
            })

            self.payment_id.post()
            self.state = 'done'

        moras = self.mora_ids.filtered(lambda i: i.name.startswith('Mora'))
        for mora in moras:
            Moras = self.env['real.estate.line.mora'].search([
                ('quota_id', '=', mora.quota_id.id),
                ('amount', '=', mora.amount),
            ])
            Moras.unlink()

        cargos = self.mora_ids.filtered(lambda i: not i.name.startswith('Mora'))
        Extras = self.env['real.estate.concepto.extra'].search([
            ('contract_id', '=', self.contract_id.id),
            ('date_due', '<=', self.date),
            ('paid', '=', False),
            ('name', 'in', [i.name for i in cargos])
        ])

        for i in Extras:
            i.paid = True

    @api.multi
    def action_cancel(self):
        self.payment_id.cancel()
        self.state = 'cancel'

    @api.multi
    def action_to_draft(self):
        self.payment_id.action_draft()

        self.state = 'draft'
        self.quota_ids = [(5, 0, 0)]
        self.mora_ids = [(5, 0, 0)]

    @api.multi
    def generate_payment(self):
        contract = self.contract_id

        payment_method_id = self.journal_id.inbound_payment_method_ids[0]
        payment_info = {
            'partner_id': self.partner_id.id,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'amount':  self.monto_divisa,
            'journal_id': self.journal_id.id,
            'payment_date': self.date,
            'currency_id':  self.currency_payment_id.id,
            'forma_pago': self.forma_pago,
            'communication': self.memo,
            'real_estate_contract_id': self.contract_id.id,
            'payment_method_id': payment_method_id.id,
        }

        payment_id = self.env['account.payment'].create(payment_info)
        payment_id.post()

        return payment_id

    @api.model
    def create(self, vals):
        if vals.get('date_transaction'):
            pago = self.search([
                ('date_transaction', '=', vals.get('date_transaction')),
                ('contract_id', '=', vals.get('contract_id'))
            ])

            if pago:
                raise UserError(
                    'Ya el pago por %s fue registrado' % vals.get('forma_pago')
                )

        vals['amount'] = vals['monto_divisa'] / vals['tasa']
        vals['name'] = self.env['ir.sequence'].next_by_code('payment.quota')
        obj = super(PaymentQuota, self).create(vals)
        data = obj._get_quota_info()

        obj.quota_ids = data[0]
        obj.mora_ids = data[1]
        obj.contract_id.get_mora_pagadas()

        return obj

    @api.multi
    def write(self, vals):
        if 'monto_divisa' in vals:
            self.quota_ids = [(5 ,0 ,0)]
            self.mora_ids = [(5 ,0 ,0)]

            amount = vals['monto_divisa'] / self.tasa
            
            data = self.with_context({'monto': amount})._get_quota_info()
            _logger.warning(' %s' % (amount))
            vals.update({
                'quota_ids': data[0],
                'mora_ids': data[1],
            })

        return super(PaymentQuota, self).write(vals)


class PaymentQuotaLine(models.Model):
    _name = 'payment.quota.line'
    _description = 'Real Estate Pagos Cuotas Lineas'

    pago_id = fields.Many2one('payment.quota')
    quota_id = fields.Many2one(
        'real.estate.contract.quota', string='Cuota/Descripcion'
    )
    date_due = fields.Date(related='quota_id.date_due')
    currency_id = fields.Many2one(related='quota_id.currency_id')
    amount = fields.Monetary(
        currency_field='currency_id', string='Monto Cuota'
    )
    amount_paid = fields.Monetary(
        currency_field='currency_id', string='Monto Pagado'
    )
    residual = fields.Monetary(currency_field='currency_id', string='Residual')
    to_pay = fields.Monetary(currency_field='currency_id', string='A pagar')
    note = fields.Char()


class PaymentQuotaLineMoras(models.Model):
    _name = 'payment.quota.line.mora'
    _description = 'Real Estate Pagos Cuotas Lineas Moras'

    name = fields.Char('Descripcion')
    pago_id = fields.Many2one('payment.quota')
    quota_id = fields.Many2one('real.estate.contract.quota',
                               string='Cuota Vencida')
    contract_id = fields.Many2one('real.estate.contract', string='Contrato')
    currency_id = fields.Many2one(related='quota_id.currency_id')
    date = fields.Date('Vencion el')
    amount = fields.Monetary(currency_field='currency_id',
                             string='Monto a Pagar')
    to_pay = fields.Boolean(string='Se pagara?', default=True)

# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

READONLY_STATE_PROPERTY = {'available': [('readonly', False)]}
READONLY_STATE = {'draft': [('readonly', False)]}


class RealEstateProperty(models.Model):
    _name = 'real.estate.property'
    _description = 'Real State Property'

    name = fields.Char(string='Name', required=1, copy=False, readonly=1,
                       states=READONLY_STATE_PROPERTY)
    code = fields.Char(string='Code', readonly=1, states=READONLY_STATE_PROPERTY)
    amount = fields.Monetary(string='Property Value', required=1, readonly=1,
                          states=READONLY_STATE_PROPERTY, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', required=1, readonly=1,
                                  default=lambda self: self.env.user.company_id.currency_id.id,
                                  states=READONLY_STATE_PROPERTY)

    property_type = fields.Many2one('real.estate.property.type',
                                    string='Property Type', required=1,
                                    readonly=1, states=READONLY_STATE_PROPERTY, ondelete='restrict')
    street = fields.Char('street', readonly=1, states=READONLY_STATE_PROPERTY)
    street2 = fields.Char('street 2', readonly=1, states=READONLY_STATE_PROPERTY)
    city = fields.Char('CIty', readonly=1, states=READONLY_STATE_PROPERTY)
    state_id = fields.Many2one('res.country.state', domain="[('country_id', '=?', country_id)]",
                               readonly=1, states=READONLY_STATE_PROPERTY, ondelete='restrict')
    country_id = fields.Many2one('res.country', readonly=1, states=READONLY_STATE_PROPERTY,
                                 ondelete='restrict',
                                 default = lambda self: self.env.user.company_id.country_id.id)

    state = fields.Selection([
        ('available', 'Available'),
        ('reserved', 'Reserved'),
        ('sold', 'Sold'),
    ], default='available', string='State',
        help=" * The 'Available' status is used when a user is encoding a new property.\n"
             " * The 'Reserved' status is used when user creates a contract and validate it.\n"
             " * The 'Sold' status is set automatically when the Contract is paid.\n"
    )

    rooms = fields.Integer('Number of Rooms', readonly=1, states=READONLY_STATE_PROPERTY)
    bathrooms = fields.Float('Number of Bathrooms', readonly=1, states=READONLY_STATE_PROPERTY)
    parking = fields.Integer('Number of Parking', readonly=1, states=READONLY_STATE_PROPERTY)
    floor = fields.Integer('Floor/Level', readonly=1, states=READONLY_STATE_PROPERTY)
    mt2 = fields.Float('Building Mt2', readonly=1, states=READONLY_STATE_PROPERTY)

    description = fields.Text('Description', readonly=1, states=READONLY_STATE_PROPERTY)

    @api.model
    def create(self, vals):
        seq = self.env['ir.sequence'].next_by_code('real.estate.property')
        vals['code'] = seq

        return super(RealEstateProperty, self).create(vals)

    @api.multi
    def unlink(self):
        if self.state != 'available':
            raise UserError('You can not delete a property that is Reserved or sold.')
        return super(RealEstateProperty, self).unlink()


class RealEstateContract(models.Model):
    _name = 'real.estate.contract'
    _description = 'Real State Partner Contract'

    @api.depends('quota_ids.residual')
    def compute_remaining(self):
        for i in self:
            i.remaining = sum([quota.residual for quota in i.quota_ids])

    @api.depends('quota_ids')
    def _count_invoice_done(self):
        for i in self:
            i.invoice_done = len([inv for inv in i.quota_ids if inv.state == 'paid'])

    name = fields.Char(string='Name/Reference', readonly=1, copy=False)

    partner_id = fields.Many2one('res.partner', string='Partner', readonly=1,
                                 states=READONLY_STATE, ondelete='restrict')
    property_id = fields.Many2one('real.estate.property', string='Property',
                                  readonly=1, states=READONLY_STATE,
                                  ondelete='restrict')
    property_amount = fields.Monetary(related='property_id.amount',
                                      currency_field='property_currency_id')
    payment_month = fields.Monetary(currency_field='property_currency_id')
    invoice_done = fields.Integer(compute='_count_invoice_done', string='Quota Paid')
    property_currency_id = fields.Many2one(related='property_id.currency_id')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('validate', 'Validate'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
    ], default='draft')

    invoiced = fields.Boolean(string='Invoiced')

    advance = fields.Float(string='Advance', readonly=1, states=READONLY_STATE)
    journal_id = fields.Many2one('account.journal', string='Journal',
                                 default=lambda self: self.env.user.company_id.real_estate_journal.id,
                                 readonly=1, states=READONLY_STATE)
    payment_id = fields.Many2one('account.payment', string='Payment',
                                 readonly=1, states=READONLY_STATE)
    remaining = fields.Monetary(string='Remaining Amount', compute='compute_remaining',
                             currency_field='property_currency_id')
    date_start = fields.Date(string='Date Start', readonly=1, states=READONLY_STATE)
    num_payments = fields.Integer(string='Number of Payments', readonly=1,
                                  states=READONLY_STATE)

    quota_ids = fields.One2many('real.estate.contract.quota', 'contract_id')

    @api.multi
    def onchange_property(self):
        self.advance = self.property_amount * 0.10

    @api.multi
    def get_quota(self):
        if self.num_payments >= 1 and self.date_start:
            self.quota_ids.unlink()

            try:
                payment_month = (self.property_amount -self.advance) / self.num_payments
            except ZeroDivisionError:
                payment_month = self.num_payments

            date = self.date_start
            quota_name = _('Quota')

            quota_list = []

            active_id = self.id

            for i in range(1, self.num_payments+1):
                quota_list.append(
                    (0, 0, {
                        'contract_id': active_id,
                        'name': "%s %s" % (quota_name, i),
                        'date': date,
                        'amount': payment_month,
                    })
                )
                date = fields.Date.add(date, months=1)

            self.payment_month = payment_month
            self.quota_ids = quota_list

    @api.model
    def create(self, vals):
        seq = self.env['ir.sequence'].next_by_code('real.estate.contract')
        vals['name'] = seq

        return super(RealEstateContract, self).create(vals)

    @api.multi
    def action_open_invoices(self):
        actions = {
            "type": "ir.actions.act_window",
            "res_model": "account.invoice",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [["origin", "=", self.name]],
        }

        return actions

    @api.multi
    def create_invoice(self):
        for i in self.quota_ids:
            i.create_invoice()

        self.invoiced = True

    @api.multi
    def action_validate(self):
        if not self.quota_ids:
            raise UserError('You need to indicate at least one quota')

        if self.property_id.state != 'available':
            raise UserError('This Property is not Available')

        quota_total = sum([quota.amount for quota in self.quota_ids])

        if (quota_total + self.advance) != self.property_amount:
            raise UserError('Check the quota and advance amount.')

        payment_method_id = self.journal_id.inbound_payment_method_ids[0]

        payment_data = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner_id.id,
            'amount': self.advance,
            'currency_id': self.property_currency_id.id,
            'journal_id': self.journal_id.id,
            'payment_date': self.date_start,
            'communication': 'Advance Contract %s' % self.name,
            'payment_method_id': payment_method_id.id,
        }

        payment = self.env['account.payment'].create(payment_data)
        self.payment_id = payment

        self.property_id.state = 'reserved'
        return self.write({'state': 'validate'})

    @api.multi
    def action_cancel(self):
        # TODO: crear un Wizard para indicar el motivo
        #  de la cancelacion y un monto administrativo
        invoices = self.env['account.invoice'].search([
            ('origin', '=', self.name), ('state','=','draft')])

        for inv in invoices:
            inv.action_cancel()

        self.property_id.state = 'available'
        return self.write({'state': 'cancel'})


class ReaLEstateContractQuota(models.Model):
    _name = 'real.estate.contract.quota'
    _description = 'Real State Contract Quota'

    @api.depends('invoice_id', 'invoice_id.payment_move_line_ids')
    def get_amount_paid(self):
        for i in self:
            inv = i.invoice_id
            total_paid = 0
            for payment in inv._get_payments_vals():
                total_paid += payment['amount']

            i.amount_paid = total_paid
            i.residual = i.amount - total_paid

    @api.depends('date')
    def get_date_due(self):
        for i in self:
            if i.date:
                i.date_due = fields.Date.add(i.date, months=1)

    contract_id = fields.Many2one('real.estate.contract', string='Contract')

    name = fields.Char(string='Name/Reference', copy=False)
    invoice_id = fields.Many2one('account.invoice', string='Invoice')
    date = fields.Date(string='Date')
    date_due = fields.Date(string='Date Due', compute='get_date_due')
    currency_id = fields.Many2one(related='invoice_id.currency_id', string='Currency')
    amount = fields.Monetary(currency_field='currency_id')
    amount_paid = fields.Monetary(currency_field='currency_id', compute='get_amount_paid')
    residual = fields.Monetary(currency_field='currency_id', compute='get_amount_paid')
    state = fields.Selection(related='invoice_id.state')

    @api.multi
    def create_invoice(self):
        invoice_obj = self.env['account.invoice']

        product = self.env.ref('real_estate.product_quota')
        account_id = getattr(product, 'property_account_income_id')
        account_categ_id = getattr(product.categ_id, 'property_account_income_categ_id')

        contract_id = self.contract_id

        invoice_data = {
            'partner_id': contract_id.partner_id.id,
            'currency_id': contract_id.property_currency_id.id,
            'date_invoice': self.date,
            'date_due': self.date_due,
            'origin': contract_id.name,
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': product.id,
                    'name': self.name,
                    'account_id': account_id.id or account_categ_id.id,
                    'quantity': 1,
                    'invoice_line_tax_ids': [(4, tax.id) for tax in product.taxes_id],
                    'price_unit': self.amount,
                })
            ]
        }

        invoice = invoice_obj.create(invoice_data)

        self.invoice_id = invoice.id

    @api.model
    def cron_validate_invoice(self):
        date = fields.Date.today()

        quota_objs = self.env['real.estate.contract.quota'].search([
            ('state', '=', 'draft'),
            ('date', '=', date),
        ])

        for i in quota_objs:
            i.invoice_id.action_invoice_open()

        _logger.info((date, quota_objs))


class RealEstatePropertyType(models.Model):

    _name = 'real.estate.property.type'
    _description = 'Real State Property Type'

    name = fields.Char(string='Name/Reference', required=1, copy=False)

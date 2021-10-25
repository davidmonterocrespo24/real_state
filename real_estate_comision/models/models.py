# -*- coding: utf-8 -*-

import logging

from odoo import models, api, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TIPO = [('vendedor', 'Vendedor'), ('gerente','Gerente')]


class REComisionConfig(models.Model):
    _name = 'real.estate.comision.config'
    _description = 'Real Estate Comision Conf'

    name = fields.Char(string='Name')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id)
    tipo = fields.Selection([('vendedor', 'Vendedor'), ('Gerente','Gerente')], string='Tipo')
    gerente_id = fields.Many2one('res.users', string='Gerente de Ventas')
    line_ids = fields.One2many('real.estate.comision.config.line', 'config_id', string='Lineas')
    

class REComisionConfigLine(models.Model):
    _name = 'real.estate.comision.config.line'
    _description = 'Real Estate Comision Conf Line'

    desde = fields.Integer(string='Desde', required=1)
    hasta = fields.Integer(string='Hasta', required=1)
    porcent = fields.Float(string='% comision', required=1)
    config_id = fields.Many2one('real.estate.comision.config', string='Configuracion')
    
    
class REComision(models.Model):
    _name = 'real.estate.comision'
    _description = 'Real Estate Comision'
    
    date_from = fields.Date(string='Desde', required=1)
    date_to = fields.Date(string='Hasta', required=1)
    payment_date = fields.Date(string='Fecha a Pagar', required=1)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.user.company_id.id)
    # tipo = fields.Selection(TIPO, string='Tipo', required=1)
    line_ids = fields.One2many('real.estate.comision.line', 'comision_id')
    state = fields.Selection([('draft', 'Borrador'), ('done','Hecho`')])

    @api.multi
    def action_get_lines(self):
        self.line_ids.unlink()
        
        contracts = self.env['real.estate.contract'].sudo().search([
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', '=', 'validate'),
            '|',('company_id', '=', self.env.user.company_id.id),
            ('company_id', '!=', self.env.user.company_id.id),
            
        ], order='representante_id')

        vendedores = set()
        lines = []
        for i in contracts:
            
            amount = i.property_amount
            
            currency_id = i.property_currency_id
            if currency_id and i.company_id and currency_id != i.company_id.currency_id:
                amount = currency_id._convert(
                    i.property_amount, i.company_id.currency_id,
                    i.company_id, i.date or fields.Date.today()
                )

            # if i.representante_id not in vendedores:
            #     vendedores.add(i.representante_id)
            #     lines.append(
            #         (0, 0, {
            #             'name': i.representante_id.sudo().name or 'Sin Vendedor',
            #             'display_type': 'line_section'
            #         })
            #     )

            lines.append(
                (0, 0, {
                    'name': '%s - %s'  % (i.name, i.sudo().company_id.name),
                    'contract_id': i.id,
                    'vendedor_id': i.contacto_id.id,
                    'representante_id': i.representante_id.id,
                    'date': i.date,
                    'property_amount': i.property_amount,
                    'amount': amount,
                    
                })
            )
            
        self.line_ids = lines

    def get_by_vendedor(self, comision):
        data_line = {}
        for l in comision.line_ids:
            if not l.display_type:
                data_line.setdefault(l.vendedor_id, []).append(l)
        _logger.info(data_line)
        return data_line

    def get_by_representante(self, comision):
        data_line = {}
        for l in comision.line_ids:
            if not l.display_type:
                data_line.setdefault(l.representante_id, []).append(l)
        _logger.info(data_line)
        return data_line

    def get_by_gerente(self, comision):
        tarifa = self.env['real.estate.comision.config.line'].search([
            ('config_id.tipo', '=', 'Gerente'),
            ('config_id.company_id', '=', self.company_id.id),
        ], limit=1)

        amount = 0.0
        cant = 0
        for l in comision.line_ids:
            if not l.display_type:
                amount += l.amount
                cant += 1

        return (tarifa.config_id.gerente_id.name or '', cant, amount, self.get_comision(cant, amount, 'Gerente'))

    def get_comision(self, cant, monto, tipo):
        tarifa = self.env['real.estate.comision.config.line'].search([
            ('desde', '<=', cant),
            ('hasta', '>=', cant),
            ('config_id.tipo', '=', tipo),
            ('config_id.company_id', '=', self.company_id.id),
        ])

        comision = 0.0
        if tarifa:
            comision = monto * tarifa.porcent

        return comision

    def get_currency_rate(self, currency, date):
        res = currency._get_rates(self.company_id, date)
        rate = 1.0
        for i in res:
            rate = 1 / res[i]
        return "{:.4f}".format(rate)

    @api.multi
    def create_payslip_input(self):
        vendedores = self.get_by_vendedor(self)

        Input = self.env['payslip.input.import']
        Employee = self.env['hr.employee']
        Contract = self.env['hr.contract']

        for user, lista in vendedores.items():
            if not user :
                continue

            cant = len(lista)
            monto = sum([i.amount for i in lista])
            comision = self.get_comision(user, cant, monto, 'vendedor')

            employee = Employee.search([
                ('address_home_id', '=', user.id),
                ('active', '=', True)
            ], limit=1)
            if not employee:
                continue
                
            contract = Contract.search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'open')
            ], limit=1)

            if employee and contract:
                date_start = self.payment_date
                if int(date_start.day) <= 15:
                    apply_on = '1'
                else:
                    apply_on = '2'

                Input.create({
                    'employee_id': employee.id,
                    'contract_id': contract.id,
                    'frecuency_type': 'variable',
                    'input_id': self.env.ref('payslip_input_import.hr_rule_input_comisiones').id,
                    'amount': comision,
                    'apply_on': apply_on,
                    'start_date': self.payment_date,
                    'end_date': self.payment_date,
                    'frecuency_number': 1,
                })


class REComisionLine(models.Model):
    _name = 'real.estate.comision.line'
    _description = 'Real Estate Comision Line'
    
    name = fields.Char()
    comision_id = fields.Many2one('real.estate.comision')
    contract_id = fields.Many2one('real.estate.contract', string='', readonly=1)
    vendedor_id = fields.Many2one('res.partner', string='Vendedor', readonly=1)
    representante_id = fields.Many2one('res.users', string='Representante', readonly=1)
    date = fields.Date(string='Fecha', readonly=1)
    property_amount = fields.Float(string='', readonly=1)
    amount = fields.Float(string='Monto RD', readonly=1)
    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note")], default=False, help="Technical field for UX purpose.")


class RealEstateContract(models.Model):
    _inherit = 'real.estate.contract'

    vendedor_id = fields.Many2one(states={})
    representante_id = fields.Many2one(states={})
    contacto_id = fields.Many2one('res.partner','Vendedor')    
    procedencia_fondo = fields.Date(string="Espera Procedencia de Fondos", track_visibility='onchange')
    poder_consular = fields.Date(string="Espera Poder Consular Cambio titular", track_visibility='onchange')
    formalizacion = fields.Date(string="Formalizacion", track_visibility='onchange')
    cumplimiento = fields.Date(string="Cumplimiento", track_visibility='onchange')
    completado = fields.Date(string="Comletado", track_visibility='onchange')

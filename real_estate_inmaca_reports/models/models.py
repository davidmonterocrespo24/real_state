# -*- coding: utf-8 -*-

import logging

from odoo import tools
from odoo import models, api, fields,_
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    precalificacion_banco = fields.Char(string='Precalificacion Bancaria', track_visibility='onchange')
    tipo_contrato = fields.Selection([
            ('Financiamiento', 'Financiamiento'),
            ('Efectivo', 'Efectivo'),
    ], string='Tipo de Saldo/Contrato', track_visibility='onchange')
    
    entidad_bancaria = fields.Char(string='Entidad Bancaria', track_visibility='onchange')
    estado_banco = fields.Selection([
        ('Recopilacion_de_documentos', u'Recopilación de documentos'),
        ('Proceso_de_Tasacion', u'Proceso de Tasacion'),
        ('Validacion_o_depuracion_de_Datos', u'Validacion o depuración de Datos'),
        ('Análisis_o_Comité_de_Credito', u'Análisis o Comité de Crédito'),
        ('Aprobacion', 'Aprobación'),
        ('Contratos_Tripartitos_en_Confeccion', u'Contratos Tripartitos en Confeccion'),
        ('Formalizacion_de_Firmas', u'Formalizacion de Firmas'),
        ('Espera_Desembolso', 'Espera Desembolso'),
        ('Declinacion_Bancaria', 'Declinación Bancaria'),
    ], track_visibility='onchange')
    date_seguimiento = fields.Date('Ultimo Seguimiento')
    
    # compute and search fields, in the same order of fields declaration

    # Constraints and onchanges
    @api.onchange('precalificacion_banco', 'tipo_contrato',
                  'entidad_bancaria', 'estado_banco')
    def _set_date(self):
        self.date_seguimiento = fields.Date.today()
    
    # CRUD methods (and name_get, name_search, ...) overrides
    @api.model
    def create(self, vals):
        vals['name'] = vals['name'].upper()
        return super(ResPartner, self).create(vals)
    # Action methods
        
    # Business methods

class WizardContractCancel(models.TransientModel):
    _name = 'wizard.contract.cancel'
    _inherit = 'wizard.contract.cancel'


    name = fields.Selection([
            ('Voluntad_Propia', 'Voluntad Propia'),
            ('No_Aplica', 'No Aplica a Prestamo'),
            ('Cambio_Titular', 'Cambio Titular'),
            ('Cambio_Unidad', 'Cambio de Unidad'),
            ('Cambio_Unidad_Etapa', 'Cambio de Unidad y Etapa'),
            ('Otro', 'Otro'),
        ], string="Motivo de Desestimiento")

    amount = fields.Float(string='Monto a Reembolsar')
    amount_ing = fields.Float(string='Monto Penalidad')
    
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
        
        if self.amount_ing > 0:
            message += """
                <p><strong>Se genero una Venta por Penalidad por un total de:</strong>{}{:,.2f}</p>
            """.format(currency.name, self.amount_ing)
            
            product_id = self.env['product.product'].search([
                ('name', '=', 'Penalizaciones'),
                ('company_id', '=', contract.company_id.id)
            ])
            
            Sale = self.env['sale.order'].create({
                'partner_id': contract.partner_id.id,
                'order_line': [(0, 0, {
                    'product_id': product_id.id,
                    'name': product_id.name,
                    'product_uom_qty': 1,
                    'price_unit': self.amount_ing,
                })]
            })
            
        contract.message_post(body=message)


class QuotaDetail(models.Model):
    _inherit = 'real.estate.quota.details'

    company_id = fields.Many2one('res.company', string='Compania')
    currency_id = fields.Many2one('res.currency', string="Moneda")
    descuento = fields.Float('Descuento')
    @api.model_cr
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (
         SELECT cuota.id, 
                    cuota.name as quota_name,
                    cuota.contract_id as contract_id,
                    contrato.date as date,
                    contrato.partner_id as partner_id,
                    contrato.property_id as property_id,
                    contrato.company_id as company_id,
                    proyecto.etapa as etapa,
                    proyecto.name as proyecto,
                    contrato.property_amount as property_amount,
                    contrato.tipo as tipo,
                    contrato.state as state,
                    MAX(payment.date) as date_payment,
                    cuota.date_due as date_due,
                    cuota.amount as amount,
                    cuota.discount as descuento,
                    property.currency_id as currency_id,
                    coalesce(SUM(payment_line.to_pay), 0) as amount_paid,
                    (cuota.amount - cuota.discount- coalesce(SUM(payment_line.to_pay), cuota.amount)) as residual
        FROM real_estate_contract_quota cuota
        LEFT JOIN payment_quota_line payment_line ON cuota.id = payment_line.quota_id
        RIGHT JOIN payment_quota payment on payment_line.pago_id = payment.id
        RIGHT JOIN real_estate_contract contrato ON cuota.contract_id = contrato.id
                    LEFT JOIN real_estate_property property on contrato.property_id = property.id
                    LEFT JOIN real_estate_project proyecto on property.project_id = proyecto.id
        WHERE payment.state not in ('draft', 'cancel')
        GROUP BY cuota.id, cuota.name, cuota.contract_id, contrato.date, contrato.partner_id ,
                     contrato.property_id, contrato.property_amount, contrato.tipo, contrato.state, contrato.company_id,
                     cuota.date_due, cuota.amount, proyecto.name, proyecto.etapa, contrato.company_id, property.currency_id
        
        UNION
          SELECT cuota.id, 
                    cuota.name as quota_name,
                    cuota.contract_id as contract_id,
                    contrato.date as date,
                    contrato.partner_id as partner_id,
                    contrato.property_id as property_id,
                    contrato.company_id as company_id,
                    proyecto.etapa as etapa,
                    proyecto.name as proyecto,
                    contrato.property_amount as property_amount,
                    contrato.tipo as tipo,
                    contrato.state as state,
                    cuota.date_due as date_payment,
                    cuota.date_due as date_due,
                    cuota.amount as amount,
                    0 as amount_paid,
                    cuota.discount as descuento,
                    property.currency_id as currency_id,
                    cuota.amount as residual
        FROM real_estate_contract_quota cuota
        RIGHT JOIN real_estate_contract contrato ON cuota.contract_id = contrato.id
                    LEFT JOIN real_estate_property property on contrato.property_id = property.id
                    LEFT JOIN real_estate_project proyecto on property.project_id = proyecto.id
        WHERE cuota.id not in (SELECT cuota.id
        FROM real_estate_contract_quota cuota
            LEFT JOIN payment_quota_line payment_line ON cuota.id = payment_line.quota_id
            RIGHT JOIN payment_quota payment on payment_line.pago_id = payment.id
            RIGHT JOIN real_estate_contract contrato ON cuota.contract_id = contrato.id
            LEFT JOIN real_estate_property property on contrato.property_id = property.id
            LEFT JOIN real_estate_project proyecto on property.project_id = proyecto.id
        WHERE payment.state not in ('draft', 'cancel')
        GROUP BY cuota.id, cuota.name, cuota.contract_id, contrato.date, contrato.partner_id ,
             contrato.property_id, contrato.property_amount, contrato.tipo, contrato.state, contrato.company_id,
             cuota.date_due, cuota.amount, proyecto.name, proyecto.etapa, property.currency_id
        ) 
                )""" % (self._table))


class PaymentQuota(models.Model):
    _name = 'payment.quota'
    _inherit = ['payment.quota', 'mail.thread']

    state = fields.Selection(track_visibility=True)

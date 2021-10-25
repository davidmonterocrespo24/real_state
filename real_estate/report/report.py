#-*- coding:utf-8 -*-

import logging
from collections import defaultdict
from odoo import api, models

_logger = logging.getLogger(__name__)

class ReportEstadoCliente(models.AbstractModel):
    _name = 'report.real_estate.estado_cliente'

    def pagos(self, quota_id):
        """
            res[1] = [{}, {}, {}]
            res[2] = [{}, {}, {}, {}]
            ...
            res[12] = [{}]
        """
        result = {}
        res = {}
        # for line in quota_ids:
        #     result.setdefault(line.contract_id.id, {})
        #     result[line.contract_id.id].setdefault(line.contract_id, line)
        #     # result[line.contract_id.id][line.id] |= line
        # _logger.info(('AQUI', result))
        # for contract_id, lines_dict in result.items():
        #     _logger.info(('AQUI', pago_id, lines_dict))
        #     res.setdefault(contract_id, [])
        #     for contract, lines in lines_dict.items():
        #         res[payslip_id].append({
        #             'register_name': register.name,
        #             'total': sum(lines.mapped('total')),
        #         })
        #         for line in lines:
        #             res[payslip_id].append({
        #                 'name': line.name,
        #                 'code': line.code,
        #                 'quantity': line.quantity,
        #                 'amount': line.amount,
        #                 'total': line.total,
        #             })


        pagos = self.env['payment.quota.line'].search([
            ('pago_id.state', '=', 'done'), ('quota_id', '=', quota_id)
        ])

        return pagos

    @api.model
    def _get_report_values(self, docids, data=None):
        Contract = self.env['real.estate.contract'].browse(docids)

        return {
            'doc_ids': docids,
            'doc_model': 'hr.payslip',
            'docs': Contract,
            'data': data,
            'pagos': self.pagos #(Contract.mapped('quota_ids')),
        }


class PaymentDetailsReport(models.AbstractModel):
    _name = 'report.real_estate.cumplimiento'
    _description = 'Real Estate Cumplimiento Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        tipo = defaultdict(int)
        nacionalidad = defaultdict(int)
        residencia = defaultdict(int)
        categoria = defaultdict(int)
        actividad = defaultdict(int)

        temp_partner = self.env['res.partner'].browse(1)

        tipos = dict(temp_partner._fields['tipo_cliente'].selection)
        riesgos = dict(temp_partner._fields['calificacion_riesgo'].selection)
        actividades = dict(temp_partner._fields['actividad_economica'].selection)
        tipo_cliente = {
            'dop': {'cnt': 0, 'monto': 0},
            'other': {'cnt': 0, 'monto': 0},
        }

        for i in tipos.values(): tipo[i] = {'cantidad': 0, 'monto': 0.0}
        for i in actividades.values(): actividad[i] = 0
        for i in riesgos.values(): categoria[i] = 0

        lst_partners = []
        DOP_currency = self.env['res.currency'].search([('name', '=', 'DOP')])

        cnt = len(docids)
        total = 0
        for o in self.env['payment.quota'].browse(docids):
            partner_id = o.contract_id.x_studio_comprador_final_1 #o.partner_id

            if partner_id.id not in lst_partners:
                nacionalidad[partner_id.nacionalidad_id.name] += 1
                residencia[partner_id.residencia_id.name] += 1
                categoria[riesgos.get(partner_id.calificacion_riesgo)] += 1
                actividad[actividades.get(partner_id.actividad_economica, 'Otros')] += 1

                pt = 'dop' if partner_id.nacionalidad_id.code == 'DO' else 'other'
                tipo_cliente[pt]['cnt'] += 1

                partner_type = tipos.get(partner_id.tipo_cliente)

                if o.currency_payment_id.name == "DOP":
                    amount = o.monto_divisa
                elif o.tasa != 1.0:
                    amount = o.amount
                else:        
                    amount = o.currency_payment_id._convert(o.amount, DOP_currency,
                                                            o.contract_id.company_id, o.date)
                total += amount
                if partner_type in tipo:
                    if partner_id.id not in lst_partners:
                        tipo[partner_type]['cantidad'] += 1
                    tipo[partner_type]['monto'] += amount
                else:
                    tipo[partner_type] = {'cantidad': 1, 'monto': amount}
    
                tipo_cliente[pt]['monto'] += amount
    
                lst_partners.append(partner_id.id)

        pagos = self.env['payment.quota'].browse(docids)

        docargs = {
            'doc_ids': docids,
            'doc_model': 'payment.quota',
            'docs': self,
            'cantidad': cnt,
            'total': total,
            'pagos': pagos,
            'tipo': dict(tipo),
            'tipo_cliente': tipo_cliente,
            'nacionalidad': dict(nacionalidad),
            'residencia': dict(residencia),
            'categoria': dict(categoria),
            'actividad': dict(actividad),
        }
        return docargs


class PaymentsReport(models.AbstractModel):
    _name = 'report.real_estate.cuadre_caja'
    _description = 'Real Estate Cuadre de Caja Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        cnt = len(docids)
        tree = lambda: defaultdict(dict)
        tipo = defaultdict(tree)
        currencies = []
        resume = {}

        pagos = self.env['payment.quota'].browse(docids)

        for p in pagos:
            if p.currency_payment_id.name in tipo:
                if p.forma_pago in tipo[p.currency_payment_id.name]:
                    tipo[p.currency_payment_id.name][p.forma_pago]['cnt'] += 1
                    tipo[p.currency_payment_id.name][p.forma_pago]['total'] += p.monto_divisa
                else:
                    tipo[p.currency_payment_id.name][p.forma_pago] = {
                            'cnt': 1, 'total': p.monto_divisa
                    }
            else:
                tipo[p.currency_payment_id.name][p.forma_pago] = {
                        'cnt': 1, 'total': p.monto_divisa
                }

            if p.currency_payment_id.id in resume:
                resume[p.currency_payment_id.id]['cnt'] += 1
                resume[p.currency_payment_id.id]['total'] += p.monto_divisa
            else:
                currencies.append(p.currency_payment_id.name)
                resume[p.currency_payment_id.id] = {
                    'currency': p.currency_payment_id.name,
                    'cnt': 1,
                    'total': p.monto_divisa
                }

        docargs = {
            'doc_ids': docids,
            'doc_model': 'payment.quota',
            'docs': self,
            'cantidad': cnt,
            'pagos': pagos,
            'tipos': tipo,
            'currencies': set(currencies),
            'resume': resume,
        }

        return docargs

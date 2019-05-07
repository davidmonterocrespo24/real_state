#-*- coding:utf-8 -*-

import logging
from odoo import api, models

_logger = logging.getLogger(__name__)


class PaymentDetailsReport(models.AbstractModel):
    _name = 'report.real_estate.report_paymentdetails'
    _description = 'Real Estate Payment Details Report'

    def get_invoice_payments(self, quota_ids):
        _logger.info(quota_ids)

        res = {}
        for quota in quota_ids.filtered('invoice_id'):
            res.setdefault(quota.id, [])

            _logger.info((quota,quota.invoice_id,quota.invoice_id._get_payments_vals()))
            for payment in quota.invoice_id._get_payments_vals():
                res[quota.id].append({
                    'name': payment['name'],
                    'date': payment['date'],
                    'currency': payment['currency'],
                    'amount': payment['amount']
                })
            _logger.info((res, quota))
        return res

    @api.model
    def _get_report_values(self, docids, data=None):
        contract = self.env['real.estate.contract'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'real.estate.contract',
            'docs': contract,
            'data': data,
            'get_invoice_payments': self.get_invoice_payments(contract.mapped('quota_ids')),
        }

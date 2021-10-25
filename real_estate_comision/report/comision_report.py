# -*- coding: utf-8 -*-

import logging

from odoo import models, api, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class REComision(models.AbstractModel):
    _name = 'report.real_estate_comision.comision'
    
    def get_porcent(self, lines, type='vendedor'):
        
        pass
    
    def get_by_vendedor(self, comision):
        data_line = {}
        for l in comision.line_ids:
            data_line.setdefault(l.vendedor_id, []).append(l)
        _logger.info(data_line)
        return data_line

    def get_by_representante(self, lines):
        data_line = {}
        for l in lines:
            data_line.setdefault(l.representante, []).append(l)
        return data_line


    @api.model
    def _get_report_values(self, docids, data=None):
        report_obj = self.env['ir.actions.report']
        report = report_obj._get_report_from_name('module.report_name')
        docargs = {
            'doc_ids': docids,
            'doc_model': report.model,
            'docs': self,
        }
        return docargs
    #
    # @api.model
    # def _get_report_values(self, docids, data=None):
    #     comision = self.env['real.estate.comision'].browse(docids)
    #
    #     docargs = {
    #         'doc_ids': docids,
    #         'doc_model': 'real.estate.comision',
    #         'docs': self,
    #         'get_by_vendedor': self.get_by_vendedor(comision)
    #     }
    #
    #     return docargs
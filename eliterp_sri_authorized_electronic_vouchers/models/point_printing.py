# -*- coding: utf-8 -*-

from odoo import fields, api, models, _
from odoo.exceptions import UserError


class PointPrinting(models.Model):
    _inherit = 'sri.point.printing'

    def _get_sequence(self, type='out_invoice'):
        CODE = {
            'out_invoice': 'electronic.invoice',
            'out_refund': 'electronic.refund'
        }
        company = self.company_id
        sequence = self.env['ir.sequence'].with_context(force_company=company.id).next_by_code(CODE[type])
        if not sequence:
            raise UserError(
                _(
                    "No está definida la secuencia para documento electrónico para compañía: %s") % company.name)
        return sequence

    allow_electronic_invoices = fields.Boolean('Permitir factura electrónica?', default=False)
    allow_electronic_credit_note = fields.Boolean('Permitir N/C electrónica?', default=False)
    allow_electronic_debit_note = fields.Boolean('Permitir N/D electrónica?', default=False)
    allow_electronic_waybill = fields.Boolean('Permitir G/R electrónica?', default=False)
    allow_electronic_withhold = fields.Boolean('Permitir retención electrónica?', default=False)


class Invoice(models.Model):
    _inherit = 'account.invoice'

    @api.onchange('point_printing_id')
    def _onchange_point_printing_id(self):
        """
        Al cambiar punto de impresión si tiene habilitados los campos de documento electrónico se
        coloca el campo 'is_electronic' a True
        TODO: Revisar si es la mejor forma realizarlo así, pendiene el secuencial de documento
        :return:
        """
        point_printing = self.point_printing_id
        self.is_electronic = point_printing.allow_electronic_invoices or point_printing.allow_electronic_credit_note

class Retention(models.Model):
    _inherit = 'account.retention'

    @api.onchange('point_printing_id')
    def _onchange_point_printing_id(self):
        """
        Al cambiar punto de impresión si tiene habilitados los campos de documento electrónico se
        coloca el campo 'is_electronic' a True
        :return:
        """
        point_printing = self.point_printing_id
        self.is_electronic = point_printing.allow_electronic_withhold
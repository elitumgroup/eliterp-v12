# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime


class PaymentForms(models.Model):
    _name = 'sri.payment.forms'
    _description = _("Forma de pago SRI")

    _order = "code asc"

    @api.multi
    def name_get(self):
        """
        Cambiamos nombre a mostrar de registros
        :return list:
        """
        res = []
        for data in self:
            res.append((data.id, "{0} [{1}]".format(data.name, data.code)))
        return res

    name = fields.Char('Nombre', required=True)
    code = fields.Char('Código', size=2, required=True)

    _sql_constraints = [
        ('code_unique', 'unique (code)', 'El código debe ser único.')
    ]


class ProofSupport(models.Model):
    _name = 'sri.proof.support'
    _description = _("Sustentos del comprobante")

    _order = "code asc"

    @api.multi
    def name_get(self):
        """
        Cambiamos nombre a mostrar de registros
        :return list:
        """
        res = []
        for data in self:
            res.append((data.id, "{0} [{1}]".format(data.name, data.code)))
        return res

    name = fields.Char('Nombre', required=True)
    code = fields.Char('Código', size=2, required=True)

    _sql_constraints = [
        ('code_unique', 'unique (code)', 'El código debe ser único.')
    ]


class AuthorizedVouchers(models.Model):
    _name = 'sri.authorized.vouchers'
    _description = _("Comprobantes autorizados")

    _order = "code asc"

    @api.multi
    def name_get(self):
        """
        Cambiamos nombre a mostrar de registros
        :return list:
        """
        res = []
        for data in self:
            res.append((data.id, "{0} [{1}]".format(data.name, data.code)))
        return res

    name = fields.Char('Nombre', required=True)
    code = fields.Char('Código', size=2, required=True)
    # TODO: Poner por defecto los sustentos de cada comprobante
    proof_support_ids = fields.Many2many('sri.proof.support', string='Sustentos del comprobante')

    _sql_constraints = [
        ('code_unique', 'unique (code)', _("El código debe ser único."))
    ]


class Shop(models.Model):
    _inherit = 'sale.shop'

    establishment = fields.Char('Nº Establecimiento', size=3, required=True)

    _sql_constraints = [
        ('establishment_unique', 'unique (establishment, company_id)', 'El nº de establecimiento debe ser único por compañía!'),
    ]


class SriPointPrinting(models.Model):
    _name = 'sri.point.printing'
    _description = _("Punto de impresión SRI")
    _order = 'shop_id'

    @api.multi
    def _get_authorization(self, t=None):
        """
        Verificamos si tiene autorización del SRI y seleccionamos la primer qué encuentre
        esste método sirve para asegurarnos de qué exista al menos una.
        :param type:
        :return:
        """
        type = {
            'out_invoice': '18',
            'out_refund': '04',
            'retention': '07'
        }
        sri_authorization = self.env['sri.authorization'].search([
            ('point_printing_id', '=', self.id),
            ('authorized_voucher_id.code', '=', type[t]),
            ('is_valid', '=', True)
        ], limit=1)
        if not sri_authorization:
            raise UserError(_(
                'No ha configurado la autorización del SRI (NC) para este punto de impresión (%s). O la misma puede estar vencida.' %
                self.name_get()[0][1]))
        else:
            return sri_authorization

    @api.multi
    def name_get(self):
        """
        Cambiamos nombre a mostrar de registros
        :return list:
        """
        res = []
        for data in self:
            res.append((data.id, "{0} - {1}".format(data.shop_id.establishment, data.emission_point)))
        return res

    shop_id = fields.Many2one('sale.shop', 'Establecimiento', required=True)
    emission_point = fields.Char('Punto emisión', size=3, default='001', required=True)
    company_id = fields.Many2one('res.company', string='Compañía')

    _sql_constraints = [
        ('point_printing_unique', 'unique(shop_id, emission_point, company_id)',
         "El punto de impresión debe ser único por nº establecimiento!")
    ]


class SriAuthorization(models.Model):
    _name = 'sri.authorization'
    _description = _("Autorizaciones SRI")
    _rec_name = 'authorization'

    _order = "expiration_date desc"

    @api.multi
    def name_get(self):
        """
        Cambiamos nombre a mostrar de registros
        :return list:
        """
        res = []
        for data in self:
            if not data.is_electronic:
                res.append((data.id, "{0} [{1}] de {2} a {3}".format(
                    data.authorization,
                    data.authorized_voucher_id.code,
                    data.initial_number,
                    data.final_number
                )))
            else:
                res.append((data.id, "{0} [{1}] Electrónica".format(
                    data.authorized_voucher_id.name,
                    data.point_printing_id.name
                )))
        return res

    def _check_authorization(self, values):
        """
        Verificamos no exista una autorización (Físicas)
        :return:
        """
        if self.search([
            ('company_id', '=', values['company_id']),
            ('point_printing_id', '=', values['point_printing_id']),
            ('authorized_voucher_id', '=', values['authorized_voucher_id']),
            ('is_valid', '=', True),
            ('is_electronic', '=', False)
        ]):
            raise ValidationError(_("Ya existe una Autorización válida del SRI para estos parámetros."))

    @api.model
    def create(self, vals):
        self._check_authorization(vals)
        return super(SriAuthorization, self).create(vals)

    @api.multi
    def unlink(self):
        """
        Al borrar evitar eliminar autorización relacionadas con documentos (Facturas, N/C, etc.)
        :return object:
        """
        invoices = self.env['account.invoice']
        for record in self:
            if bool(invoices.search([('sri_authorization_id', '=', record.id)])):
                raise ValidationError(_("Está Autorización SRI está relacionada a un documento."))
        return super(SriAuthorization, self).unlink()

    @api.model
    def _default_company(self):
        """
        Por defecto mandamos la compañía del usuario
        :return object:
        """
        return self.env.user.company_id

    @api.multi
    def is_valid_number(self, number):
        """
        Si es número inválido, no está en el rango ingresado de la autorización
        :param number:
        :return:
        """
        if self.initial_number <= number <= self.final_number:
            return
        else:
            raise ValidationError(_(
                "Secuencial no está entre rango ingresado en autorización %s. "
                "Debe crear una nueva autorización del SRI o corregirla."
                % self.authorization))

    @api.one
    @api.constrains('final_number')
    def _check_final_number(self):
        """
        Verificamos número final si no es factura electrónica
        :return:
        """
        if self.final_number < self.initial_number and not self.is_electronic:
            raise ValidationError(_("Número final no puede ser menor al inicial."))

    @api.one
    @api.depends('expiration_date')
    def _compute_is_valid(self):
        """
        Calculamos sea una autorización válida (No se muestra en documentos, soló es para físicas)
        :return:
        """
        if not self.is_electronic:
            self.is_valid = datetime.today().date() < self.expiration_date

    initial_number = fields.Integer('Nº Inicial', default=1, required=True)
    final_number = fields.Integer('Nº Final', default=50, size=9)
    authorization = fields.Char('Nº Autorización', size=10)
    authorized_voucher_id = fields.Many2one('sri.authorized.vouchers', 'Comprobante autorizado', required=True)
    is_valid = fields.Boolean('Es válida?', compute='_compute_is_valid', store=True)
    expiration_date = fields.Date('Fecha de expiración')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=_default_company)
    point_printing_id = fields.Many2one('sri.point.printing', string='Punto de impresión', required=True)
    is_electronic = fields.Boolean('Es electrónica?', default=False)

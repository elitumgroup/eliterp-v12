# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError, UserError
import re
from odoo import fields, models, api, _
import base64
import logging

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
except ImportError:
    _logger.debug(_('No se puede importar librería xlsxwriter.'))

class Invoice(models.Model):
    _inherit = 'account.invoice'

    ISSUANCE_DOCUMENTS = [
        'out_invoice',
        'out_refund'
    ]

    @api.multi
    def name_get(self):
        """
        Cambios los registros a mostrar
        :return:
        """
        TYPES = {
            'out_invoice': _('Invoice'),
            'in_invoice': _('Vendor Bill'),
            'out_refund': _('Credit Note'),
            'in_refund': _('Vendor Credit note'),
        }
        result = []
        for inv in self:
            result.append((inv.id, "%s [%s]" % (TYPES[inv.type], inv.reference or '*')))
        return result

    @api.one
    @api.depends('serial_number', 'invoice_number', 'point_printing_id')
    def _compute_reference(self):
        """
        Calcular el número de documento dependiendo del tipo
        :return:
        """
        if self.type in self.ISSUANCE_DOCUMENTS:
            self.reference = '{0}-{1}-{2}'.format(
                self.point_printing_id.shop_id.establishment,
                self.point_printing_id.emission_point,
                self.invoice_number if self.invoice_number else '*'
            )
        else:
            self.reference = '{0}-{1}'.format(
                self.serial_number,
                self.invoice_number
            )

    @api.onchange('invoice_number')
    def _onchange_invoice_number(self):
        """
        Rellenamos de 0 el número de factura
        :return:
        """
        if self.invoice_number:
            self.invoice_number = self.invoice_number.zfill(9)

    @api.multi
    def action_move_create(self):
        """
        Agregamos el proyecto y división al movimiento creado
        :return:
        """
        result = super(Invoice, self).action_move_create()
        for inv in self:
            inv.move_id.write({
                'company_division_id': inv.company_division_id.id,
                'project_id': inv.project_id.id
            })
        return result

    @api.constrains('invoice_number')
    def _check_invoice_number(self):
        """
        Validamos qué secuencial este entre el rango ingresado en autorización
        :return:
        """
        if not self.type in self.ISSUANCE_DOCUMENTS:
            return
        if self.invoice_number and not self.is_electronic:
            self.sri_authorization_id.is_valid_number(int(self.invoice_number))

    @api.constrains('authorization')
    def _check_authorization(self):
        """
        Verificamos que la autorización sean los dígitos correctos para plantilla ATS (Compras)
        :return:
        """
        if self.type in self.ISSUANCE_DOCUMENTS:
            return
        if self.authorization and len(self.authorization) not in [10, 37, 49]:
            raise ValidationError('Debe ingresar 10, 37 o 49 dígitos según el tipo de autorización.')

    @api.one
    @api.depends('amount_total')
    def _compute_validate_payment_form(self):
        """
        Calcular si se debe colocar la forma de pago
        :return:
        """
        self.validate_payment_form = self.amount_total > 1000

    @api.constrains('serial_number')
    def _check_serial_number(self):
        """
        Verificamos qué número de serie de proveedores sea correcto
        :return:
        """
        if self.type not in self.ISSUANCE_DOCUMENTS:
            if not re.match("\d{3,}-\d{3,}", self.serial_number):
                raise ValidationError("Nº Serie debe ser 001-001.")

    @api.multi
    def invoice_validate(self):
        """
        ME: Revisamos factura d cliente no esté repetida
        :return:
        """
        result = super(Invoice, self).invoice_validate()
        self._check_duplicate_reference()
        return result

    @api.multi
    def _check_duplicate_supplier_reference(self):
        for invoice in self:
            # MM: Le quitamos el filtro de la compañía
            # refuse to validate a vendor bill/credit note if there already exists one with the same reference for the same partner,
            # because it's probably a double encoding of the same bill/credit note
            if invoice.type in ('in_invoice', 'in_refund') and invoice.reference:
                if self.search([('type', '=', invoice.type), ('reference', '=', invoice.reference),
                                ('commercial_partner_id', '=', invoice.commercial_partner_id.id),
                                ('state', 'in', ['open', 'paid']),
                                ('id', '!=', invoice.id)]):
                    raise UserError(_(
                        "Duplicated vendor reference detected. You probably encoded twice the same vendor bill/credit note."))

    @api.multi
    def _check_duplicate_reference(self):
        """
        Verificamos no existan documentos de cliente repetidos
        :return:
        """
        for invoice in self:
            if invoice.type in ('out_invoice', 'out_refund') and invoice.reference and not invoice.is_electronic:
                if self.search([('type', '=', invoice.type), ('reference', '=', invoice.reference),
                                ('id', '!=', invoice.id), ('company_id', '=', invoice.company_id.id)]):
                    raise UserError(_(
                        "Se detectó secuencial duplicado para pre-impreso de Autorización del SRI (%s)." % invoice.sri_authorization_id.authorization))

    @api.multi
    def copy(self, default=None):
        """
        Al duplicar eliminamos origen y comentario si está cancelada
        :param default:
        :return:
        """
        default = default or {}
        default['comment'] = False if self.state == 'cancel' else self.comment
        default['origin'] = False
        record = super(Invoice, self).copy(default=default)
        return record

    @api.model
    def _default_point_printing(self):
        """
        Defecto de punto de impresión
        :return:
        """
        company = self.env.user.company_id.id
        point_printing_ids = self.env['sri.point.printing'].search([('company_id', '=', company)], limit=1)
        return point_printing_ids

    @api.model
    def _default_payment_form(self):
        """
        Defecto forma de pago
        :return:
        """
        payment_forms_ids = self.env['sri.payment.forms'].search([], limit=1)
        return payment_forms_ids


    def _generate_xlsx_report(self, workbook):
        # Formatos
        money_format = workbook.add_format({'num_format': '$#,##0.00', 'bold': 1})
        sheet = workbook.add_worksheet('Factura')
        amount_words = self.env['res.functions'].get_amount_to_word(self.amount_total).upper()
        ruc = self.company_id.vat # Por empresa
        if ruc == '0992968168001':
            sheet.write(7, 1, self.partner_id.name)
            sheet.write(7, 8, self.partner_id.documentation_number)
            sheet.write(8, 1, self.partner_id.street)
            sheet.write(9, 2, self.date_invoice)
            sheet.write(9, 9, self.payment_term_id.name if self.payment_term_id else 'Contado')
            row = 12
            for line in self.invoice_line_ids:
                sheet.write(row, 1, line.quantity)
                sheet.write(row, 3, line.name)
                sheet.write(row, 5, line.price_unit, money_format)
                sheet.write(row, 7, line.price_subtotal, money_format)
                row += 1
            sheet.write(22, 10, self.amount_untaxed, money_format)
            sheet.write(23, 1, amount_words)
            sheet.write(24, 3, self.payment_form_id.name)
            sheet.write(24, 9, ("12"))
            sheet.write(24, 10, self.amount_tax, money_format)
            sheet.write(25, 10, self.amount_total, money_format)
        else:
            return

    @api.multi
    def print_out_invoice_xlsx(self):
        """
        Imprimimos factura en xlsx
        :return:
        """
        self.ensure_one()
        self.write(self.create_xlsx_report('Factura', None))

    def create_xlsx_report(self, name, context=None):
        name = name + '.xlsx'
        workbook = xlsxwriter.Workbook(name, self.get_workbook_options())
        self._generate_xlsx_report(workbook)
        workbook.close()
        with open(name, "rb") as file:
            file = base64.b64encode(file.read())
        data = {
            'file_invoice': file,
            'file_invoice_name': name
        }
        return data

    def get_workbook_options(self):
        return {'in_memory': True}

    def generate_xlsx_report(self, workbook, context):
        # TODO: Revisar está función
        pass

    invoice_number = fields.Char('Secuencial', readonly=True, states={'draft': [('readonly', False)]},
                                 help="Número de factura de la compañía según el tipo.", copy=False, size=9)  # CM
    validate_payment_form = fields.Boolean('Validación forma de pago', compute='_compute_validate_payment_form')
    payment_form_id = fields.Many2one('sri.payment.forms', string='Forma de pago', readonly=True,
                                      states={'draft': [('readonly', False)]}, default=_default_payment_form)
    point_printing_id = fields.Many2one('sri.point.printing', string='Punto de impresión', readonly=True,
                                        states={'draft': [('readonly', False)]}, default=_default_point_printing)
    sri_authorization_id = fields.Many2one('sri.authorization', string='Autorización SRI', readonly=True,
                                           domain="[('authorized_voucher_id.code', '=', {'out_invoice': ['18'], 'out_refund': ['04']}.get(type, [])), ('point_printing_id', '=', point_printing_id)]",
                                           states={'draft': [('readonly', False)]})
    authorization = fields.Char('Nº Autorización', readonly=True, size=49,
                                states={'draft': [('readonly', False)]})
    reference = fields.Char('Nº Factura', compute='_compute_reference', store=True, readonly=True,
                            copy=False)  # Modificamos el campo para facilitar referencia (SRI Ecuador)
    proof_support_id = fields.Many2one('sri.proof.support', string='Sustento del comprobante', readonly=True,
                                       states={'draft': [('readonly', False)]})
    serial_number = fields.Char(string='Nº Serie', size=7,
                                readonly=True, states={'draft': [('readonly', False)]})
    is_electronic = fields.Boolean(string='Es electrónica?',
                                   default=False)  # Dejar para futuras implementaciones de F.E.
    concept = fields.Char('Concepto', readonly=True, states={'draft': [('readonly', False)]})
    file_invoice = fields.Binary('Factura (.xlsx)')
    file_invoice_name = fields.Char('Nombre de archivo', readonly=True)
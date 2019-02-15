# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero
import re
from odoo.exceptions import ValidationError, RedirectWarning
from datetime import datetime


class Invoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def _other_actions(self):
        """
        Cancelamos retención
        :return:
        """
        res = super(Invoice, self)._other_actions()
        self.retention_id.write({'state': 'cancel'})
        return res

    @api.multi
    def add_retention(self):
        """
        Abrimos ventana para agregar retención a proveedor
        :return:
        """
        view = self.env.ref('eliterp_treasury.view_form_retention_purchase_wizard')
        context = {
            'defaul_date_retention': self.date_invoice,
            'default_invoice_id': self.id,
            'default_partner_id': self.partner_id.id,
            'default_type': 'purchase'
        }
        return {
            'name': "Retención a proveedor",
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'account.retention',
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }

    @api.multi
    def open_retention(self):
        """
        Abrimos la retención desde la factura
        :return:
        """
        retention = self.env['account.retention'].search([('invoice_id', '=', self.id)])
        imd = self.env['ir.model.data']
        if self.type == 'out_invoice':
            action = imd.xmlid_to_object('eliterp_treasury.action_retention_sale')
            list_view_id = imd.xmlid_to_res_id('eliterp_treasury.view_tree_retention_sale')
            form_view_id = imd.xmlid_to_res_id('eliterp_treasury.view_form_retention_sale')
        else:
            action = imd.xmlid_to_object('eliterp_treasury.action_retention_purchase')
            list_view_id = imd.xmlid_to_res_id('eliterp_treasury.view_tree_retention_purchase')
            form_view_id = imd.xmlid_to_res_id('eliterp_treasury.view_form_retention_purchase')
        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
        if len(retention) > 1:
            result['domain'] = "[('id','in',%s)]" % retention.ids
        elif len(retention) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = retention.ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    @api.multi
    def action_invoice_open(self):
        """
        Al validar factura si es retención de compra confirmamos su consecutivo (No SRI)
        :return object:
        """
        if self.type == 'in_invoice':
            if not self.retention_id:
                raise UserError(_("Debe ingresar retención de documento."))
            else:
                self.retention_id.confirm()
        res = super(Invoice, self).action_invoice_open()
        return res

    @api.one
    @api.depends('invoice_line_ids.price_subtotal',
                 'tax_line_ids.amount', 'currency_id',
                 'company_id', 'date_invoice')
    def _compute_amount(self):
        """
        MM: Realizamos nuevo cálculo por motivo de las retenciones e impuestos
        :return:
        """
        round_curr = self.currency_id.round
        self.amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
        amount_tax = 0.00
        amount_retention = 0.00
        # Sumamos grupo de impuestos Retenciones
        for line in self.tax_line_ids:
            if line.amount >= 0:
                amount_tax += line.amount
            else:
                amount_retention += line.amount
        self.amount_tax = round_curr(amount_tax)
        self.amount_retention = round_curr(amount_retention)
        self.amount_total = self.amount_untaxed + self.amount_tax
        amount_total_company_signed = self.amount_total
        amount_untaxed_signed = self.amount_untaxed
        if self.currency_id and self.company_id and self.currency_id != self.company_id.currency_id:
            currency_id = self.currency_id.with_context(date=self.date_invoice)
            amount_total_company_signed = currency_id.compute(self.amount_total, self.company_id.currency_id)
            amount_untaxed_signed = currency_id.compute(self.amount_untaxed, self.company_id.currency_id)
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        self.amount_total_company_signed = amount_total_company_signed * sign
        self.amount_total_signed = self.amount_total * sign
        self.amount_untaxed_signed = amount_untaxed_signed * sign
        total_base_taxed = 0.00
        total_base_zero_iva = 0.00
        for line in self.invoice_line_ids:
            for tax in line.invoice_line_tax_ids:
                if tax.amount > 0:
                    total_base_taxed += line.price_subtotal
                else:
                    total_base_zero_iva += line.price_subtotal
        self.base_zero_iva = total_base_zero_iva
        self.base_taxed = total_base_taxed

    @api.one
    @api.depends(
        'state', 'currency_id', 'invoice_line_ids.price_subtotal',
        'move_id.line_ids.amount_residual',
        'move_id.line_ids.currency_id')
    def _compute_residual(self):
        """
        MM: Cambiamos el cálculo del saldo por motivo de las retenciones
        :return:
        """
        residual = 0.0
        residual_company_signed = 0.0
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        for line in self.sudo().move_id.line_ids:
            if line.account_id == self.account_id:
                residual_company_signed += line.amount_residual
                if line.currency_id == self.currency_id:
                    residual += line.amount_residual_currency if line.currency_id else line.amount_residual
                else:
                    from_currency = line.currency_id or line.company_id.currency_id
                    residual += from_currency._convert(line.amount_residual, self.currency_id, line.company_id,
                                                       line.date or fields.Date.today())
        self.residual_company_signed = abs(residual_company_signed) * sign
        self.residual_signed = abs(residual) * sign
        self.residual = abs(residual)
        digits_rounding_precision = self.currency_id.rounding
        if float_is_zero(self.residual, precision_rounding=digits_rounding_precision):
            self.reconciled = True
        else:
            self.reconciled = False
        total_base_taxed = 0.00
        total_base_zero_iva = 0.00
        for line in self.invoice_line_ids:
            for tax in line.invoice_line_tax_ids:
                if tax.amount > 0:
                    total_base_taxed += line.price_subtotal
                else:
                    total_base_zero_iva += line.price_subtotal
        self.base_zero_iva = total_base_zero_iva
        self.base_taxed = total_base_taxed

    @api.multi
    def copy(self, default=None):
        """
        Al duplicar eliminamos impuestos de retención de la antigua
        :param default:
        :return:
        """
        record = super(Invoice, self).copy(default=default)
        for tax in record.tax_line_ids.filtered(lambda x: x.tax_id.tax_type == 'retention'):
            tax.unlink()
        return record

    retention_id = fields.Many2one('account.retention', string='Retención', copy=False, ondelete="set null")
    retention_number = fields.Char('Nº Retención', related='retention_id.retention_number')
    amount_retention = fields.Float('(-) Total a retener', store=True,
                                    currency_field='currency_id', compute='_compute_amount')
    base_zero_iva = fields.Float('Base cero IVA', currency_field='currency_id', compute='_compute_amount', store=True)
    base_taxed = fields.Float('Base gravada', currency_field='currency_id', compute='_compute_amount', store=True)


class RetentionLine(models.Model):
    _name = 'account.retention.line'

    _description = _("Líneas de retención")

    @api.onchange('retention_type')
    def _onchange_retention_type(self):
        """
        Al cambiar el tipo de retención cambiamos su base imponible
        :return:
        """
        if self.retention_type:
            if self.retention_type == 'iva':
                self.base_taxable = self.retention_id.base_iva
            else:
                self.base_taxable = self.retention_id.base_taxable

    @api.onchange('tax_id', 'base_taxable')
    def _onchange_tax_id(self):
        """
        Calcular nuevamente el monto de la línea dependiendo del impuesto
        :return:
        """
        self.amount = round((self.tax_id.amount * self.base_taxable) / 100, 2)

    retention_type = fields.Selection([
        ('iva', 'IVA'),
        ('rent', 'Renta')
    ], string='Tipo de retención', required=True)
    tax_id = fields.Many2one('account.tax', string='Impuesto', required=True)
    base_taxable = fields.Float('Base imponible', required=True)
    amount = fields.Float('Monto', required=True)
    retention_id = fields.Many2one('account.retention', string='Retención', ondelete="cascade")
    retention_tax_id = fields.Many2one('account.invoice.tax', string='Impuesto de retención (Factura)')


class RetentionCancel(models.TransientModel):
    _name = 'account.retention.cancel'

    _description = _("Ventana para cancelar retención")

    @api.multi
    def confirm_cancel(self):
        """
        Anulamos retención aplica para retenciones de venta (Pagos)
        :return:
        """
        retention_id = self.env['account.retention'].browse(self._context['active_id'])
        retention_id.move_id.reverse_moves(
            retention_id.date_retention,
            retention_id.journal_id
        )
        retention_id.move_id.write({
            'state': 'cancel',
            'ref': self.description
        })
        retention_id.action_cancel()
        return True

    description = fields.Text('Descripción', required=True)


class InvoiceTax(models.Model):
    _inherit = 'account.invoice.tax'

    retention_id = fields.Many2one('account.retention', 'Retención', ondelete="cascade")


class Retention(models.Model):
    _name = 'account.retention'
    _order = "date_retention desc"
    _inherit = ['mail.thread']

    _description = _("Retención")

    @api.multi
    def open_cancel_wizard(self):
        """
        Abrimos ventana emergente para cancelar retención
        :return: dict
        """
        # Cancelamos la retención directamente si está en estado Borrador
        if self.state == 'draft':
            return self.cancel_retention()
        else:
            return {
                'name': _("Explique motivo"),
                'view_mode': 'form',
                'view_type': 'form',
                'res_model': 'account.retention.cancel',
                'type': 'ir.actions.act_window',
                'target': 'new'
            }

    @api.multi
    def action_cancel(self):
        """
        Cancelamos la retención
        :return:
        """
        self.invoice_id.write({
            'retention_id': False,
        })
        if not self.retention_lines:
            return
        invoice_tax_ids = self.env['account.invoice.tax'].search([
            ('retention_id', '=', self.retention_id.id),
        ])
        invoice_tax_ids.unlink()
        self.invoice_id._compute_amount()
        self.invoice_id._compute_residual()
        self.write({
            'state': 'cancel'
        })
        return True

    @api.multi
    def confirm_retention(self):
        """
        Confirmamos la retención de cliente
        :return:
        """
        if not self.retention_lines:
            raise ValidationError(_("Debe crear alguna línea de retención."))
        journal_id = self.env.ref("eliterp_treasury.journal_retention_customer")
        move_id = self.env['account.move'].create({
            'journal_id': journal_id.id,
            'ref': _("Retención de factura: ") + "%s" % (self.invoice_id.reference),
            'date': self.date_retention
        })
        line_move_retention = self.env['account.move.line'].with_context(check_move_validity=False).create({
            'name': '/',
            'journal_id': journal_id.id,
            'partner_id': self.partner_id.id,
            'account_id': self.partner_id.property_account_receivable_id.id,
            'move_id': move_id.id,
            'credit': self.total,
            'debit': 0.0,
            'date': self.date_retention
        })
        count = len(self.retention_lines)
        for line in self.retention_lines:
            count -= 1
            if count == 0:
                move_line = self.env['account.move.line']
            else:
                move_line = self.env['account.move.line'].with_context(check_move_validity=False)
            move_line.create({
                'name': line.tax_id.name,
                'account_id': line.tax_id.account_id.id,
                'partner_id': self.partner_id.id,
                'journal_id': journal_id.id,
                'move_id': move_id.id,
                'credit': 0.0,
                'debit': line.amount,
                'date': self.date_retention
            })
        move_id.post()
        # La conciliamos con la factura de venta
        line_move_invoice = self.invoice_id.move_id.line_ids.filtered(
            lambda x: x.account_id == self.partner_id.property_account_receivable_id)
        (line_move_invoice + line_move_retention).reconcile()
        return self.write({
            'state': 'confirm',
            'move_id': move_id.id,
            'name': move_id.name
        })

    @api.one
    @api.depends('retention_lines.amount')
    def _compute_total(self):
        """
        Calculamos el total de la retención
        :return:
        """
        self.total = sum(line.amount for line in self.retention_lines)

    @api.onchange('invoice_id')
    def _onchange_invoice_id(self):
        """
        Al cambiar factura colocamos los datos por defecto
        :return:
        """
        self.base_taxable = self.invoice_id.amount_untaxed
        self.base_iva = self.invoice_id.amount_tax

    @api.constrains('retention_number')
    def _check_retention_number(self):
        """
        Verificamos qué número de retención de cliente sea la correcta
        :return:
        """
        if self.type == 'sale':
            if not re.match("\d{3,}-\d{3,}-\d{9,}", self.retention_number):
                raise ValidationError("Nº Retención debe ser en formato 001-001-000000001.")

    def _get_name(self, code):
        company = self.company_id
        sequence = self.env['ir.sequence'].with_context(force_company=company.id).next_by_code(code)
        if not sequence:
            raise UserError(
                _("No está definida la secuencia con código '%s' para compañía: %s") % (code, company.name))
        return sequence

    @api.multi
    def confirm(self):
        """
        Confirmamos retención a proveedor desde factura
        :return:
        """
        name = self._get_name('retention.supplier')
        vals = {
            'state': 'confirm',
            'name': name
        }
        if not self.is_sequential:
            new_number = self._get_name('internal.process')
            vals.update({'retention_number': new_number})
        self.write(vals)

    @api.multi
    def unlink(self):
        """
        Verificamos al borrar no elimine confirmadas o anuladas
        :return:
        """
        for retention in self:
            if retention.state != 'draft':
                raise UserError("No se puede eliminar una retención qué no este en estado borrador.")
        return super(Retention, self).unlink()

    name = fields.Char('Documento', default='Nueva retención', index=True)
    retention_number = fields.Char('Nº Retención', readonly=True, states={'draft': [('readonly', False)]},
                                   track_visibility='onchange')
    base_taxable = fields.Float('Base imponible', readonly=True, states={'draft': [('readonly', False)]})
    base_iva = fields.Float('Base IVA', readonly=True, states={'draft': [('readonly', False)]})
    date_retention = fields.Date('Fecha de emisión', default=fields.Date.context_today, required=True, readonly=True,
                                 states={'draft': [('readonly', False)]}, track_visibility='onchange')
    partner_id = fields.Many2one('res.partner', string='Empresa', readonly=True,
                                 states={'draft': [('readonly', False)]})
    invoice_id = fields.Many2one('account.invoice', string='Factura', readonly=True,
                                 states={'draft': [('readonly', False)]})
    type = fields.Selection([
        ('sale', 'Venta'),
        ('purchase', 'Compra')
    ], string='Tipo')
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirm', 'Confirmada'),
        ('cancel', 'Cancelada')
    ], string='Estado', default='draft', track_visibility='always')
    retention_lines = fields.One2many('account.retention.line', 'retention_id', string='Líneas de retención',
                                      readonly=True,
                                      states={'draft': [('readonly', False)]})
    total = fields.Float(compute='_compute_total', string='Total', store=True, track_visibility='onchange')
    is_sequential = fields.Boolean('Es secuencial?',
                                   help="Si no se marca, la compañía asume la retención.", readonly=True,
                                   states={'draft': [('readonly', False)]}, default=False)
    journal_id = fields.Many2one('account.journal', string='Diario', readonly=True)
    move_id = fields.Many2one('account.move', string='Asiento contable')
    modified_bill = fields.Boolean('Factura modificada?', default=False)  # TODO: Revisar para que sirve esto
    company_id = fields.Many2one('res.company', string='Compañía', related='invoice_id.company_id', store=True)

    @api.depends('date_retention')
    def _compute_period(self):
        """
        Obtenemos el período contable dependiendo de la  fecha de retención
        :return:
        """
        if not self.date_retention:
            self.period_id = False
        else:
            date = self.date_retention
            period = self.env['account.fiscal.year'].search([('name', '=', date.year)])
            if not period:
                err_msg = _("Debes definir algún período contable para comenzar a transaccionar.")
                redir_msg = _("Ir a período contable")
                raise RedirectWarning(err_msg, self.env.ref('account.actions_account_fiscal_year').id, redir_msg)
            else:
                period_id = period.period_lines.filtered(lambda x: x.code == date.month)
                self.period_id = period_id.id

    @api.model
    def create(self, values):
        """
        Al crear actualizamos algunos datos correspondientes la factura
        :param values:
        :return:
        """
        invoice = self.env['account.invoice'].browse(values['invoice_id'])
        retention = super(Retention, self).create(values)
        invoice.write({
            'retention_id': retention.id
        })
        invoice_tax = self.env['account.invoice.tax']
        for line in retention.retention_lines:
            tax_id = invoice_tax.create({
                'retention_id': retention.id,
                'invoice_id': invoice.id,
                'name': line.tax_id.name,
                'tax_id': line.tax_id.id,
                'account_id': line.tax_id.account_id.id,
                'amount': -1 * line.amount
            })
            line.write({'retention_tax_id': tax_id.id})
        return retention

    @api.multi
    def write(self, values):
        """
        TODO: Al editar verificamos líneas de retención
        :param values:
        :return:
        """
        if 'retention_lines' in values:
            for line in values['retention_lines']:
                if line[0] == 0:  # No existe líneas creadas y se modifica la misma
                    retention = self.env['account.tax'].browse(line[2]['tax_id'])
                    amount = line[2]['amount'] if 'amount' in line[2] else 0.00
                    self.env['account.invoice.tax'].create({
                        'invoice_id': self.invoice_id.id,
                        'name': retention.name,
                        'tax_id': retention.id,
                        'account_id': retention.account_id.id,
                        'amount': -1 * amount
                    })
                if line[0] == 1:
                    tax_id = self.env['account.tax'].browse(line[2]['retention_tax_id'])
                    if self.retention_lines.retention_tax_id:
                        self.retention_lines.tax_id.write({
                            'name': tax_id.name,
                            'tax_id': tax_id.id,
                            'account_id': tax_id.account_id.id,
                            'amount': line[2]['amount'] if 'amount' in line[2] else 0.00
                        })
                    else:
                        line_retention = self.retention_lines.browse(line[1])
                        amount = line[2]['amount'] if 'amount' in line[2] else 0.00
                        invoice_tax = self.env['account.invoice.tax'].search([('invoice_id', '=', self.invoice_id.id),
                                                                              ('name', '=',
                                                                               line_retention.tax_id.name),
                                                                              ('tax_id', '=',
                                                                               line_retention.tax_id.id),
                                                                              ('account_id', '=',
                                                                               line_retention.tax_id.account_id.id)])[
                            0]
                        invoice_tax.write({
                            'name': tax_id.name,
                            'tax_id': tax_id.id,
                            'account_id': tax_id.account_id.id,
                            'amount': -1 * amount
                        })
                if line[0] == 2:
                    if not self.modified_bill:
                        if self.retention_lines.retention_tax_id:
                            self.retention_lines.retention_tax_id.unlink()
                        else:
                            line_retention = self.retention_lines.browse(line[1])
                            invoice_tax = \
                                self.env['account.invoice.tax'].search([('invoice_id', '=', self.invoice_id.id),
                                                                        ('name', '=', line_retention.tax_id.name),
                                                                        ('tax_id', '=', line_retention.tax_id.id),
                                                                        ('account_id', '=',
                                                                         line_retention.tax_id.account_id.id)])[0]
                            invoice_tax.unlink()
                    else:
                        values.update({'modified_bill': False})
            self.invoice_id._compute_amount()
            self.invoice_id._compute_residual()
        return super(Retention, self).write(values)

    @api.constrains('date_retention')
    def _check_date_retention(self):
        """
        Verificamos retención no sea mayor a 5 días
        :return:
        """
        d1 = self.invoice_id.date_invoice
        d2 = self.date_retention
        if (d2 - d1).days > 5 or d2 < d1:
            raise ValidationError(_("La retención no puede tener una fecha mayor a 5 días del documento a retener."))

    @api.onchange('point_printing_id', 'reference')
    def _onchange_reference(self):
        """
        Rellenamos de 0 el secuencial
        :return:
        """
        if self.reference:
            self.reference = self.reference.zfill(9)
            if self.type == 'purchase' or self._context.get('default_type') == 'purchase':
                self.retention_number = '{0}-{1}-{2}'.format(
                    self.point_printing_id.shop_id.establishment,
                    self.point_printing_id.emission_point,
                    self.reference if self.reference else '*'
                )

    @api.constrains('reference')
    def _check_reference(self):
        """
        Validamos qué secuencial este entre el rango ingresado en autorización
        :return:
        """
        if self.type == 'sale':
            return
        if self.reference and not self.is_electronic:
            self.sri_authorization_id.is_valid_number(int(self.reference))

    @api.model
    def _default_point_printing(self):
        """
        Defecto de punto de impresión
        :return:
        """
        company = self.env.user.company_id.id
        point_printing_ids = self.env['sri.point.printing'].search([('company_id', '=', company)], limit=1)
        return point_printing_ids

    point_printing_id = fields.Many2one('sri.point.printing', string='Punto de impresión', readonly=True,
                                        states={'draft': [('readonly', False)]}, default=_default_point_printing)
    sri_authorization_id = fields.Many2one('sri.authorization', string='Autorización del SRI', readonly=True,
                                           states={'draft': [('readonly', False)]})
    reference = fields.Char('Secuencial', readonly=True, states={'draft': [('readonly', False)]}, size=9)
    is_electronic = fields.Boolean(string='Es electrónica?', default=False)
    period_id = fields.Many2one('account.period.line', string='Período', store=True, readonly=True,
                                compute='_compute_period')

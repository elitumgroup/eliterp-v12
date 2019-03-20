# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class PayOrderAbstract(models.AbstractModel):
    _name = 'account.pay.order.abstract'
    _description = _('Lógica de las ordenes de pago')

    @api.one
    @api.constrains('amount')
    def _check_amount(self):
        """
        Verificamos el monto no sea mayor al valor por defecto
        """
        if self.amount > self.default_amount:
            raise ValidationError(
                _("Monto mayor al del saldo por pagar del documento (%.2f)." % self.default_amount))

    @api.one
    @api.constrains('date')
    def _check_date(self):
        """
        Verificamos la fecha de la orden de pago no sea menor a la del documento
        """
        if self.date < self.default_date:
            raise ValidationError(_("Fecha de la orden de pago no puede ser menor a la del documento."))

    @api.model
    def _compute_amount(self, invoice_ids):
        total = 0
        for inv in invoice_ids:
            total += inv.residual_pay_order
        return total

    def _get_vals_document(self, active_model, active_ids):
        """
        Obtenemos los valores de la orden de pago dependiendo del documento
        Dejamos está función así para utilizar en otros modelos otros modelos
        u aplicaciones.
        :return:
        """
        vals = {}
        if active_model == 'account.invoice':
            invoice_ids = self.env['account.invoice'].browse(active_ids)
            if len(invoice_ids) > 1:
                # Revisar empresas y cuentas de facturas
                if any(invoice.state != 'open' for invoice in invoice_ids):
                    raise UserError("Soló se puede generar orden de pago de facturas por pagar.")
                if any(inv.partner_id != invoice_ids[0].partner_id for inv in invoice_ids):
                    raise UserError("Soló se puede generar orden de pago de facturas del mismo proveedor.")
                if any(inv.account_id != invoice_ids[0].account_id for inv in invoice_ids):
                    raise UserError("Soló se puede generar orden de pago de facturas con la misma cuenta por pagar.")
            vals.update({
                # Fecha del día
                'date': fields.Date.today(),
                'default_date': fields.Date.today(),
                'type': 'invoice',
                'amount': self._compute_amount(invoice_ids),
                'default_amount': self._compute_amount(invoice_ids),
                'origin': ', '.join(str(i.number) for i in invoice_ids),
                'invoice_ids': [(6, 0, invoice_ids.ids)],
                'company_id': self.env.user.company_id.id,
                'beneficiary': invoice_ids[0].partner_id.name
            })
        return vals

    @api.model
    def default_get(self, fields):
        """
        Valores por defecto dependiendo del modelo del documento
        :param fields:
        :return:
        """
        result = super(PayOrderAbstract, self).default_get(fields)
        if 'active_ids' in self._context:
            records = self._context['active_ids']
        else:
            records = self._context['active_id']
        vals = self._get_vals_document(self._context['active_model'], records)
        result.update(vals)
        return result

    date = fields.Date('Fecha de pago', default=fields.Date.context_today, required=True)
    type = fields.Selection([
        ('invoice', 'Facturas de proveedor'),
        ('purchase', 'Orden de compra/servicio')
    ], string="Tipo de origen")
    amount = fields.Float('Monto a pagar', required=True)
    default_amount = fields.Float('Monto ficticio',
                                  help="Sirve para evitar generar una orden de "
                                       "pago con monto mayor al del documento.")
    default_date = fields.Date('Fecha ficticia', help="Sirve para evitar generar una orden de pago "
                                                      "con fecha menor a la del documento.")

    type_egress = fields.Selection([
        ('cash', 'Pagos varios'),
        ('transfer', 'Transferencia')
    ], string='Forma de egreso', required=True, default='cash')
    origin = fields.Char('Origen', required=True)
    beneficiary = fields.Char('Beneficiario')
    # Campos para traer los diferentes documentos para la orden de pago
    invoice_ids = fields.Many2many('account.invoice', string='Facturas')
    purchase_order_id = fields.Many2one('purchase.order', 'Orden de compra/servicio')
    journal_id = fields.Many2one('account.journal', string="Banco de pago")
    comment = fields.Text('Notas y comentarios')
    company_id = fields.Many2one('res.company', 'Compañía')


class PayOrderWizard(models.TransientModel):
    _name = 'account.pay.order.wizard'
    _inherit = "account.pay.order.abstract"

    _description = _('Ventana para generar orden pago')


class PayOrder(models.Model):
    _name = 'account.pay.order'
    _inherit = ['mail.thread', 'account.pay.order.abstract']
    _description = _("Orden de pago")
    _order = "date desc"

    @api.multi
    def generate_payment(self):
        """
        Generamos pago desde orden de pago y llenamos con los datos de la misma
        luego redirigimos al formulario creado
        :return:
        """
        new_voucher = self.env['account.voucher'].with_context({'voucher_type': 'purchase'})._create_voucher_purchase(
            self)
        action = self.env.ref('eliterp_treasury.action_voucher_purchase')
        result = action.read()[0]
        res = self.env.ref('eliterp_treasury.view_form_voucher_purchase', False)
        result['views'] = [(res and res.id or False, 'form')]
        result['res_id'] = new_voucher.id
        return result

    @api.multi
    def unlink(self):
        """
        Al eliminar verificar qué no esten diferentes de borrador
        :return:
        """
        for pay in self:
            if pay.state != 'draft':
                raise ValidationError(_("No se puede eliminar una Orden de pago diferente de borrador."))
        return super(PayOrder, self).unlink()

    @api.model
    def create(self, vals):
        """
        Al crear colocamos la secuencia del documento (Orden de pago) por compañía
        :param vals:
        :return:
        """
        result = super(PayOrder, self).create(vals)
        new_name = self.env['ir.sequence'].with_context(force_company=result.company_id.id).next_by_code('pay.order')
        if not new_name:
            raise ValidationError(_("No ha creado secuencia con código 'pay.order' para %s.") % result.company_id.name)
        result.name = new_name
        return result

    name = fields.Char('Referencia de orden', index=True)
    date = fields.Date(track_visibility='onchange')
    amount = fields.Float(track_visibility='onchange')
    # Dependiendo del origen (Ej. Requerimientos de pago)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('paid', 'Pagado'),
        ('cancel', 'Anulado'),
    ], default='draft', string="Estado", readonly=True, track_visibility='onchange')
    beneficiary = fields.Char(track_visibility='onchange')
    # Formas de pago
    type_egress = fields.Selection(track_visibility='onchange')
    voucher_id = fields.Many2one('account.voucher', string='Comprobante de egreso', readonly=True)
    comment = fields.Text(track_visibility='onchange')


class AccountVoucher(models.Model):
    _inherit = 'account.voucher'

    @api.multi
    def name_get(self):
        """
        Cambiamos nombres de registros a mostrar
        :return:
        """
        res = []
        for data in self:
            if data.pay_order_id:
                res.append((data.id, "%s [%s]" % (data.name, data.pay_order_id.name)))
            else:
                res.append((data.id, "%s" % data.name or 'Nuevo comprobante'))
        return res

    @api.multi
    @api.returns('self')
    def _create_voucher_purchase(self, record):
        """
        Creamos un nuevo voucher a partir de Orden de pago
        :param record:
        :return: self
        """
        values = {}
        # Datos por defecto para todos los origines de pago (Son obligatorios)
        values['bank_date'] = record.date
        values['voucher_type'] = 'purchase'
        values['pay_order_id'] = record.id
        values['amount_cancel'] = record.amount
        values['type_egress'] = record.type_egress
        values['bank_journal_id'] = record.journal_id.id if record.journal_id else False
        voucher = self.create(values)
        voucher._onchange_pay_order_id()  # Al cambiar realizar transacciones dependiendo del tipo
        return voucher

    def _get_concept(self, invoices):
        """
        Concepto para facturas (Puede haber varias)
        :param invoices:
        :return:
        """
        if len(invoices) > 1:
            references = ', '.join(invoice.reference for invoice in invoices)
            concept = "Pago de facturas: %s" % references
        else:
            concept = "Pago de factura %s" % invoices[0].reference
        return concept

    @api.multi
    def data_invoice_purchase(self):
        """
        Cargamos la información de las facturas
        :return:
        """
        invoice = self.pay_order_id.invoice_ids[0]
        beneficiary = invoice.partner_id.name
        partner_id = invoice.partner_id.id
        list_accounts = []
        list_accounts.append([0, 0, {'account_id': invoice.partner_id.property_account_payable_id.id,
                                     'amount': self.amount_cancel,
                                     }])
        list_invoices = []
        for invoice in self.pay_order_id.invoice_ids:
            list_invoices.append([0, 0, {
                'invoice_id': invoice.id
            }])
        return self.update({
            'in_invoice_line': list_invoices,
            'account_line': list_accounts,
            'beneficiary': beneficiary,
            'partner_id': partner_id,
            'reference': self._get_concept(self.pay_order_id.invoice_ids)
        })

    @api.onchange('pay_order_id')
    def _onchange_pay_order_id(self):
        """
        Al cambiar la Orden de pago cargamos la data por defecto
        """
        if self.type_pay_order == 'invoice':
            self.data_invoice_purchase()
            self._set_amount(self.in_invoice_line, self.amount_cancel)

    def _update_type(self, move_id=None):
        """
        Creamos líneas dependiendo del tipo de origen, este método querda abierto para otras
        aplicaciones
        :param journal:
        :return:
        """
        self.pay_order_id.update({
            'voucher_id': self.id,
            'state': 'paid'
        })
        # TODO: Factura
        if self.type_pay_order == 'invoice':
            account_partner = self.partner_id.property_account_payable_id
            if len(self.in_invoice_line) > 1:
                for line_invoice in self.in_invoice_line:
                    line_move_voucher = move_id.line_ids.filtered(
                        lambda x: x.account_id == account_partner and x.invoice_id.id == line_invoice.invoice_id.id)
                    line_move_invoice = line_invoice.invoice_id.move_id.line_ids.filtered(
                        lambda x: x.account_id == account_partner)
                    (line_move_invoice + line_move_voucher).reconcile()

            else:
                line_move_voucher = move_id.line_ids.filtered(lambda x: x.account_id == account_partner)
                for line_invoice in self.in_invoice_line:
                    line_move_invoice = line_invoice.invoice_id.move_id.line_ids.filtered(
                        lambda x: x.account_id == account_partner)
                    (line_move_invoice + line_move_voucher).reconcile()

    def _check_pay_order_id(self):
        # TODO: Verificar mejor método
        new_object = self.search([
            ('pay_order_id', '=', self.pay_order_id.id),
            ('state', '=', 'posted')
        ])
        if new_object:
            raise ValidationError("Ya existe una Orden de pago contabilizada de la misma.")
        else:
            return

    @api.constrains('company_id', 'currency_id')
    def _check_company_id(self):
        """
        MM
        :return:
        """
        pass

    pay_order_id = fields.Many2one('account.pay.order', string='Orden de pago', readonly=True,
                                   domain=[('state', '=', 'draft')],
                                   states={'draft': [('readonly', False)]})
    type_pay_order = fields.Selection(related='pay_order_id.type', string="Tipo de origen", store=True)
    company_id = fields.Many2one('res.company', 'Compañía', related=False,
                                 default=lambda self: self.env.user.company_id)

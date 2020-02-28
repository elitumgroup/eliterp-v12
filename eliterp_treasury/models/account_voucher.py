# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

TYPE_JOURNAL = {
    'purchase': 'Comprobante de egreso',
    'sale': 'Comprobante de ingreso'
}


class VoucherInvoiceLine(models.Model):
    _name = 'account.voucher.invoice.line'
    _order = 'residual asc'

    _description = _("Línea de factura en comprobante")

    invoice_id = fields.Many2one('account.invoice', 'Factura')
    currency_id = fields.Many2one('res.currency', related='invoice_id.currency_id', store=True, string="Moneda",
                                  related_sudo=False)
    name = fields.Char('No. Factura', related="invoice_id.reference")
    date_due = fields.Date('Fecha vencimiento', related='invoice_id.date_due', store=True)
    amount_total = fields.Monetary('Monto de factura', related='invoice_id.amount_total', store=True)
    residual = fields.Monetary('Monto adeudado', related='invoice_id.residual', store=True)
    amount_payable = fields.Float('Monto a cobrar/pagar')
    voucher_id = fields.Many2one('account.voucher', string='Comprobante', ondelete="cascade")


class CollectionLine(models.Model):
    _name = "account.collection.line"

    _description = _('Líneas de recaudación')

    @api.one
    @api.constrains('amount')
    def _check_amount(self):
        """
        Validamos monto sea mayor a 0
        """
        if self.amount <= 0:
            raise ValidationError("Monto no puede ser menor o igual a 0.")

    @api.one
    @api.constrains('date_due')
    def _check_date_due(self):
        """
        Verificamos la fechas
        """
        if self.date_due < self.date_issue:
            raise ValidationError('La fecha de vencimiento no puede ser menor a la de emisión de la recaudación.')

    @api.onchange('date_issue')
    def _onchange_date_issue(self):
        """
        Cambiamos fecha de vencimiento por la de emisión
        :return:
        """
        if self.date_issue:
            self.date_due = self.date_issue

    type_payment = fields.Selection([
        ('cash', 'Pagos varios'),
        ('deposit', 'Depósito'),
        ('transfer', 'Transferencia')
    ], string='Tipo de recaudación', required=True)
    account_id = fields.Many2one('account.account', string='Cuenta contable', required=True)
    amount = fields.Float('Monto', required=True)
    voucher_id = fields.Many2one('account.voucher', 'Comprobante de ingreso', ondelete="cascade")
    date_issue = fields.Date('Fecha de emisión', default=fields.Date.context_today, required=True)
    date_due = fields.Date('Fecha vencimiento', default=fields.Date.context_today, required=True)
    move_id = fields.Many2one('account.move', string='Asiento contable (Interno)', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía',
                                 related='voucher_id.company_id', store=True, readonly=True, related_sudo=False)


class AccountLine(models.Model):
    _name = 'account.account.line'

    _description = _("Línea de cuenta contable")

    account_id = fields.Many2one('account.account', required=True, string="Cuenta contable")
    amount = fields.Float('Monto', required=True)
    voucher_id = fields.Many2one('account.voucher', string='Comprobante', ondelete="cascade")
    company_id = fields.Many2one('res.company', string='Compañía',
                                 related='voucher_id.company_id', store=True, readonly=True, related_sudo=False)


class Voucher(models.Model):
    _inherit = "account.voucher"

    @api.multi
    def print_voucher(self):
        """Imprimimos comprobante"""
        self.ensure_one()
        if self.voucher_type == 'purchase':
            return self.env.ref('eliterp_treasury.action_report_voucher').report_action(self)
        else:
            return self.env.ref('eliterp_treasury.action_report_voucher_sale').report_action(self)

    @api.model
    def _default_journal(self):
        """
        MM: Se cambio el método
        :return:
        """
        voucher_type = self._context.get('voucher_type', 'sale')
        company_id = self._context.get('company_id', self.env.user.company_id.id)
        type = TYPE_JOURNAL[voucher_type]
        domain = [
            ('name', '=', type),
            ('company_id', '=', company_id)
        ]
        return self.env['account.journal'].search(domain, limit=1)

    @api.onchange('partner_id', 'pay_now')
    def onchange_partner_id(self):
        """
        MM: Se eliminó funciones del método
        """
        return {}

    def _set_amount(self, invoices, total):
        """
        Dividimos monto para facturas
        :param total:
        :return:
        """
        for invoice in invoices:
            if total == 0.00:
                continue
            if invoice.residual <= total:
                invoice.update({
                    'amount_payable': invoice.residual
                })
                total = total - invoice.residual
            else:
                invoice.update({
                    'amount_payable': total
                })
                total = 0.00

    def _create_move_line_sale(self, name, journal_id, credit, debit, account_credit, account_debit, balance):
        """
        Creamos movmientos para comprobante de ingreso
        :param name:
        :param move_id:
        :param credit:
        :param debit:
        :param account_credit:
        :param account_debit:
        :param balance:
        :return: object
        """
        move = self.env['account.move'].create({
            'journal_id': journal_id.id,
            'date': self.date,
            'ref': self.reference if not self.advance else False
        })
        if not self.advance:
            if balance > 0:
                self.env['account.move.line'].with_context(check_move_validity=False).create({
                    'name': name,
                    'journal_id': journal_id.id,
                    'partner_id': self.partner_id.id,
                    'account_id': account_debit,
                    'move_id': move.id,
                    'credit': balance,
                    'debit': 0.0,
                    'date': move.date,
                })
            self.env['account.move.line'].with_context(check_move_validity=False).create({
                'name': self.partner_id.name,
                'journal_id': journal_id.id,
                'partner_id': self.partner_id.id,
                'account_id': account_credit,
                'move_id': move.id,
                'credit': (credit - balance) if balance > 0 else credit,
                'debit': 0.0,
                'date': move.date,
            })
            self.env['account.move.line'].with_context(check_move_validity=True).create({
                'name': name,
                'journal_id': journal_id.id,
                'partner_id': self.partner_id.id,
                'account_id': account_debit,
                'move_id': move.id,
                'credit': 0.0,
                'debit': debit,
                'date': move.date,
            })
        else:
            self.env['account.move.line'].with_context(check_move_validity=False).create({
                'name': self.partner_id.name,
                'journal_id': journal_id.id,
                'partner_id': self.partner_id.id,
                'account_id': self.advance_account_id.id,
                'move_id': move.id,
                'credit': credit,
                'debit': 0.0,
                'date': move.date,
            })
            self.env['account.move.line'].with_context(check_move_validity=True).create({
                'name': _("Anticipo: ") + "%s" % name,
                'journal_id': move.journal_id.id,
                'partner_id': self.partner_id.id,
                'account_id': account_debit,
                'move_id': move.id,
                'credit': 0.0,
                'debit': debit,
                'date': move.date,
            })
        return move

    def _create_move_sale(self, journal_id):
        """
        Creamos movimientos de comprobante de ingreso
        :param journal_id:
        :return list:
        """
        moves_voucher = []
        balance = self.amount_collection - self.amount_invoice
        for payment in self.collection_line:
            move_id = self._create_move_line_sale(
                self.reference,
                journal_id,
                payment.amount,
                payment.amount,
                self.partner_id.property_account_receivable_id.id,
                payment.account_id.id,
                balance,
            )
            move_id.with_context(my_moves=True, internal_voucher=True).post()
            payment.write({'move_id': move_id.id})
            if not self.advance:
                line_move_voucher = move_id.line_ids.filtered(
                    lambda x: x.account_id == self.partner_id.property_account_receivable_id)
                for line in self.out_invoice_line:
                    line_move_invoice = line.invoice_id.move_id.line_ids.filtered(
                        lambda x: x.account_id == self.partner_id.property_account_receivable_id)
                    (line_move_voucher + line_move_invoice).reconcile()
                    moves_voucher.append(move_id)
        return moves_voucher

    def _get_move_name(self):
        """
        Obtenemos el nombre del asiento según la compañía y el egreso
        """
        prefix = "CE-%s-" % self.company_id.name[:3]
        if self.type_egress == 'cash':
            year = str(self.date.year)
        else:
            year = str(self.bank_date.year)
            code = self.bank_journal_id.code
        if self.type_egress == 'cash':
            sequence = self.env['ir.sequence'].with_context(force_company=self.company_id.id).next_by_code(
                'account.voucher.purchase.cash')
            if not sequence:
                raise ValidationError(
                    _("No existe secuencia 'account.voucher.purchase.cash' para compañía %s.") % self.company_id.name)
            move_name = prefix + "VAR-" + year + "-" + sequence
        else:
            bank_sequence = self.bank_journal_id.sequence_id.next_by_id()
            move_name = prefix + code + "-" + year + "-" + bank_sequence
        return move_name

    @api.multi
    def post_voucher(self):
        """
        Contabilizamos el voucher
        :return:
        """
        journal_id = self.journal_id
        if not self.journal_id:
            raise ValidationError(
                "Debe definir diario (%s) para compañía %s." % (TYPE_JOURNAL[self.voucher_type], self.company_id.name))
        if self.voucher_type == 'sale':
            new_name = journal_id.sequence_id.next_by_id()
            moves_voucher = self._create_move_sale(journal_id)
            for move in moves_voucher:
                move.write({'ref': new_name})
            return self.write({
                'state': 'posted',
                'name': new_name
            })
        else:
            move_id = self.env['account.move'].create({
                'journal_id': journal_id.id,
                'project_id': self.project_id.id,
                'company_division_id': self.company_division_id.id,
                'date': self.date,
                'ref': self.reference
            })
            # Línea de débito (Banco o efectivo)
            self.env['account.move.line'].with_context(check_move_validity=False).create({
                'name': self.reference if self.type_egress == 'cash' else '{0} - [{1}]'.format(
                    self.bank_journal_id.name,
                    self.reference),
                'move_id': move_id.id,
                'journal_id': journal_id.id,
                'partner_id': self.partner_id.id if self.partner_id else False,
                'account_id': self.account_id.id if self.account_id else self.bank_journal_id.default_debit_account_id.id,
                'move_id': move_id.id,
                'debit': 0.0,
                'credit': self.amount_cancel,
                'date': self.date
            })
            number_accounts = len(self.account_line)
            number_invoices = len(self.in_invoice_line)
            if number_invoices > 1:
                account_payable = self.partner_id.property_account_payable_id.id
                # Cuentas qué no son de proveedor
                for line in self.account_line.filtered(lambda x: not x.account_id.id == account_payable):
                    self.env['account.move.line'].with_context(check_move_validity=False).create({
                        'name': line.account_id.name,
                        'journal_id': move_id.journal_id.id,
                        'partner_id': False,
                        'account_id': line.account_id.id,
                        'move_id': move_id.id,
                        'credit': 0.0,
                        'debit': line.amount,
                        'date': self.date,
                        'analytic_account_id': self.account_analytic_id.id
                        # Soló en está línea le mandamos centro de costo
                    })
                for line in self.in_invoice_line:
                    number_invoices -= 1
                    if number_invoices == 0:
                        self.env['account.move.line'].with_context(check_move_validity=True).create({
                            'name': line.name,
                            'journal_id': move_id.journal_id.id,
                            'partner_id': self.partner_id.id,
                            'account_id': account_payable,
                            'move_id': move_id.id,
                            'credit': 0.0,
                            'debit': line.amount_payable,
                            'date': self.date,
                            'invoice_id': line.invoice_id.id
                        })
                    else:
                        self.env['account.move.line'].with_context(check_move_validity=False).create({
                            'name': line.name,
                            'journal_id': move_id.journal_id.id,
                            'partner_id': self.partner_id.id,
                            'account_id': account_payable,
                            'move_id': move_id.id,
                            'credit': 0.0,
                            'debit': line.amount_payable,
                            'date': self.date,
                            'invoice_id': line.invoice_id.id
                        })
            else:
                # Para una sola factura o transacción
                for line in self.account_line:
                    number_accounts -= 1
                    if number_accounts == 0:
                        self.env['account.move.line'].with_context(check_move_validity=True).create({
                            'name': line.account_id.name,
                            'journal_id': move_id.journal_id.id,
                            'partner_id': self.partner_id.id if self.partner_id else False,
                            'account_id': line.account_id.id,
                            'move_id': move_id.id,
                            'credit': 0.0,
                            'debit': line.amount,
                            'date': self.date,
                            'analytic_account_id': self.account_analytic_id.id
                        })
                    else:
                        self.env['account.move.line'].with_context(check_move_validity=False).create({
                            'name': line.account_id.name,
                            'journal_id': move_id.journal_id.id,
                            'partner_id': self.partner_id.id if self.partner_id else False,
                            'account_id': line.account_id.id,
                            'move_id': move_id.id,
                            'credit': 0.0,
                            'debit': line.amount,
                            'date': self.date,
                            'analytic_account_id': self.account_analytic_id.id
                        })
            self._update_type(move_id)  # Dependiendo del tipo hacemos las transacciones de asientos contables
            move_id.with_context(my_moves=True, move_name=self._get_move_name()).post()
            return self.write({
                'state': 'posted',
                'name': move_id.name,
                'move_id': move_id.id
            })

    @api.depends('collection_line')
    def _compute_total_collection(self):
        """
        Calculamos el total de líneas de recaudación
        :return:
        """
        for voucher in self:
            total = 0.00
            for line in voucher.collection_line:
                total += line.amount
            voucher.amount_collection = total

    @api.depends('out_invoice_line')
    def _compute_total_invoice(self):
        """
        Calculamos el total de facturas de cliente
        :return:
        """
        for voucher in self:
            total = 0.00
            for line in voucher.out_invoice_line:
                total += line.residual
            voucher.amount_invoice = total

    @api.multi
    def load_invoices(self):
        """
        Cargamos las facturas de ventas del cliente
        :return:
        """
        self.out_invoice_line.unlink()  # Limpiamos líneas anteriores
        invoices = self.env['account.invoice'].search([
            ('partner_id', '=', self.partner_id.id),
            ('state', '=', 'open')
        ])
        list_invoices = []
        for invoice in invoices:
            list_invoices.append([0, 0, {
                'invoice_id': invoice.id
            }])
        return self.update({'out_invoice_line': list_invoices})

    @api.multi
    def load_amount(self):
        """
        Cargamos montos de recaudaciones si existen líneas
        :return:
        """
        if not self.collection_line:
            raise UserError(_("No tiene líneas de recaudación creadas."))
        self._set_amount(self.out_invoice_line, self.amount_collection)

    # Campos para comprobantes de ingreso
    out_invoice_line = fields.One2many('account.voucher.invoice.line',
                                       'voucher_id',
                                       string='Líneas de facturas',
                                       readonly=True,
                                       states={'draft': [('readonly', False)]})
    collection_line = fields.One2many('account.collection.line',
                                      'voucher_id',
                                      string='Líneas de recaudación',
                                      readonly=True,
                                      states={'draft': [('readonly', False)]})
    amount_collection = fields.Monetary('Total de recaudación', compute='_compute_total_collection',
                                        track_visibility='onchange')
    amount_invoice = fields.Monetary('Total de facturas', compute='_compute_total_invoice')
    advance = fields.Boolean('Es anticipo?', default=False, readonly=True, states={'draft': [('readonly', False)]})

    advance_account_id = fields.Many2one('account.account', string="Cuenta de anticipo", readonly=True,
                                         states={'draft': [('readonly', False)]},
                                         help="Cuenta para crear línea de anticipo por defecto trae la del cliente.")
    # Otros campos para comprobantes
    in_invoice_line = fields.One2many('account.voucher.invoice.line',
                                      'voucher_id',
                                      string='Líneas de facturas',
                                      readonly=True,
                                      states={'draft': [('readonly', False)]})
    account_line = fields.One2many('account.account.line', 'voucher_id', string='Líneas de cuenta', readonly=True,
                                   states={'draft': [('readonly', False)]})
    journal_id = fields.Many2one('account.journal', 'Diario', required=False, readonly=True,
                                 default=_default_journal)  # CM
    bank_journal_id = fields.Many2one('account.journal', 'Banco',
                                      track_visibility='onchange', readonly=True,
                                      states={'draft': [('readonly', False)]})
    type_egress = fields.Selection([
        ('cash', 'Pagos varios'),
        ('transfer', 'Transferencia'),
    ], string='Forma de egreso', track_visibility='onchange', readonly=True,
        states={'draft': [('readonly', False)]})
    beneficiary = fields.Char('Beneficiario', readonly=True, states={'draft': [('readonly', False)]},
                              track_visibility='onchange')
    account_id = fields.Many2one('account.account', string='Cuenta de efectivo',
                                 required=False)  # CM Está cuenta se utilizará para efectivo
    transfer_code = fields.Char('Código de transferencia')
    date = fields.Date("Fecha de comprobante", readonly=True,
                       index=True, states={'draft': [('readonly', False)]},
                       copy=False, default=fields.Date.context_today)  # CM
    reference = fields.Char(string='Concepto', readonly=True, states={'draft': [('readonly', False)]},
                            help="Colocar alguna referencia (concepto) del comprobante.", copy=False)  # CM
    bank_date = fields.Date('Fecha de pago', readonly=True, states={'draft': [('readonly', False)]},
                            track_visibility='onchange')
    amount_cancel = fields.Float('Monto a cancelar', readonly=True,
                                 states={'draft': [('readonly', False)]},
                                 track_visibility='onchange')

    # Análisis de gastos
    @api.model
    def _default_company_division(self):
        """
        Defecto división empresarial
        :return:
        """
        company = self.env.user.company_id.id
        company_division_ids = self.env['account.company.division'].search([('company_id', '=', company)], limit=1)
        return company_division_ids

    company_division_id = fields.Many2one('account.company.division', string='División', readonly=True,
                                          states={'draft': [('readonly', False)]}, track_visibility='onchange',
                                          default=_default_company_division)
    project_id = fields.Many2one('account.project', string='Proyecto', readonly=True,
                                 states={'draft': [('readonly', False)]}, track_visibility='onchange')
    account_analytic_id = fields.Many2one('account.analytic.account', 'Centro de costo', readonly=True,
                                          states={'draft': [('readonly', False)]}, track_visibility='onchange')
    move_id = fields.Many2one('account.move', string='Asiento contable', readonly=True)
    _sql_constraints = [
        ('transfer_code_unique', 'unique (journal_id, transfer_code, state)',
         'El código de transferencia debe ser único por cuenta bancaria.')
    ]

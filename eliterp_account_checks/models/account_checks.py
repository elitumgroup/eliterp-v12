# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class Journal(models.Model):
    _inherit = 'account.journal'

    @api.one
    def _create_check_sequence(self):
        """
        MM: Agregamos el padding para la secuencia
        :return:
        """
        self.check_sequence_id = self.env['ir.sequence'].sudo().create({
            'name': self.name + _(": Secuencia del cheque"),
            'number_next_actual': self.start_check,
            'implementation': 'no_gap',
            'padding': self.check_padding,
            'number_increment': 1,
            'company_id': self.company_id.id,
        })

    start_check = fields.Integer('Inicio de cheques', default=1, copy=False)
    check_padding = fields.Integer('Dígitos', default=6, help="Cantidad de dígitos en el talonario de la chequera.")
    # TODO: Revisar qué al cambiar no tengamos cheques realizados


class Checks(models.Model):
    _name = "account.checks"
    _inherit = ['mail.thread']
    _description = "Cheques"
    _order = "check_date desc"

    @api.depends('amount')
    def _compute_amount_letters(self):
        """
        Calculamos el monto en letras del cheque
        :return:
        """
        for check in self:
            text = self.env['res.functions']._get_amount_letters(check.amount)
            check.amount_in_letters = text.upper()

    @api.constrains('name')
    def _check_name(self):
        """
        Validamos número sea correcto y no exista otro igual (Cualquier estado)
        # TODO: Por banco de cliente verificar su duplicidad
        """
        if self.type == 'issued':
            start = self.bank_journal_id.start_check
            if int(self.name) < int(start):
                raise ValidationError(
                    "Cheque %s menor al configurado en cuenta bancaria (%s)." % (self.name, start))
            check = self.env['account.checks'].search([
                ('bank_journal_id', '=', self.bank_journal_id.id),
                ('name', '=', self.name)
            ])
            if check:
                raise ValidationError("Ya existe un cheque "
                                      "registrado para la cuenta bancaria %s con ese número (%s)." % (
                                          self.bank_journal_id.name, self.name))

    recipient = fields.Char('Girador/Beneficiario', required=True)
    partner_id = fields.Many2one('res.partner', string='Cliente/Proveedor')
    bank_id = fields.Many2one('res.bank', 'Banco de cliente')
    account_number = fields.Char('No. Cuenta')
    account_id = fields.Many2one('account.account', string='Cuenta de recaudo')
    amount = fields.Float('Monto', required=True, track_visibility='onchange')
    amount_in_letters = fields.Char('Monto en letras', compute='_compute_amount_letters', readonly=True)
    date = fields.Date('Fecha Recepción/Emisión', required=True, track_visibility='onchange')
    check_date = fields.Date('Fecha de cheque', required=True, track_visibility='onchange')
    type = fields.Selection([('receipts', 'Recibidos'), ('issued', 'Emitidos')], string='Tipo de cheque', required=True)
    check_type = fields.Selection([('current', 'Corriente'), ('to_date', 'A la fecha')], string='Tipo de cheque'
                                  , default='current')
    state = fields.Selection([
        ('received', 'Recibido'),
        ('deposited', 'Depositado'),
        ('issued', 'Emitido'),
        ('delivered', 'Entregado'),
        ('protested', 'Anulado')
    ], string='Estado', track_visibility='onchange')
    voucher_id = fields.Many2one('account.voucher', string='Pago/Cobro')
    company_id = fields.Many2one(string="Compañía", related="voucher_id.company_id", store=True)
    bank_journal_id = fields.Many2one(string="Banco de emisión", related="voucher_id.bank_journal_id", store=True)
    name = fields.Char('No. Cheque', required=True)

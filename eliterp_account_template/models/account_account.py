# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons import decimal_precision as dp

SRI = [
    ('i', 'IVA diferente de 0%'),
    ('i0', 'IVA 0%'),
    ('ni', 'No objeto a IVA'),
    ('rib', 'Retención de IVA (Bienes)'),
    ('ris', 'Retención de IVA (Servicios)'),
    ('rir', 'Retención impuesto a la renta'),
    ('nrir', 'No sujetos a RIR'),
    ('ia', 'Impuesto aduana'),
    ('sb', 'Super de bancos'),
    ('ice', 'ICE'),
    ('c', 'Compensaciones'),
    ('o', 'Otro')
]


class AccountType(models.Model):
    _inherit = 'account.account.type'

    type = fields.Selection(selection_add=[('view', 'Vista')])


class AccountTemplate(models.Model):
    _inherit = 'account.account.template'

    parent_id = fields.Many2one('account.account.template', 'Cuenta padre', ondelete="set null")


class Account(models.Model):
    _inherit = 'account.account'
    _parent_name = "parent_id"
    _parent_store = True
    _order = 'parent_path'

    def _get_beginning_balance(self, start_date):
        """
        Obtenemos el saldo inicial de una cuenta contable
        :param account:
        :param start_date:
        :param end_date:
        :return: float
        """
        move_lines = self.env['account.move.line'].search([
            ('account_id', '=', self.id),
            ('date', '<', start_date)
        ])
        balance = 0.00
        for line in move_lines:
            type = (self.code.split("."))[0]
            balance += self._get_balance_nature_account(type, line.debit, line.credit)
        return balance

    @staticmethod
    def _get_balance_nature_account(type, debit, credit):
        """
        Monto de balance según naturaleza de cuenta contable
        :param type:
        :param debit:
        :param credit:
        :return balance:
        """
        balance = debit - credit
        if type in ['1', '5']:
            if debit < credit:
                if balance > 0:
                    balance = -1 * round(debit - credit, 2)
        if type in ['2', '3', '4']:
            if debit < credit:
                if balance < 0:
                    balance = -1 * round(debit - credit, 2)
            if debit > credit:
                if balance > 0:
                    balance = -1 * round(debit - credit, 2)
        return balance

    @api.multi
    def _account_balance(self, accounts, date_from=False, date_to=False):
        """
        Balance de cuenta contable
        :param accounts:
        :param date_from:
        :param date_to:
        :return:
        """
        debit = 0.00
        credit = 0.00
        balance = 0.00
        arg = []
        arg.append(('account_id', 'in', accounts.ids))
        if date_from and date_to:  # TODO: Si existen las fechas se las filtra por las mismas (Dejamos esto para futuro reportes)
            arg.append(('date', '>=', date_from))
            arg.append(('date', '<=', date_to))
        account_lines = self.env['account.move.line'].search(arg)
        if not account_lines:
            return debit, credit, balance
        for line in account_lines:
            credit += line.credit
            debit += line.debit
            balance += self._get_balance_nature_account(
                line.account_id.code.split(".")[0],
                line.debit, line.credit
            )
        return debit, credit, balance

    @api.multi
    @api.depends('accounting_lines', 'accounting_lines.debit', 'accounting_lines.credit')
    def _compute_balance(self):
        """
        Mostramos el débito, crédito y balance de cada cuenta,
        las cuenta padres suman los registros de las cuentas hijas.
        :return:
        """
        for account in self:
            # TODO: Revisar si colocamos contexto para no mostrar cuentas padres en transacciones
            # with_context({'show_parent_account': True})
            childs = self.search([('id', 'child_of', [account.id])])
            data = list(self._account_balance(childs))
            account.debit = data[0]
            account.credit = data[1]
            account.balance = data[2]

    @api.multi
    def write(self, vals):
        """
        Revisar qué al cambiar el tipo a vista no tenga línea de movimiento
        :param vals:
        :return:
        """
        if ('user_type_id' in vals and self.user_type_id.id != vals['user_type_id']):
            if self.env['account.move.line'].search([('account_id', 'in', self.ids)], limit=1):
                raise UserError(
                    _(
                        "Está cuenta ya contiene apuntes, por lo tanto, no puede cambiar a tipo vista. (código: %s)" % self.code))
        return super(Account, self).write(vals)

    @api.constrains('parent_id')
    def _check_parent_id(self):
        """
        Verificar cuenta padre
        :return:
        """
        if not self._check_recursion():
            raise ValidationError(_('No puede crear cuentas padres recursivas.'))
        return True

    accounting_lines = fields.One2many('account.move.line', 'account_id', string='Líneas contables')
    parent_id = fields.Many2one('account.account', 'Cuenta padre', ondelete="set null")
    child_ids = fields.One2many('account.account', 'parent_id', string='Cuentas hijas')
    credit = fields.Float(string='Crédito', compute='_compute_balance', digits=dp.get_precision('Account'))
    debit = fields.Float(string='Débito', compute='_compute_balance', digits=dp.get_precision('Account'))
    balance = fields.Float(string='Balance', compute='_compute_balance', digits=dp.get_precision('Account'))
    parent_path = fields.Char(index=True)


class TaxGroup(models.Model):
    _inherit = 'account.tax.group'

    tax_reference = fields.Selection(SRI, string='Referencia de impuesto', default='i', required=True,
                                     help="Campo necesario para declaraciones del SRI.")


class TaxTemplate(models.Model):
    _inherit = 'account.tax.template'

    code = fields.Char('Código de retención')
    tax_type = fields.Selection([
        ('iva', 'IVA'),
        ('retention', 'Retención')
    ], string='Tipo de impuesto', default='iva', required=True)
    retention_type = fields.Selection([
        ('rent', 'Renta'),
        ('iva', 'IVA')
    ], string='Tipo de retención', default='rent')

    _sql_constraints = [
        ('code_unique', 'unique (code,type_tax_use,company_id)',
         _("El código de retención debe ser único por tipo de impuesto."))
    ]


class Tax(models.Model):
    _inherit = 'account.tax'

    @api.multi
    def name_get(self):
        """
        Cambiamos los nombres a mostrar de los registros
        :return:
        """
        result = []
        for data in self:
            if data.tax_type == 'retention' and data.code:
                result.append((data.id, "%s [%s]" % (data.code, data.name)))
            else:
                result.append((data.id, "%s" % (data.name)))
        return result

    code = fields.Char('Código de retención')
    tax_type = fields.Selection([
        ('iva', 'IVA'),
        ('retention', 'Retención')
    ], string='Tipo de impuesto', default='iva', required=True)
    retention_type = fields.Selection([
        ('rent', 'Renta'),
        ('iva', 'IVA')
    ], string='Tipo de retención', default='rent')

    _sql_constraints = [
        ('code_unique', 'unique (code, type_tax_use)', _("El código de retención debe ser único por tipo de impuesto."))
    ]

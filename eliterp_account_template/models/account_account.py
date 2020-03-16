# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons import decimal_precision as dp
from odoo.osv import expression

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
        debit = 0.00
        credit = 0.00
        move_lines = self.env['account.move.line'].search([
            ('account_id', '=', self.id),
            ('date', '<', start_date)
        ])
        for line in move_lines:
            credit += line.credit
            debit += line.debit
        type = (self.code.split("."))[0]
        return self._get_balance_nature_account(type, debit, credit)

    @staticmethod
    def _get_balance_nature_account(type, debit, credit):
        """
        Monto de balance según naturaleza de cuenta contable
        http://enrique-asuntoscontables.blogspot.com/2011/09/clasificacion-general-de-las-cuentas.html
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
        if type in ['2', '3', '4', '6', '7']:
            if debit < credit:
                if balance < 0:
                    balance = -1 * round(debit - credit, 2)
            if debit > credit:
                if balance > 0:
                    balance = -1 * round(debit - credit, 2)
        return balance

    @api.multi
    def _account_balance(self, account, accounts, date_from=False, date_to=False):
        """
        Balance de cuenta contable
        https://www.contabilidae.com/deudor-y-acreedor/
        :param accounts:
        :param date_from:
        :param date_to:
        :return:
        """
        debit = 0.00
        credit = 0.00
        balance = 0.00
        arg = [('account_id', 'in', accounts.ids)]
        if date_from and date_to:
            arg.append(('date', '>=', date_from))
            arg.append(('date', '<=', date_to))
        account_lines = self.env['account.move.line'].search(arg)
        if not account_lines:
            return debit, credit, balance
        for line in account_lines:
            credit += line.credit
            debit += line.debit
        balance = self._get_balance_nature_account(account.code.split(".")[0], debit, credit)
        return debit, credit, balance

    @api.multi
    @api.depends('accounting_lines', 'accounting_lines.debit', 'accounting_lines.credit')
    def _compute_balance(self):
        """
        Mostramos el débito, crédito y balance de cada cuenta,
        las cuenta padres suman los registros de las cuentas hijas.
        :return:
        """
        pass

    @api.multi
    def write(self, vals):
        """
        Revisar qué al cambiar el tipo a vista no tenga línea de movimiento
        :param vals:
        :return:
        """
        if 'user_type_id' in vals and self.user_type_id.id != vals['user_type_id']:
            user_type_id = self.env['account.account.type'].browse(vals['user_type_id'])
            # Soló cuando queremos cambiar a tipo vista verificamos no tenga movimientos
            if user_type_id.type == 'view':
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

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        """
        MM: Buscar soló tipo vistas
        :param name:
        :param args:
        :param operator:
        :param limit:
        :param name_get_uid:
        :return:
        """
        args = args or []
        domain = []
        if not self._context.get('show_parent_account', False):
            args += [('internal_type', '!=', 'view')]
        if name:
            domain = ['|', ('code', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        account_ids = self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)
        return self.browse(account_ids).name_get()

    accounting_lines = fields.One2many('account.move.line', 'account_id', string='Líneas contables')
    parent_id = fields.Many2one('account.account', 'Cuenta padre', ondelete="set null")
    child_ids = fields.One2many('account.account', 'parent_id', string='Cuentas hijas')
    credit = fields.Float(string='Crédito', compute='_compute_balance', digits=dp.get_precision('Account'))
    debit = fields.Float(string='Débito', compute='_compute_balance', digits=dp.get_precision('Account'))
    balance = fields.Float(string='Saldo en cuenta', compute='_compute_balance', digits=dp.get_precision('Account'))
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
                result.append((data.id, "%s" % data.name))
        return result

    @api.multi
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = default or {}
        if self.code:
            default['code'] = _("%s (copia)") % self.code
        return super(Tax, self).copy(default=default)

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        """
        ME: Agregamos a la búsqueda el código de retención
        :param name:
        :param args:
        :param operator:
        :param limit:
        :param name_get_uid:
        :return:
        """
        args = args or []
        if name:
            args = [('code', '=', name)]
        tax_ids = self._search(args, limit=limit, access_rights_uid=name_get_uid)
        if not tax_ids:
            return super(Tax, self)._name_search(name, args=None, operator=operator, limit=limit,
                                                 name_get_uid=name_get_uid)
        return self.browse(tax_ids).name_get()

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
        ('code_unique', 'unique (code, type_tax_use, company_id)',
         _("El código de retención debe ser único por tipo de impuesto."))
    ]

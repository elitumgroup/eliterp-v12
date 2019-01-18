# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo import api, fields, models, tools, _
from datetime import date, datetime
from calendar import monthrange
import babel
from odoo.exceptions import RedirectWarning, ValidationError


class PeriodLine(models.Model):
    _name = 'account.period.line'

    _description = _("Líneas de período contable'")

    _order = "code desc"

    @api.one
    @api.depends('closing_date')
    def _compute_state(self):
        """
        Calculamos el estado de la línea de período contable
        :return:
        """
        self.state = self.closing_date > datetime.today().date()

    name = fields.Char('Referencia de período')
    code = fields.Integer('Código')
    start_date = fields.Date('Fecha inicio')
    closing_date = fields.Date('Fecha cierre')
    state = fields.Boolean('Estado', compute='_compute_state', store=True)
    period_id = fields.Many2one('account.fiscal.year', 'Año contable', ondelete="cascade")


class FiscalYear(models.Model):
    _inherit = 'account.fiscal.year'

    @api.multi
    def valid_period(self, date):
        """
        Realizamos validación de período con fecha dada
        :param date:
        :return:
        """
        if isinstance(date, str):  # Por si acaso venga como string
            date = datetime.strptime(date, "%Y-%m-%d")
        year_accounting = self.env['account.fiscal.year'].search([('name', '=', date.year)])
        if not year_accounting:
            raise UserError(_("No hay ningún período contable creado en el sistema."))
        period_id = year_accounting.period_lines.filtered(lambda x: x.code == date.month)
        if not period_id:
            raise UserError(_("No hay ninguna línea de período contable creada."))
        current_date = fields.Date.today()
        if current_date < period_id.start_date:
            raise UserError(_("La fecha está fuera del rango del período contable."))
        if current_date > period_id.closing_date:
            raise UserError(_("El período contable está cerrado, comuníquese con Contabilidad."))
        return True

    @api.multi
    def load_periods(self):
        """
        Cargamos meses del año contable para poder transaccionar en diferentes documentos
        :return:
        """
        period_lines = []
        for x in range(1, 13):
            start_date = date(int(self.name), x, 1)
            locale = self.env.context.get('lang') or 'en_US'
            name_month = tools.ustr(babel.dates.format_date(date=start_date, format='MMMM', locale=locale)).title()
            last_day = monthrange(self.name, x)[1]
            closing_date = date(int(self.name), x, last_day)
            period_lines.append([0, 0, {
                'code': x,
                'name': name_month + " del " + str(self.name),
                'start_date': start_date,
                'closing_date': closing_date
            }])
        return self.update({'period_lines': period_lines})

    @api.constrains('name')
    def _check_name(self):
        """
        Validamos año sea correcto
        :return:
        """
        if not (self.name >= 2010 and self.name <= 2100):
            raise ValidationError(_("Año contable incorrecto, fuera de rango válido."))

    name = fields.Integer(string='Año contable', required=True, size=4, default=date.today().year)  # CM
    period_lines = fields.One2many('account.period.line', 'period_id', string='Líneas de período contable')

    sql_constraints = [
        ('name_unique', 'unique (company_id, name)', _("El año debe ser único por compañía!"))
    ]


class Invoice(models.Model):
    _inherit = 'account.invoice'

    @api.one
    @api.depends('date_invoice')
    def _compute_period(self):
        """
        Obtenemos el período contable dependiendo de la  fecha del documento
        :return:
        """
        date = self.date_invoice
        period = self.env['account.fiscal.year'].search([('name', '=', date.year)])
        # Si no existe rederiguimos a crear un período contable
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
        Al crear validamos período contable con la fecha
        :param values:
        :return:
        """
        if 'date_invoice' not in values:
            values.update({'date_invoice': date.today().strftime("%Y-%m-%d")})
        self.env['account.fiscal.year'].valid_period(values['date_invoice'])
        return super(Invoice, self).create(values)

    date_invoice = fields.Date('Fecha de factura',
                               readonly=True, states={'draft': [('readonly', False)]}, index=True,
                               help="Keep empty to use the current date", default=fields.Date.context_today,
                               required=True)  # CM
    period_id = fields.Many2one('account.period.line', string='Período', store=True, readonly=True,
                                compute='_compute_period')

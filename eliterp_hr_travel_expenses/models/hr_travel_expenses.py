# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero


class TravelDestinations(models.Model):
    _name = 'hr.travel.destinations'

    _description = _('Destinos para viático')

    name = fields.Char('Nombre', required=True, index=True)
    company_id = fields.Many2one('res.company', string="Compañía", default=lambda self: self.env.user.company_id)


class TravelConcepts(models.Model):
    _name = 'hr.travel.concepts'

    _description = _('Conceptos de viático')

    @api.one
    @api.constrains('amount')
    def _check_amount(self):
        """
        Verificamos qué el valor sea mayor a 0
        :return:
        """
        if not self.amount > 0:
            raise ValidationError(_("El monto debe ser mayor a 0."))

    account_id = fields.Many2one('account.account', string="Cuenta de gasto", required=True)
    amount = fields.Float('Monto')
    name = fields.Char('Nombre', required=True, index=True)
    company_id = fields.Many2one('res.company', string="Compañía", default=lambda self: self.env.user.company_id)


class TravelConceptsLine(models.Model):
    _name = 'hr.travel.concepts.line'
    _order = 'amount_total desc'
    _description = _('Línea de conceptos de viático')

    @api.one
    @api.depends('daily_value', 'days', 'number_people')
    def _compute_amount_total(self):
        """
        Calculamos el monto total de la línea
        :return:
        """
        self.amount_total = round(float(self.daily_value * self.days * self.number_people), 2)

    travel_concepts_id = fields.Many2one('hr.travel.concepts', string="Concepto", required=True)
    travel_expenses_request_id = fields.Many2one('hr.travel.expenses.request', string="Solicitud de viático",
                                                 ondelete="cascade")
    daily_value = fields.Float('Monto diario', required=True)
    days = fields.Integer('Días', default=1, required=True)
    number_people = fields.Integer('No. personas', default=1)
    amount_total = fields.Float('Monto total', compute='_compute_amount_total')


class TravelExpensesRequest(models.Model):
    _name = 'hr.travel.expenses.request'
    _order = 'application_date desc'
    _description = _('Solicitud de viático')
    _inherit = ['mail.thread']

    @api.multi
    def unlink(self):
        """
        Revisar registros al eliminar
        :return:
        """
        for record in self:
            if record.state != 'draft':
                raise UserError("No se puede eliminar una solicitud de viático diferente a estado borrador.")
        return super(TravelExpensesRequest, self).unlink()

    @api.multi
    def print_request(self):
        """
        Imprimimos solicitud de viático
        :return:
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr_travel_expenses.action_report_travel_expenses_request').report_action(self)

    @api.one
    @api.depends('line_ids')
    def _compute_amount_total(self):
        """
        Calculamos el total de las líneas
        :return:
        """
        self.amount_total = sum(line.amount_total for line in self.line_ids)

    def _get_name(self):
        company = self.company_id
        sequence = self.env['ir.sequence'].with_context(force_company=company.id).next_by_code(
            'travel.expenses.request')
        if not sequence:
            raise UserError(
                _(
                    "No está definida la secuencia con código 'travel.expenses.request' para compañía: %s") % company.name)
        return sequence

    @api.model
    def create(self, values):
        """
        :param values:
        :return: object
        """
        res = super(TravelExpensesRequest, self).create(values)
        res.name = self._get_name()
        return res

    @api.multi
    def action_approve(self):
        """
        Aprobar solicitud
        :return:
        """
        self.write({
            'state': 'approve',
            'approval_user': self.env.uid
        })

    @api.multi
    def action_deny(self):
        self.write({'state': 'deny'})

    @api.multi
    def to_approve(self):
        """
        Solicitar aprobación
        :return:
        """
        if not self.line_ids:
            raise ValidationError(_("No tiene línea de conceptos creadas para solicitud."))
        self.write({
            'state': 'to_approve'
        })

    @api.constrains('return_date')
    def _check_return_date(self):
        """
        Verificamos la fecha de retorno con la de viaje
        :return:
        """
        if self.return_date < self.trip_date:
            raise ValidationError(_('La fecha de retorno no puede ser menor a la del viaje.'))

    name = fields.Char('No. Documento', copy=False, default='Nueva solicitud', index=True)
    application_date = fields.Date('Fecha de solicitud', default=fields.Date.context_today, required=True,
                                   readonly=True, states={'draft': [('readonly', False)]})
    trip_date = fields.Date('Fecha de viaje', default=fields.Date.context_today, required=True, readonly=True,
                            states={'draft': [('readonly', False)]})
    return_date = fields.Date('Fecha de retorno', default=fields.Date.context_today, required=True
                              , readonly=True, states={'draft': [('readonly', False)]})
    employee_id = fields.Many2one('hr.employee', string='Beneficiario', required=True, readonly=True,
                                  states={'draft': [('readonly', False)]})
    destination_id = fields.Many2one('hr.travel.destinations', string='Destino', required=True, readonly=True,
                                     states={'draft': [('readonly', False)]})
    company_division_id = fields.Many2one('account.company.division', string='División', readonly=True,
                                          states={'draft': [('readonly', False)]}, track_visibility='onchange')
    reason = fields.Char('Motivo de viaje', required=True, track_visibility='onchange')
    amount_total = fields.Float(compute='_compute_amount_total', string="Monto total", store=True)
    approval_user = fields.Many2one('res.users', 'Aprobado por')
    line_ids = fields.One2many('hr.travel.concepts.line', 'travel_expenses_request_id',
                               string='Línea de conceptos', readonly=True,
                               states={'draft': [('readonly', False)]})
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('to_approve', 'Por aprobar'),
        ('approve', 'Aprobado'),
        ('liquidated', 'Liquidado'),
        ('deny', 'Negado')
    ], "Estado", default='draft', track_visibility='onchange')
    company_id = fields.Many2one('res.company', string="Compañía", default=lambda self: self.env.user.company_id)

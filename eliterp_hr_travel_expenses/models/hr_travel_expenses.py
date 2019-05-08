# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
from operator import itemgetter
from itertools import groupby


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
    project_id = fields.Many2one('account.project', string='Proyecto')
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


class Invoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def action_invoice_open(self):
        """
        ME: Validamos la factura, para verificar qué sea cuenta correcta de las líneas
        :return: object
        """
        res = super(Invoice, self).action_invoice_open()
        if self.viaticum:
            travel_concepts = self.env['hr.travel.concepts'].search([])
            accounts = []
            for account in travel_concepts:
                accounts.append(account.account_id)
            if not any(self.invoice_line_ids.filtered(lambda x: x.account_id in accounts)) and self.viaticum:
                raise UserError(_('Una cuenta de las líneas no corresponden a los conceptos (cuenta contable) de viáticos.'))
        return res

    viaticum = fields.Boolean('Viático', default=False,
                              help="Campo para diferenciar facturas creadas por módulo de viáticos.")
    invoice_liquidated = fields.Boolean('Factura liquidada', default=False)


class VoucherExpensesLiquidation(models.Model):
    _name = 'hr.voucher.expenses.liquidation'
    _description = _('Documento de viático en liquidación')

    @api.constrains('amount_total')
    def _check_amount_total(self):
        """
        Validamos monto no sea menor o igual a 0
        :return:
        """
        for record in self:
            if record.amount_total <= 0:
                raise ValidationError(_("Monto no puede ser menor o igual a 0."))

    @api.onchange('invoice_id')
    def _onchange_invoice_id(self):
        """
        Al cambiar la factura llenamos estos campos con sus datos
        :return:
        """
        if self.invoice_id:
            self.date = self.invoice_id.date_invoice
            self.name = self.invoice_id.reference
            self.amount_total = self.invoice_id.amount_total

    type_voucher = fields.Selection([
        ('vale', 'Vale'),
        ('invoice', 'Factura'),
    ], string="Tipo", required=True)
    invoice_id = fields.Many2one('account.invoice', string='Factura', domain=[('viaticum', '=', True),
                                                                              ('invoice_liquidated', '=', False),
                                                                              ('state', '=', 'open')])
    # Al seleccionar factura cambiar estos valores
    date = fields.Date('Fecha documento', required=True)
    name = fields.Char(string="No. Documento")
    amount_total = fields.Float("Monto")
    travel_concept_id = fields.Many2one('hr.travel.concepts', string="Concepto (gasto)")
    type_validation = fields.Selection([
        ('charge', 'Cargo a la empresa'),
        ('reimburse', 'Por reembolsar'),
    ], string="Tipo de validación", default='reimburse')
    account_id = fields.Many2one('account.account', string="Cuenta contable")
    liquidation_id = fields.Many2one('hr.travel.expenses.liquidation', string="Liquidación", ondelete="cascade")


class TravelExpensesLiquidation(models.Model):
    _name = 'hr.travel.expenses.liquidation'
    _order = 'date desc'
    _description = _('Liquidación de viático')
    _inherit = ['mail.thread']

    @api.model
    def _default_journal(self):
        """
        Diario por defecto para la liquidación de viático
        # TODO: Realizar en configuración de empresa
        :return:
        """
        return self.env['account.journal'].search([('name', '=', 'Liquidación de viático')], limit=1)[0].id

    @api.multi
    def action_print(self):
        self.ensure_one()
        return self.env.ref('eliterp_hr_travel_expenses.action_report_travel_expenses_liquidate').report_action(self)

    @api.multi
    def action_deny(self):
        # TODO: Verificar luego si se abre la ventana
        self.write({'state': 'deny'})

    @api.multi
    def action_approve(self):
        self.write({
            'state': 'approve',
            'approval_user': self.env.uid
        })

    @api.multi
    def action_to_approve(self):
        """
        Solicitamos aprobamos la liquidación
        """
        if not self.line_ids:
            raise UserError(_("No tiene líneas de documentos ingresadas para liquidar."))
        self.write({
            'name': self.journal_id.sequence_id.next_by_id(),
            'state': 'to_approve'
        })

    @api.depends('line_ids.amount_total', 'with_request')
    def _compute_difference(self):
        """
        Calculamos la diferencia entre total de solicitud y registro de documentos
        # TODO: Pendiente CON SOLICITUD
        """
        for record in self:
            record.amount_total = sum(line['amount_total'] for line in record.line_ids)
            if record.with_request and record.travel_request_id:
                difference = record.travel_request_id.amount_total - record.amount_total
                record.difference = round(difference, 2)

    @api.multi
    def action_liquidate(self):
        """
        Acción para liquidar documento
        :return:
        """
        list_accounts = []
        for line in self.line_ids:
            if not line.account_id:
                raise ValidationError(_("Debe seleccionar una cuenta en la línea de comprobante."))
            if line.type_voucher != 'vale':
                partner = line.invoice_id.partner_id.id
                account = line.invoice_id.account_id.id
                name = line.invoice_id.concept
                line.invoice_id.write({'invoice_liquidated': True})  # Para no volverla a seleccionar
            else:
                account = line.travel_concept_id.account_id.id
                partner = False
                name = line.travel_concept_id.name
            list_accounts.append({
                'partner': partner,
                'name': name,
                'account': account,
                'account_credit': line.account_id,
                'invoice': line.invoice_id.id or False,
                'amount': line.amount_total
            })
        # Generamos Asiento contable
        move_id = self.env['account.move'].create({
            'journal_id': self.journal_id.id,
            'date': self.date,
            'ref': _('Liquidación :%s') % self.reason,
            'company_division_id': self.company_division_id.id if self.company_division_id else False,
            'project_id': self.project_id.id if self.project_id else False
        })
        for register in list_accounts:
            # Gastos de viáticos (Debe)
            self.env['account.move.line'].with_context(check_move_validity=False).create({
                'name': register['name'],
                'journal_id': self.journal_id.id,
                'partner_id': register['partner'],
                'account_id': register['account'],
                'move_id': move_id.id,
                'debit': register['amount'],
                'invoice_id': register['invoice'],
                'credit': 0.00,
                'date': self.application_date
            })
        moves_credit = []
        for account, group in groupby(list_accounts, key=itemgetter('account_credit')):
            amount = 0.00
            for i in group:
                amount += i['amount']
            moves_credit.append({
                'account': account,
                'amount': amount
            })
        count = len(moves_credit)
        for line in moves_credit:
            count -= 1
            if count == 0:
                self.env['account.move.line'].with_context(check_move_validity=True).create(
                    {'name': line['account'].name,
                     'journal_id': self.journal_id.id,
                     'account_id': line['account'].id,
                     'move_id': move_id.id,
                     'credit': line['amount'],
                     'debit': 0.00,
                     'date': self.application_date})
            else:
                self.env['account.move.line'].with_context(check_move_validity=False).create(
                    {'name': line['account'].name,
                     'journal_id': self.journal_id.id,
                     'account_id': line['account'].id,
                     'move_id': move_id.id,
                     'credit': line['amount'],
                     'debit': 0.00,
                     'date': self.application_date})
        move_id.post()
        # Liquidamos con factura
        for line in self.line_ids.filtered(lambda l: l.type_voucher in ['invoice', 'note']):
            d = line.invoice_id or line.sale_note_id
            movelines = d.move_id.line_ids or d.move_id.line_ids
            line_ = move_id.line_ids.filtered(lambda x: x.invoice_id == d)
            line_x = movelines.filtered(lambda x: x.invoice_id == d and x.account_id.user_type_id.type == 'payable')
            (line_x + line_).reconcile()
        # Cambiamos estado de la solicitud
        if self.with_request:
            self.travel_request_id.update({'state': 'liquidated'})
        self.write({
            'state': 'liquidated',
            'move_id': move_id.id
        })
        return True

    @api.onchange('with_request')
    def _onchange_with_request(self):
        """
        Quitamos la solicitud
        :return:
        """
        if not self.with_request:
            self.travel_request_id = False
        return {}

    @api.constrains('return_date')
    def _check_return_date(self):
        """
        Verificamos la fechas
        :return:
        """
        if self.return_date < self.trip_date:
            raise ValidationError(_('La fecha de retorno no puede ser menor a la del viaje.'))

    @api.multi
    def unlink(self):
        for record in self:
            if not record.state in ['draft', 'deny']:
                raise UserError(_("No se puede borrar una liquidación si no está en borrador o negada."))
        return super(TravelExpensesLiquidation, self).unlink()

    name = fields.Char('Nombre', copy=False, index=True)
    date = fields.Date('Fecha de documento', default=fields.Date.context_today, required=True,
                       readonly=True, states={'draft': [('readonly', False)]}, track_visibility='onchange')
    with_request = fields.Boolean('Con solicitud', default=False,
                                  readonly=True, states={'draft': [('readonly', False)]})
    travel_request_id = fields.Many2one('hr.travel.expenses.request', string="Solicitud",
                                        domain=[('state', '=', 'approve')],
                                        readonly=True, states={'draft': [('readonly', False)]})

    application_date = fields.Date('Fecha de solicitud', default=fields.Date.context_today, required=True,
                                   readonly=True, states={'draft': [('readonly', False)]})
    trip_date = fields.Date('Fecha de viaje', default=fields.Date.context_today, required=True
                            , readonly=True, states={'draft': [('readonly', False)]}, track_visibility='onchange')
    return_date = fields.Date('Fecha de retorno', default=fields.Date.context_today, required=True
                              , readonly=True, states={'draft': [('readonly', False)]}, track_visibility='onchange')
    beneficiary = fields.Many2one('hr.employee', string='Beneficiario', required=True
                                  , readonly=True, states={'draft': [('readonly', False)]}, track_visibility='onchange')
    destination_id = fields.Many2one('hr.travel.destinations', string='Destino', required=True, readonly=True,
                              states={'draft': [('readonly', False)]})

    reason = fields.Char('Motivo', required=True, readonly=True, states={'draft': [('readonly', False)]})
    amount_total = fields.Float(string="Monto total", compute='_compute_difference', store=True)
    approval_user = fields.Many2one('res.users', 'Aprobado por')
    move_id = fields.Many2one('account.move', string='Asiento contable')
    journal_id = fields.Many2one('account.journal', string="Diario", default=_default_journal)
    company_division_id = fields.Many2one('account.company.division', string='División', readonly=True,
                                         states={'draft': [('readonly', False)]}, track_visibility='onchange')
    project_id = fields.Many2one('account.project', string='Proyecto')
    reason_deny = fields.Text('Negado por')
    comment = fields.Text('Notas y comentarios')
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('to_approve', 'Por aprobar'),
        ('approve', 'Aprobada'),
        ('liquidated', 'Liquidada'),
        ('deny', 'Negada')
    ], "Estado", default='draft', track_visibility='onchange')
    line_ids = fields.One2many('hr.voucher.expenses.liquidation', 'liquidation_id',
                               "Comprobantes")
    difference = fields.Float('Diferencia', compute='_compute_difference', store=True)

    @api.depends('trip_date', 'return_date')
    def _compute_days(self):
        """
        Calculamos el número de días
        :return:
        """
        delta = self.return_date - self.trip_date
        self.number_days = 1 if delta.days == 0 else delta.days

    number_days = fields.Integer('# días', compute='_compute_days', store=True)
    number_of_people = fields.Integer('# personas', default=1,
                                      readonly=True, states={'draft': [('readonly', False)]})
    company_id = fields.Many2one('res.company', string="Compañía", default=lambda self: self.env.user.company_id)

# -*- coding: utf-8 -*-


from odoo import fields, models, api, _
import base64
import logging

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
except ImportError:
    _logger.debug(_('No se puede importar librería xlsxwriter.'))


class CollectionLine(models.Model):
    _inherit = "account.collection.line"

    @api.onchange('type_payment')
    def _onchange_type_payment(self):
        """
        Colocamos por defecto el girador el nombre del cliente
        :return:
        """
        if self.type_payment == 'check':
            self.drawer = self.voucher_id.partner_id.name

    type_payment = fields.Selection(selection_add=[('check', 'Cheque')])
    bank_id = fields.Many2one('res.bank', 'Banco de cliente')
    account_number = fields.Char('No. Cuenta')
    check_number = fields.Char('No. Cheque')
    drawer = fields.Char('Girador')
    check_type = fields.Selection([('current', 'Corriente'), ('to_date', 'A la fecha')], string='Tipo de cheque'
                                  , default='current')


class PayOrder(models.Model):
    _inherit = 'account.pay.order'

    type_egress = fields.Selection(selection_add=[('check', 'Cheque')])


class Voucher(models.Model):
    _inherit = "account.voucher"

    def _create_move_sale(self, move_id):
        """
        ME: Creamos cheques recaudados
        :return:
        """
        result = super(Voucher, self)._create_move_sale(move_id)
        object_check = self.env['account.checks']
        for check in self.collection_line.filtered(lambda x: x.type_payment == 'check'):
            object_check.create({
                'partner_id': self.partner_id.id,
                'name': check.check_number.zfill(6),
                'recipient': check.drawer,
                'type': 'receipts',
                'date': check.date_issue,
                'check_date': check.date_due,
                'bank_id': check.bank_id.id,
                'account_number': check.account_number,
                'account_id': check.account_id.id,
                'check_type': check.check_type,
                'state': 'received',
                'amount': check.amount,
                'voucher_id': self.id
            })
        return result

    @api.one
    def _create_check(self):
        """
        Función para crear cheque desde voucher
        :return:
        """
        vals = {}
        object_check = self.env['account.checks']
        vals['name'] = self.check_number
        vals['voucher_id'] = self.id
        vals['partner_id'] = self.partner_id.id if self.partner_id else False
        vals['recipient'] = self.beneficiary
        vals['type'] = 'issued'
        vals['date'] = self.date
        vals['check_date'] = self.bank_date
        vals['state'] = 'issued'
        vals['amount'] = self.amount_cancel
        object_check.create(vals)

    @api.multi
    def post_voucher(self):
        """
        ME: Creamos el cheque si el tipo de egreso es cheque y es pago
        :return:
        """
        result = super(Voucher, self).post_voucher()
        if self.voucher_type == 'purchase':
            if self.type_egress == 'check':
                self._create_check()
                new_ref = self.move_id.ref + " - Cheque: " + self.check_number
                self.move_id.update({'ref': new_ref})
        return result

    def _generate_xlsx_report(self, workbook, context):
        # Formatos
        money_format = workbook.add_format({'num_format': '$#,##0.00', 'bold': 1})
        bold = workbook.add_format({'bold': 1})
        sheet = workbook.add_worksheet('Cheque')
        amount_words = self.env['res.functions'].get_amount_to_word(self.amount_cancel).upper()
        bic = self.bank_journal_id.bank_id.bic  # Me sirve para referencia el banco del cheque
        date = self.bank_date.strftime('%Y/%m/%d')
        if bic == '13':
            # Pichincha
            sheet.set_margins(left=0.18, right=0.7, top=0.0, bottom=0.75)
            # Columnas
            sheet.set_column("A:A", 7.29)
            sheet.set_column("B:B", 10.71)
            sheet.set_column("C:C", 10.71)
            sheet.set_column("D:D", 10.71)
            sheet.set_column("F:F", 12.8)
            sheet.set_column("E:E", 13.14)
            # Filas
            sheet.set_default_row(15)
            sheet.set_row(0, 10.50)
            sheet.set_row(3, 19.50)
            sheet.set_row(4, 10.50)
            sheet.set_row(5, 13.50)
            sheet.set_row(7, 18)
            # Datos
            sheet.write(3, 1, self.beneficiary, bold)
            sheet.write(3, 5, self.amount_cancel, money_format)
            sheet.write(5, 1, amount_words, bold)
            sheet.write(7, 0, 'GUAYAQUIL, %s' % date, bold)
        elif bic == '100':
            # Internacional
            sheet.set_margins(left=0.04, right=0.7, top=0.0, bottom=0.75)
            # Columnas
            sheet.set_column("A:A", 8.14)
            sheet.set_column("B:B", 10.71)
            sheet.set_column("C:C", 10.71)
            sheet.set_column("D:D", 10.71)
            sheet.set_column("E:E", 10.71)
            sheet.set_column("F:F", 0.33)
            sheet.set_column("G:G", 11.57)
            # Filas
            sheet.set_default_row(15)
            sheet.set_row(0, 8.25)
            sheet.set_row(1, 18)
            sheet.set_row(2, 18)
            sheet.set_row(3, 8.25)
            sheet.set_row(7, 6)
            sheet.set_row(8, 13.50)
            # Datos
            sheet.write(4, 1, self.beneficiary, bold)
            sheet.write(4, 6, self.amount_cancel, money_format)
            sheet.write(5, 1, amount_words, bold)
            sheet.write(8, 0, 'GUAYAQUIL, %s' % date, bold)
        elif bic == 'XXX':
            # Margins
            sheet.set_margins(left=0.0, right=0.0, top=0.0, bottom=0.0)
            # Columnas
            sheet.set_column("A:A", 1.86)
            sheet.set_column("B:B", 8.64)
            sheet.set_column("C:C", 10.71)
            sheet.set_column("D:D", 10.71)
            sheet.set_column("E:E", 10.71)
            sheet.set_column("F:F", 12.43)
            sheet.set_column("G:G", 11.57)
            # Filas
            sheet.set_default_row(15)
            sheet.set_row(0, 10.50)
            sheet.set_row(3, 20.25)
            sheet.set_row(4, 6)
            sheet.set_row(5, 13.50)
            sheet.set_row(7, 18)
            # Datos
            sheet.write(3, 2, self.beneficiary, bold)
            sheet.write(3, 6, self.amount_cancel, money_format)
            sheet.write(5, 2, amount_words, bold)
            sheet.write(7, 1, 'GUAYAQUIL, %s' % date, bold)
        elif bic == 'XX':
            # Margins
            sheet.set_margins(left=0.18, right=0.7, top=0.0, bottom=0.75)
            # Columnas
            sheet.set_column("A:A", 7.29)
            sheet.set_column("B:B", 10.71)
            sheet.set_column("C:C", 10.71)
            sheet.set_column("D:D", 10.71)
            sheet.set_column("F:F", 12.86)
            sheet.set_column("E:E", 13.14)
            # Filas
            sheet.set_default_row(15)
            sheet.set_row(0, 12)
            sheet.set_row(3, 19.50)
            sheet.set_row(4, 3.75)
            sheet.set_row(5, 16.50)
            sheet.set_row(6, 19.50)
            sheet.set_row(7, 18.00)
            # Datos
            sheet.write(3, 1, self.beneficiary, bold)
            sheet.write(3, 5, self.amount_cancel, bold)
            sheet.write(5, 1, amount_words, bold)
            sheet.write(7, 0, 'GUAYAQUIL, %s' % date, bold)

        elif bic == '40':
            # Margins
            sheet.set_margins(left=0.18, right=0.7, top=0.73, bottom=0.75)
            # Columnas
            sheet.set_column("A:A", 7.50)
            sheet.set_column("B:B", 10.71)
            sheet.set_column("C:C", 10.71)
            sheet.set_column("D:D", 10.71)
            sheet.set_column("E:E", 7)
            sheet.set_column("F:F", 11.57)
            # Filas
            sheet.set_default_row(15)
            sheet.set_row(3, 11.25)
            sheet.set_row(4, 13.50)
            # Datos
            sheet.write(0, 1, self.beneficiary, bold)
            sheet.write(0, 6, self.amount_cancel, money_format)
            sheet.write(1, 1, amount_words, bold)
            sheet.write(4, 0, 'GUAYAQUIL, %s' % date, bold)
        else:
            return

    @api.multi
    def print_check_xlsx(self):
        """
        Imprimimos cheque en xlsx
        :return:
        """
        self.write(self.create_xlsx_report('Cheque', None))

    def create_xlsx_report(self, name, context=None):
        name = name + '.xlsx'
        workbook = xlsxwriter.Workbook(name, self.get_workbook_options())
        self._generate_xlsx_report(workbook, context)
        workbook.close()
        with open(name, "rb") as file:
            file = base64.b64encode(file.read())
        data = {
            'file': file,
            'file_name': name
        }
        return data

    def get_workbook_options(self):
        return {'in_memory': True}

    def generate_xlsx_report(self, workbook, context):
        # TODO: Revisar está función
        pass

    @api.onchange('check_number')
    def _onchange_check_number(self):
        """
        TODO: Rellenamos con 0 el número de cheque, pendiente hacerlo secuencial
        :return:
        """
        if self.check_number:
            number = self.bank_journal_id.check_padding
            self.check_number = self.check_number.zfill(number)

    type_egress = fields.Selection(selection_add=[('check', 'Cheque')])
    check_number = fields.Char('No. Cheque', readonly=True, states={'draft': [('readonly', False)]},
                               track_visibility='onchange')
    file = fields.Binary('Cheque (.xlsx)')
    file_name = fields.Char('Nombre de archivo', readonly=True)

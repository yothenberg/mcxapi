import sys
import click
import csv
import xlsxwriter
import logging
import json

from .api import McxApi
from collections import namedtuple


def configure_logging():
    formatter = logging.Formatter("mcx: %(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger()
    logger.level = logging.INFO

    info_file_handler = logging.FileHandler("mcx.log")
    info_file_handler.setFormatter(formatter)
    info_file_handler.setLevel(logging.INFO)
    logger.addHandler(info_file_handler)

    error_file_handler = logging.FileHandler("mcx.err")
    error_file_handler.setFormatter(formatter)
    error_file_handler.setLevel(logging.ERROR)
    logger.addHandler(error_file_handler)

    error_stream_handler = logging.StreamHandler(sys.stderr)
    error_stream_handler.setFormatter(formatter)
    error_stream_handler.setLevel(logging.ERROR)
    logger.addHandler(error_stream_handler)


# A tuple containing a list of unique, sorted fieldnames and a list of dicts, rows, that contains the data
ColumnarFormat = namedtuple('ColumnarFormat', 'fieldnames rows')

FORMAT_EXCEL = 'xlsx'
FORMAT_CSV = 'csv'
FORMAT_JSON = 'json'


class McxCli(object):
    """ Context object for command line arguments

    """
    def __init__(self, user, password, instance, company):
        self.user = user
        self.password = password
        self.instance = instance
        self.company = company
        self.config = {}
        self.verbose = False
        self.format = FORMAT_EXCEL

    def set_config(self, key, value):
        self.config[key] = value
        if self.verbose:
            click.echo('  config[%s] = %s' % (key, value), file=sys.stderr)

    def __repr__(self):
        return '<McxCli %r>' % self.home


pass_mcxcli = click.make_pass_decorator(McxCli)


@click.group()
@click.option('--user', '-u', envvar='MCX_USERNAME', help='Usename.', required=True)
@click.option('--password', '-p', envvar='MCX_PASSWORD', help='Password.', required=True)
@click.option('--instance', '-i', envvar='MCX_INSTANCE', help='Instance.', required=True)
@click.option('--company', '-c', envvar='MCX_COMPANY', help='Company name.', required=True)
@click.option('--format', '-f', help='Output file format', type=click.Choice([FORMAT_EXCEL, FORMAT_CSV, FORMAT_JSON]), default=FORMAT_EXCEL)
@click.version_option('1.0')
@click.pass_context
def cli(ctx, user, password, instance, company, format):
    """Command line entry point
    """
    configure_logging()
    ctx.obj = McxCli(user, password, instance, company)
    ctx.obj.format = format


@cli.command()
@click.argument('case_ids', nargs=-1, type=click.INT)
@pass_mcxcli
def cases(mcxcli, case_ids):
    """Exports detailed information about active cases assigned to the user
    """
    file = "cases.{}".format(mcxcli.format)
    click.echo('Exporting cases assigned to {} from {} to {}'.format(mcxcli.user, mcxcli.company, file))

    api = __init_api(mcxcli)
    ids = case_ids
    if not case_ids:
        ids = api.get_case_inbox().ids

    click.echo('Exporting case_ids: {}'.format(ids))

    cases = []
    for case_id in ids:
        click.echo('Exporting case_id: {}'.format(case_id))
        cases.append(api.get_case(case_id))

    output = __cases_to_columnar_format(file, cases)
    __write_to_file(mcxcli, file, output.fieldnames, output.rows)


@cli.command()
@pass_mcxcli
def inbox(mcxcli):
    """Exports summary information about active cases assigned to the user
    """
    file = "case_inbox.{}".format(mcxcli.format)
    click.echo('Exporting case inbox for {} in {} to {}'.format(mcxcli.user, mcxcli.company, file))

    api = __init_api(mcxcli)
    inbox = api.get_case_inbox()
    __write_to_file(mcxcli, file, inbox.fieldnames, inbox.cases)


def __init_api(mcxcli):
    """Initiates the api session and authenticates the user
    """
    api = McxApi(mcxcli.instance, mcxcli.company, mcxcli.user, mcxcli.password)
    api.auth()

    return api


def __cases_to_columnar_format(file, cases):
    """Converts a list of cases to the ColumnarFormat named tuple
    """
    # convert each case to a dict
    rows = [case.dict for case in cases]

    # Generate a set of unique fieldnames across all cases
    fieldnames = set()
    for row in rows:
        row_fieldnames = list(row.keys())
        fieldnames = fieldnames | set(row_fieldnames)
    fieldnames = list(fieldnames)
    fieldnames.sort()

    return ColumnarFormat(fieldnames=fieldnames, rows=rows)


def __write_to_file(mcxcli, file, fieldnames, rows):
    if mcxcli.format == FORMAT_CSV:
        write_to_csv(file, fieldnames, rows)
    elif mcxcli.format == FORMAT_JSON:
        write_to_json(file, rows)
    else:
        write_to_excel(file, fieldnames, rows)


def write_to_json(file, data):
    with open(file, 'w') as jsonfile:
        json.dump(data, jsonfile, sort_keys=True, indent=4)


def write_to_excel(file, fieldnames, rows):
    workbook = xlsxwriter.Workbook(file)
    worksheet = workbook.add_worksheet('Cases')

    r = 0
    c = 0
    try:
        # header row
        for fieldname in fieldnames:
            worksheet.write(r, c, fieldname)
            c += 1

        # data
        r = 1
        c = 0
        for row in rows:
            for fieldname in fieldnames:
                cell = row.get(fieldname, None)
                worksheet.write(r, c, cell)
                c += 1
            r += 1
            c = 0
    finally:
        workbook.close()


def write_to_csv(filename, fieldnames, rows):
    # write out the BOM. Using a BOM to help Excel recognize the encoding of the CSV
    with open(filename, 'wb') as csvfile:
        csvfile.write(u'\ufeff'.encode('utf8'))

    with open(filename, 'a') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

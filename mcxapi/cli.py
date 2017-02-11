import sys
import click
import csv
import xlsxwriter
import logging
import json

from .api import McxApi
from collections import namedtuple

logging.basicConfig(level=logging.WARN)
ColumnarFormat = namedtuple('ColumnarFormat', 'fieldnames rows')

FORMAT_EXCEL = 'xlsx'
FORMAT_CSV = 'csv'
FORMAT_JSON = 'json'


class McxCli(object):

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
@click.option('--verbose', '-v', is_flag=True, help='Enables verbose mode.')
@click.version_option('1.0')
@click.pass_context
def cli(ctx, user, password, instance, company, format, verbose):
    """mzcli is a command line tool that.
    """
    # Create a repo object and remember it as as the context object.  From
    # this point onwards other commands can refer to it by using the
    # @pass_mzcli decorator.
    ctx.obj = McxCli(user, password, instance, company)
    ctx.obj.format = format
    ctx.obj.verbose = verbose


@cli.command()
@pass_mcxcli
def cases(mcxcli):
    """Exports detailed information about active cases assigned to the user

    """
    file = "cases.{}".format(mcxcli.format)
    click.echo('Exporting cases assigned to {} from {} to {}'.format(mcxcli.user, mcxcli.company, file))

    api = __init_api(mcxcli)
    inbox = api.get_case_inbox()
    click.echo('Exporting case_ids: {}'.format(inbox.ids))
    cases = [api.get_case(case_id) for case_id in inbox.ids]
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
    api = McxApi(mcxcli.instance, mcxcli.company, mcxcli.user, mcxcli.password)
    api.auth()

    return api


def __cases_to_columnar_format(file, cases):
    # convert each case to a dict
    rows = [case.dict for case in cases]

    # find set of unique fieldnames across all cases
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
    # header row
    for fieldname in fieldnames:
        worksheet.write(r, c, fieldname)
        c += 1

    # data
    r = 1
    c = 0
    try:
        for row in rows:
            for fieldname in fieldnames:
                cell = row.get(fieldname, None)
                # print("{} - '{}'".format(type(cell), cell))
                worksheet.write(r, c, cell)
                c += 1
            r += 1
            c = 0
    finally:
        workbook.close()


def write_to_csv(filename, fieldnames, rows):
    with open(filename, 'wb') as csvfile:
        csvfile.write(u'\ufeff'.encode('utf8'))

    with open(filename, 'a') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

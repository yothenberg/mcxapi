import sys
import click
import csv
import xlsxwriter
import logging
import json

from collections import namedtuple

from .exceptions import McxError
from .api import McxApi


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


# A tuple containing a list of unique, sorted fieldnames and a list of rows (dicts), that contains the data
ColumnarFormat = namedtuple('ColumnarFormat', 'fieldnames rows')
User = namedtuple('User', 'user password')

FORMAT_EXCEL = 'xlsx'
FORMAT_CSV = 'csv'
FORMAT_JSON = 'json'


class McxCli():
    """ Context object for command line arguments
    """

    def __init__(self, instance, company):
        self.instance = instance
        self.company = company
        self.credentials = None
        self.user = None
        self.password = None
        self.user = None
        self.password = None
        self.config = {}
        self.debug = False
        self.format = FORMAT_EXCEL

    def set_config(self, key, value):
        self.config[key] = value
        if self.debug:
            click.echo('  config[%s] = %s' % (key, value), file=sys.stderr)

    def validate(self):
        if self.credentials is None and (self.user is None or self.password is None):
            raise click.UsageError("If a --credentials file is not being used --user and --password are required.")
        if self.credentials and (self.user or self.password):
            raise click.UsageError("You have specified a --credentials file and a --user and --password. Please choose one or the other.")

    def __repr__(self):
        return '<McxCli %r>' % self.home


pass_mcxcli = click.make_pass_decorator(McxCli)


@click.group()
@click.option('--instance', '-i', envvar='MCX_INSTANCE', help='Instance.', required=True)
@click.option('--company', '-c', envvar='MCX_COMPANY', help='Company name.', required=True)
@click.option('--credentials', '-m', help="Use a file to loop over multiple accounts. File should be one user per line and tab separated, e.g., username<tab>password", type=click.Path(exists=True, readable=True, resolve_path=True, dir_okay=False, file_okay=True))
@click.option('--user', '-u', envvar='MCX_USERNAME', help='Usename.',)
@click.option('--password', '-p', envvar='MCX_PASSWORD', help='Password.',)
@click.option('--format', '-f', help='Output file format', type=click.Choice([FORMAT_EXCEL, FORMAT_CSV, FORMAT_JSON]), default=FORMAT_EXCEL)
@click.option('--debug', '-d', is_flag=True, help='Output stack trace for any errors')
@click.version_option('1.0')
@click.pass_context
def cli(ctx, instance, company, credentials, user, password, format, debug):
    """Command line entry point
    """
    configure_logging()
    ctx.obj = McxCli(instance, company)
    ctx.obj.credentials = credentials
    ctx.obj.user = user
    ctx.obj.password = password
    ctx.obj.format = format
    ctx.obj.debug = debug

    ctx.obj.validate()


@cli.command()
@click.argument('case_ids', nargs=-1, type=click.INT)
@pass_mcxcli
def cases(mcxcli, case_ids):
    """Exports detailed information about active cases assigned to users
    """
    file = "cases.{}".format(mcxcli.format)
    users = __users_from_options(mcxcli)
    if len(users) == 1:
        click.echo('Exporting cases assigned to {} from {} to {}'.format(mcxcli.user, mcxcli.company, file))
    else:
        click.echo('Exporting cases assigned to users in {} from {} to {}'.format(mcxcli.credentials, mcxcli.company, file))

    try:
        cases = []
        for user in users:
            click.echo('Exporting cases assigned to {}'.format(user.user))
            api = __init_api(mcxcli.instance, mcxcli.company, user.user, user.password)
            ids = case_ids
            if not ids:
                ids = api.get_case_inbox().ids

            click.echo('CaseIDs to export: {}'.format(ids))

            i = 1
            for case_id in ids:
                click.echo('Exporting CaseId: {} ({} of {})'.format(case_id, i, len(ids)))
                cases.append(api.get_case(case_id))
                i = i + 1
    except McxError as e:
        logging.error(e, exc_info=mcxcli.debug)
        raise click.Abort()
    else:
        output = __cases_to_columnar_format(file, cases)
        __write_to_file(mcxcli, file, output.fieldnames, output.rows)


@cli.command()
@pass_mcxcli
def inbox(mcxcli):
    """Exports summary information about active cases assigned to users
    """
    file = "case_inbox.{}".format(mcxcli.format)
    users = __users_from_options(mcxcli)
    if len(users) == 1:
        click.echo('Exporting case inbox for {} in {} to {}'.format(mcxcli.user, mcxcli.company, file))
    else:
        click.echo('Exporting case inbox for users in {} from {} to {}'.format(mcxcli.credentials, mcxcli.company, file))

    try:
        cases = []
        for user in users:
            click.echo('Exporting case inbox for {}'.format(user.user))
            api = __init_api(mcxcli.instance, mcxcli.company, user.user, user.password)
            inbox = api.get_case_inbox()
            cases.extend(inbox.cases)
    except McxError as e:
        logging.error(e, exc_info=mcxcli.debug)
        raise click.Abort()
    else:
        __write_to_file(mcxcli, file, inbox.fieldnames, cases)


def __users_from_options(mcxcli):
    users = []
    if mcxcli.credentials:
        users = __read_from_credentials_file(mcxcli.credentials)
        if not len(users):
            raise click.UsageError("Credentials file {} is empty".format(mcxcli.credentials))
    else:
        # No need to check for empty credentials the option parser does that
        users.append(User(user=mcxcli.user, password=mcxcli.password))

    return users


def __init_api(instance, company, user, password):
    """Initiates the api session and authenticates the user
    """
    api = McxApi(instance, company, user, password)
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


def __read_from_credentials_file(file):
    users = []
    with open(file, 'r') as csvfile:
        reader = csv.reader(csvfile, delimiter='\t')
        for user, password in reader:
            users.append(User(user=user, password=password))

    return users


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

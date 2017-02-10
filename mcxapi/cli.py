import sys
import click
import csv
import logging
from .api import McxApi


logging.basicConfig(level=logging.WARN)


class McxCli(object):

    def __init__(self, user, password, instance, company):
        self.user = user
        self.password = password
        self.instance = instance
        self.company = company
        self.config = {}
        self.verbose = False

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
@click.option('--verbose', '-v', is_flag=True, help='Enables verbose mode.')
@click.version_option('1.0')
@click.pass_context
def cli(ctx, user, password, instance, company, verbose):
    """mzcli is a command line tool that.
    """
    # Create a repo object and remember it as as the context object.  From
    # this point onwards other commands can refer to it by using the
    # @pass_mzcli decorator.
    ctx.obj = McxCli(user, password, instance, company)
    ctx.obj.verbose = verbose


@cli.command()
@pass_mcxcli
def cases(mcxcli):
    """Exports detailed information about active cases assigned to the user

    """
    file = "cases.csv"
    click.echo('Exporting cases assigned to {} from {} to {}'.format(mcxcli.user, mcxcli.company, file))

    api = __init_api(mcxcli)
    inbox = api.get_case_inbox()
    click.echo('Exporting case_ids: {}'.format(inbox.ids))
    cases = [api.get_case(case_id) for case_id in inbox.ids]
    __export_cases_to_csv(file, cases)


@cli.command()
@pass_mcxcli
def inbox(mcxcli):
    """Exports summary information about active cases assigned to the user

    """
    file = "case_inbox.csv"
    click.echo('Exporting case inbox for {} in {} to {}'.format(mcxcli.user, mcxcli.company, file))

    api = __init_api(mcxcli)
    inbox = api.get_case_inbox()
    write_to_csv(file, fieldnames=inbox.fieldnames, rows=inbox.cases)


def __init_api(mcxcli):
    api = McxApi(mcxcli.instance, mcxcli.company, mcxcli.user, mcxcli.password)
    api.auth()

    return api


def __export_cases_to_csv(file, cases):
    # convert each case to a dict
    rows = [case.dict for case in cases]

    # find set of unique fieldnames across all cases
    fieldnames = set()
    for row in rows:
        row_fieldnames = list(row.keys())
        fieldnames = fieldnames | set(row_fieldnames)
    fieldnames = list(fieldnames)
    fieldnames.sort()

    write_to_csv(file, fieldnames=fieldnames, rows=rows)


def write_to_csv(filename, fieldnames, rows):
    with open(filename, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

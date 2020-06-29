import click

from poi.process import get_candidate_pairs


@click.group(context_settings=dict(max_content_width=120, help_option_names=['-h', '--help']))
def cli():
    pass


@cli.command('eval', help='\b Construct a dataset with candidate pairs of POIs from different sources')
@click.option('--dataset', default='pois_data.csv', show_default=True, help='.')
def evaluate(dataset):
    get_candidate_pairs(dataset)


cli.add_command(evaluate)


if __name__ == '__main__':
    cli()

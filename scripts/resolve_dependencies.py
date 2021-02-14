# A script to resolve dependencies of MediaWiki extension for Quibble test

# pf for https://raw.githubusercontent.com/wikimedia/integration-config/master/zuul/parameter_functions.py
from pf import dependencies, get_dependencies
from os import environ

# https://github.com/femiwiki/.github/issues/4
if 'MEDIAWIKI_VERSION' in environ and environ['MEDIAWIKI_VERSION'] == 'REL1_35':
  dependencies['EventLogging'].remove('EventBus')

dependencies['ext'] = open('dependencies').read().splitlines()
print(' '.join(['mediawiki/extensions/' + d for d in get_dependencies('ext', dependencies)]))

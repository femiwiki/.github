# A script to resolve dependencies of MediaWiki extension for Quibble test

# pf for https://raw.githubusercontent.com/wikimedia/integration-config/master/zuul/parameter_functions.py
from pf import dependencies, get_dependencies

dependencies['ext'] = open('dependencies').read().splitlines()
print(' '.join(['mediawiki/extensions/' + d for d in get_dependencies('ext', dependencies)]))

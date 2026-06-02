# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'CSTester'
copyright = '2026, Chase Phelps'
author = 'Chase Phelps'
release = '2.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
  'sphinx.ext.autosummary',
  'sphinx.ext.autodoc',
  'sphinx.ext.duration',
  'sphinx.ext.intersphinx',
  'sphinx.ext.napoleon',
  'sphinx.ext.viewcode',
]

intersphinx_mapping = {'python': ('https://docs.python.org/3', None),
}

add_module_names = False

napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_use_param = True
napoleon_use_ivar = True
napoleon_include_init_with_doc = True

templates_path = ['_templates']
exclude_patterns = []

apidoc_modules = [
  {
    'path': 'src/cstester',
    'destination': 'docs/source',
    'exclude_patterns': ['**testOutput.py'],
    'include_private': True,
    'no_headings': True,
    'autodoc_options': {
      'members',
      'undoc-members',
      'private-members',
      'special-members',
    },
  },
]

autodoc_default_options = {
  'member-order': 'bysource',
  'class-doc-from': 'class',
}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

'''
import furo
html_theme = 'furo'
html_theme_options = {
  'top_of_page_buttons': [],
}
'''
html_theme = 'alabaster'
html_theme_options = {
  'description': 'Computer Science programming submission testing tool',
  'github_user': 'chaseleif',
  'github_repo': 'cstester',
  'github_button': True,
  'show_powered_by': True,
}

html_static_path = ['_static']

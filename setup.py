from setuptools import setup

version = '1.1.dev0'

long_description = '\n\n'.join([
    open('README.rst').read(),
    open('CREDITS.rst').read(),
    open('CHANGES.rst').read(),
    ])

install_requires = [
    'Django',
    'django-extensions',
    'django-jsonfield >= 0.8.10',
    'django-nose',
    'lizard-map >= 4.1',
    'lizard-ui >= 4.1',
    'requests',
    ],

setup(name='lizard-geodin',
      version=version,
      description="Coupling between Geodin's REST API and Lizard",
      long_description=long_description,
      # Get strings from http://www.python.org/pypi?%3Aaction=list_classifiers
      classifiers=['Programming Language :: Python',
                   'Framework :: Django',
                   ],
      keywords=['lizard', 'geodin'],
      author='Reinout van Rees',
      author_email='reinout.vanrees@nelen-schuurmans.nl',
      url='https://github.com/lizardsystem/lizard-geodin',
      license='GPL',
      packages=['lizard_geodin'],
      include_package_data=True,
      zip_safe=False,
      install_requires=install_requires,
      entry_points={
        'lizard_map.adapter_class': [
            'lizard_geodin_points = lizard_geodin.layers:GeodinPoints',
            ],
          'console_scripts': [
          ]},
      )

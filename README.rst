|MIT|

==================
LGM-POI
==================

A python library for constructing candidate POI pairs among a custom source and OSM.

The source code was tested using Python 3.7 and Scikit-Learn 0.23.1 on a Linux server.

Setup procedure
---------------

Download the latest version from the `GitHub repository <https://github.com/LinkGeoML/LGM-POI.git>`_, change to
the main directory and run:

.. code:: bash

   pip install -r pip_requirements.txt

It should install all the required libraries automatically (*scikit-learn, numpy, pandas, geopandas, fuzzywuzzy etc.*).

Usage
-----
The execution of the project starts with downloading the OSM POIs which are relative to the computed area of the
provided input source and identifies the best candidate matches utilizing name, tags and spatial closeness. Afterwards,
these matches are saved to the **pois_dataset_pairs** file under the **output** folder.

The above process can be executed successfully with the following command:

.. code:: bash

    python -m poi.cli eval --dataset <input_file.csv>


where *<input_file.csv>* is the input file in CSV format. The input file should contain the following columns to be
valid: *poi_id*, *name*, *theme*, *class_name*, *subclass_n*, *x*, *y*, *geom*.

License
-------
LGM-POI is available under the `MIT <https://opensource.org/licenses/MIT>`_ License.

..
    .. |Documentation Status| image:: https://readthedocs.org/projects/coala/badge/?version=latest
       :target: https://linkgeoml.github.io/LGM-Interlinking/

.. |MIT| image:: https://img.shields.io/badge/License-MIT-yellow.svg
   :target: https://opensource.org/licenses/MIT

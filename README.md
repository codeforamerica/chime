Bizarro
=======

An experimental CMS that edits Jekyll sites and uses Git persistence and history.

Install
-------

1. Bizarro CMS is a Python Flask web application. Follow the instructions on
   [Python Virtual Environments](https://github.com/codeforamerica/howto/blob/master/Python-Virtualenv.md)
   to prepare your Python development space.

2. You will need a bare Github repository in the directory `sample-site`
   (this will become configurable in the future). Unpack the supplied
   [sample-site.tar.gz](sample-site.tar.gz) to get an empty repository.

3. Test-run the app:
   
        $ python app.py
   
   You can alternatively use [Foreman](http://ddollar.github.com/foreman)
   or its Python port [Honcho](https://pypi.python.org/pypi/honcho):
   
        $ honcho start

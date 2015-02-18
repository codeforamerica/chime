Ceviche
=======

An experimental CMS that edits Jekyll sites and uses Git persistence and history.  Very much a WIP that is entirely untested and unproven, consider this "Reckon 0.1".

Install
-------

1. Ceviche CMS is a Python Flask web application. Follow the instructions on
   [Python Virtual Environments](https://github.com/codeforamerica/howto/blob/master/Python-Virtualenv.md)
   to prepare your Python development space.

2. You will need a bare Github repository in the directory `sample-site`
   (this will become configurable in the future).

3. copy env.sample to .env

4. Run the app with [Foreman](http://ddollar.github.com/foreman):

        $ foreman run python run.py

   You can alternatively use Foreman's Python port [Honcho](https://pypi.python.org/pypi/honcho):

        $ honcho start

Who maintains this?
-------------------

[Mike Migurski](http://github.com/migurski) and [Frances Berriman](http://github.com/phae)

You can read a bit more about what we're up to over here http://digifrodo.tumblr.com

[![Stories in Ready](https://badge.waffle.io/codeforamerica/ceviche-cms.svg?label=ready&title=Ready)](http://waffle.io/codeforamerica/ceviche-cms)
[![Build Status](https://travis-ci.org/codeforamerica/ceviche-cms.svg?branch=master)](https://travis-ci.org/codeforamerica/ceviche-cms)

# What is this?

This is part of the Digital Front Door inititive.  You can read more about it here: https://github.com/codeforamerica/digitalfrontdoor

## Logging issues / ideas 
Make an issue: https://github.com/chimecms/chime/issues/new

# Install

1. Chime CMS is a Python Flask web application. Follow the instructions on
   [Python Virtual Environments](https://github.com/codeforamerica/howto/blob/master/Python-Virtualenv.md)
   to prepare your Python development space. Make sure to use Python 2.7. Your commands may look something like:
 + sudo pip install virtualenv
 + virtualenv -p /usr/bin/python2.7 .venv
 + source .venv/bin/activate

2. Install the project requirements: `pip install -r requirements.txt`

3. You will need a bare Github repository in the directory `sample-site` with an initial empty commit
   (this will become configurable in the future):

 + `cd sample-site`
 + `git init`
 + `git commit --allow-empty -m "First commit"`

4. copy env.sample to .env

5. Run app using [Honcho and the `Procfile`](https://github.com/codeforamerica/howto/blob/master/Procfile.md):

        $ honcho start

# Who maintains this?

[Mike Migurski](http://github.com/migurski) and [Frances Berriman](http://github.com/phae)

You can read a bit more about what we're up to over here http://digifrodo.tumblr.com

[![Stories in Ready](https://badge.waffle.io/chimecms/chime.svg?label=ready&title=Ready)](http://waffle.io/chimecms/chime)
[![Build Status](https://travis-ci.org/chimecms/chime.svg?branch=master)](https://travis-ci.org/chimecms/chime)

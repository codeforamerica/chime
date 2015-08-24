# What is this?

This is part of the Digital Front Door inititive.  You can read more about it here: https://github.com/codeforamerica/digitalfrontdoor

## Logging issues / ideas 
Make an issue: https://github.com/chimecms/chime/issues/new

# Install

To work with the Chime source code:

1. Chime CMS is a Python Flask web application. Follow the instructions on
   [Python Virtual Environments](https://github.com/codeforamerica/howto/blob/master/Python-Virtualenv.md)
   to prepare your Python development space. Make sure to use Python 2.7. Your commands may look something like:
 + `sudo pip install virtualenv`
 + `virtualenv -p /usr/bin/python2.7 .venv`
 + `source .venv/bin/activate`

2. Install the project requirements: `pip install -r requirements.txt`

3. You will need a Github repository in the directory `sample-site` cloned from [chimecms/chime-starter](https://github.com/chimecms/chime-starter):
 + `git clone --bare --single-branch --branch master https://github.com/chimecms/chime-starter.git sample-site`
 + `git --git-dir sample-site remote rename origin starter` (ignore the error about _config section 'remote.starter.fetch'_)

4. copy `env.sample` to `.env`.

5. You will also need a working copy of [Jekyll](https://github.com/codeforamerica/howto/blob/master/Jekyll.md):
 + `sudo apt-get -y install rbenv curl`
 + `./jekyll/install-jekyll.sh`

6. Run Chime in debug mode using [Honcho and the `Procfile`](https://github.com/codeforamerica/howto/blob/master/Procfile.md):

        $ honcho run python ./run.py

If you're a Docker user, we maintain a public build at the Docker Hub as [chimecms/chime](https://hub.docker.com/r/chimecms/chime).

# Who maintains this?

[Mike Migurski](http://github.com/migurski) and [Frances Berriman](http://github.com/phae)

You can read a bit more about what we're up to over here http://digifrodo.tumblr.com

[![Stories in Ready](https://badge.waffle.io/chimecms/chime.svg?label=current-sprint&title=WorkingOn)](http://waffle.io/chimecms/chime)
[![Build Status](https://travis-ci.org/chimecms/chime.svg?branch=master)](https://travis-ci.org/chimecms/chime)

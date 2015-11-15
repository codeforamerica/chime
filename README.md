# What is this?

Chime was a part of Code for America’s Digital Front Door inititive.  You can read more about it here: https://github.com/codeforamerica/digitalfrontdoor

**Development was halted in October 2015.**

# Install

If you're a Docker user, you can always download the latest build from the Docker Hub as [chimecms/chime](https://hub.docker.com/r/chimecms/chime). Or if you'd like to work with
the source:

1. Chime CMS is a Python Flask web application. Follow the instructions on
   [Python Virtual Environments](https://github.com/codeforamerica/howto/blob/master/Python-Virtualenv.md)
   to prepare your Python development space. Make sure to use Python 2.7. Your commands may look something like:
 + sudo pip install virtualenv
 + virtualenv -p /usr/bin/python2.7 .venv
 + source .venv/bin/activate

2. Install the project requirements: `pip install -r requirements.txt`

3. You will need a bare Github repository in the directory `sample-site` with an initial empty commit
   (this will become configurable in the future):
 + `mkdir sample-site`
 + `cd sample-site`
 + `git init`
 + `git commit --allow-empty -m "First commit"`

4. copy env.sample to .env

5. Run app using [Honcho and the `Procfile`](https://github.com/codeforamerica/howto/blob/master/Procfile.md):

        $ honcho start

# Who maintains this?

Prior to October 2015, [Mike Migurski](http://github.com/migurski) and [Frances Berriman](http://github.com/phae). Currently, Chime is not maintained.

You can read a bit more about what we were up to over here http://digifrodo.tumblr.com

[![Stories in Ready](https://badge.waffle.io/chimecms/chime.svg?label=current-sprint&title=WorkingOn)](http://waffle.io/chimecms/chime)
[![Build Status](https://travis-ci.org/chimecms/chime.svg?branch=master)](https://travis-ci.org/chimecms/chime)

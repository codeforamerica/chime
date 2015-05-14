#!/bin/bash
eval "$(rbenv init -)"
export PATH="$HOME/.rbenv/bin:$PATH"

# get a modern ruby
if [ ! -d ~/.rbenv/plugins/rvm-download ]; then
    git clone https://github.com/garnieretienne/rvm-download.git ~/.rbenv/plugins/rvm-download
fi
rbenv download 2.2.0

# use it
RBENV_VERSION=2.2.0; export RBENV_VERSION

# install bundler and needed gems
rbenv rehash
gem install bundler
rbenv rehash

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
BUNDLE_GEMFILE="${DIR}/Gemfile"; export BUNDLE_GEMFILE
bundle install

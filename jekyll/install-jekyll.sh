#!/bin/bash
eval "$(rbenv init -)"
export PATH="$HOME/.rbenv/bin:$PATH"

if [ ! -d $HOME/.rbenv/plugins/ruby-build ]; then
    git clone https://github.com/sstephenson/ruby-build.git ~/.rbenv/plugins/ruby-build
fi

rbenv install -s 2.2.0

RBENV_VERSION=2.2.0; export RBENV_VERSION

rbenv rehash
if [ ! `gem query -i -n bundler` == 'true' ]; then
    gem install bundler
    rbenv rehash
fi

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
BUNDLE_GEMFILE="${DIR}/Gemfile"; export BUNDLE_GEMFILE
bundle install

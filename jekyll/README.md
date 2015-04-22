Jekyll Install
=============

This is our installation of jekyll, which we use to preview and render
pages. Eventually this should happen automatically, but for now there's
a manual process to get it set up for development. This assumes rbenv
for managing ruby versions, but if you already have rvm, go ahead and
keep using that. (You can't use both; they conflict.)

It goes something like this:

* Install rbenv
  + Ubuntu: `apt-get install rbenv`
  + MacOS: `brew install rbenv ruby-build` (using [Homebrew](http://brew.sh/))
* activate rbenv temporarily or permanently
  + temporary: `eval "$(rbenv init -)"`
  + permanent: `echo 'eval "$(rbenv init -)"' >> ~/.bash_profile` (restart shell after)
* Install ruby-build
  + `git clone https://github.com/sstephenson/ruby-build.git ~/.rbenv/plugins/ruby-build`
* Install and use the right ruby
  + `rbenv install 2.2.0`
  + `rbenv shell 2.2.0`
* Install bundler
  + `gem install bundler`
  + `rbenv rehash`
* Install the gems
  + `bundle install`
  + `rbenv rehash`
* check jekyll
  + `cd ..`
  + `jekyll/run-jekyll.sh`
  + Should produce the jekyll help, not error messages




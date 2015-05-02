username = node[:user]

package 'rbenv'
package 'git'


ruby_build_packages = %w(autoconf bison build-essential libssl-dev libyaml-dev libreadline6-dev zlib1g-dev libncurses5-dev libffi-dev libgdbm3 libgdbm-dev)

ruby_build_packages.each {|p| package p}

repo_dir = File.realpath(File.join(File.dirname(__FILE__), '..', '..', '..'))

execute "jekyll/install-jekyll.sh" do
  cwd repo_dir
end

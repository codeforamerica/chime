include_recipe "python"
include_recipe "account"
package "git"

#
# Put code where it needs to be.
#
git "/opt/bizarro-cms" do
  repository node['repo']
  reference node['ref']
end

execute "pip install -r requirements.txt" do
  cwd "/opt/bizarro-cms"
end

#
# Populate working directories.
#
name = node[:user]

directory "/var/opt/bizarro-work" do
  owner name
  group name
  mode "0775"
end

bash "git clone https://github.com/codeforamerica/ceviche-starter.git" do
  user 'root'
  flags '-e'
  code <<-GIT
DIR=`mktemp -d /tmp/bizarro-site-XXXXXX`
git clone --bare https://github.com/codeforamerica/ceviche-starter.git $DIR
git --git-dir $DIR remote rm origin
chown #{name}:#{name} $DIR
chmod 0775 $DIR
rm -rf /var/opt/bizarro-site
mv $DIR /var/opt/bizarro-site
GIT
  creates "/var/opt/bizarro-site/config"
end

#
# Ensure upstart job exists.
#
env_file = File.realpath(File.join(File.dirname(__FILE__), 'honcho-env'))

execute "honcho export upstart /etc/init" do
  command "honcho -e #{env_file} export -u #{name} -a bizarro-cms upstart /etc/init"
  cwd "/opt/bizarro-cms"
end

#
# Make it go.
#
execute "stop bizarro-cms" do
  returns [0, 1]
end

execute "start bizarro-cms"

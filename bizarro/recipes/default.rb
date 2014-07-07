include_recipe "python"
include_recipe "account"
package "git"

git "/opt/bizarro-cms" do
  repository node['repo']
  reference node['ref']
end

execute "pip install -r requirements.txt" do
  cwd "/opt/bizarro-cms"
end

name = node[:user]

directory "/var/opt/bizarro-work" do
  owner name
  group name
  mode "0775"
end

directory "/var/opt/sample-site" do
  owner name
  group name
  mode "0775"
end

bash "tar -xzf sample-site.tar.gz" do
  user name
  code "tar -C /var/opt -xzf /opt/bizarro-cms/sample-site.tar.gz"
  creates "/var/opt/sample-site/config"
end

env_file = File.realpath(File.join(File.dirname(__FILE__), 'honcho-env'))

execute "honcho export upstart /etc/init" do
  command "honcho -e #{env_file} export -u #{name} -a bizarro-cms upstart /etc/init"
  cwd "/opt/bizarro-cms"
end

execute "stop bizarro-cms" do
  returns [0, 1]
end

execute "start bizarro-cms"

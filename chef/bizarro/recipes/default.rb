include_recipe "python"
include_recipe "repository"

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

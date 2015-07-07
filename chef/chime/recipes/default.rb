package 'python-pip'
package 'build-essential'
include_recipe "repository"
require 'socket'

hostname = Socket.gethostbyname(Socket.gethostname).first
repo_dir = File.realpath(File.join(File.dirname(__FILE__), '..', '..', '..'))
username = node[:user]

ga_client_id = ENV['GA_CLIENT_ID']
ga_client_secret = ENV['GA_CLIENT_SECRET']
authorization_data_href = ENV['AUTH_DATA_HREF']
ga_redirect_uri = "http://#{hostname}/callback"

#
# Put code where it needs to be.
#
execute "pip install -r requirements.txt" do
  cwd repo_dir
end

execute 'pip install honcho[export]'

execute "pip install -U ." do
  cwd repo_dir
end

#
# Populate working directories.
#
directory "/var/opt/chime-work" do
  action :delete
  recursive true
end

directory "/var/opt/chime-work" do
  owner username
  group username
  mode "0775"
end

#
# Ensure upstart job exists.
#
env_file = '/etc/chime.conf'

env_contents = <<-CONF
RUNNING_STATE_DIR=/var/run/#{username}
REPO_PATH=/var/opt/chime-site
WORK_PATH=/var/opt/chime-work
BROWSERID_URL=http://#{hostname}/

GA_CLIENT_ID="#{ga_client_id}"
GA_CLIENT_SECRET="#{ga_client_secret}"
GA_REDIRECT_URI="#{ga_redirect_uri}"

AUTH_DATA_HREF=#{authorization_data_href}
CONF

if ENV['ACCEPTANCE_TEST_MODE']
  env_contents << "ACCEPTANCE_TEST_MODE=1\n"
end

file env_file do
  content env_contents
end

execute "honcho export upstart /etc/init" do
  command "honcho -e #{env_file} export -u #{username} -a chime upstart /etc/init"
  cwd repo_dir
end

#
# Make it go.
#
execute "stop chime" do
  returns [0, 1]
end

execute "start chime"
execute "apache2ctl restart"

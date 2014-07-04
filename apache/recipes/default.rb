package 'apache2'

link "/etc/apache2/mods-enabled/mime.conf" do
  to "../mods-available/mime.conf"
end

link "/etc/apache2/mods-enabled/mime.load" do
  to "../mods-available/mime.load"
end

link "/etc/apache2/mods-enabled/proxy.conf" do
  to "../mods-available/proxy.conf"
end

link "/etc/apache2/mods-enabled/proxy.load" do
  to "../mods-available/proxy.load"
end

link "/etc/apache2/mods-enabled/proxy_http.load" do
  to "../mods-available/proxy_http.load"
end

link "/etc/apache2/mods-enabled/headers.load" do
  to "../mods-available/headers.load"
end

link "/etc/apache2/mods-enabled/include.load" do
  to "../mods-available/include.load"
end

link "/etc/apache2/mods-enabled/authz_host.load" do
  to "../mods-available/authz_host.load"
end

# link "/etc/apache2/mods-enabled/log_config.conf" do
#   to "../mods-available/log_config.conf"
# end

link "/etc/apache2/mods-enabled/vhost_alias.load" do
  to "../mods-available/vhost_alias.load"
end

file "/etc/apache2/apache2.conf" do
    owner "root"
    group "root"
    mode  "0644"
    content File.open(File.dirname(__FILE__) + "/apache2.conf").read()
end

file "/etc/apache2/bizarro-cms-vhost.conf" do
    owner "root"
    group "root"
    mode  "0644"
    content File.open(File.dirname(__FILE__) + "/bizarro-cms-vhost.conf").read()
end

directory "/etc/apache2/sites-enabled" do
  action    :delete
  recursive true
end

execute "apache2ctl graceful" do
  path ['/usr/bin', '/usr/sbin', '/usr/local/bin', '/usr/local/sbin']
end

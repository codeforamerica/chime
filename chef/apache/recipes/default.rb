package 'apache2'

#
# Activate minimum required modules.
#
execute 'a2enmod mime'
execute 'a2enmod proxy'
execute 'a2enmod proxy_http'
execute 'a2enmod headers'
execute 'a2enmod include'
execute 'a2enmod authz_host'
# execute 'a2enmod log_config'
execute 'a2enmod vhost_alias'

#
# Create server configuration.
#
file '/etc/apache2/sites-available/chime-cms-vhost.conf' do
  owner 'root'
  group 'root'
  mode  '0644'
  content <<-VHOST
<VirtualHost *:80>
    <Location />
        ProxyPass http://127.0.0.1:5000/
        ProxyPassReverse http://127.0.0.1:5000/
    </Location>
    <Proxy http://127.0.0.1:5000/*>
        Allow from all
    </Proxy>
</VirtualHost>
VHOST
end

execute 'a2dissite 000-default'
execute 'a2ensite chime-cms-vhost.conf'

#
# Make it go.
#
execute "apache2ctl graceful" do
  path ['/usr/bin', '/usr/sbin', '/usr/local/bin', '/usr/local/sbin']
end

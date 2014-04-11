module Reading
  class Generator < Jekyll::Generator
    def generate(site)
      # Select all pages with layout: multi.
      multis = site.pages.select { |page| !page.data.nil? && page.data['layout'] == 'multi' }
      
      multis.each do |page|
        # Delete the initial page.
        site.pages.delete(page)
          
        # Create new pages, one per language.
        ['en', 'es', 'zh-cn'].each do |language|
          new_page = page.clone()
          
          # Assign a name like base.language.extension, compatible with Apache:
          # http://httpd.apache.org/docs/2.2/content-negotiation.html#naming
          new_page.name = page.basename + '.' + language + page.ext
          new_page.process(new_page.name)

          new_page.data = page.data.clone()
          new_page.data['language'] = language
          
          # For languages other than English, move the title and content.
          if language != 'en'
            new_page.data['title'] = page.data['title-' + language]
            new_page.content = page.converter.convert(page.data['body-' + language])
          end
          
          site.pages << new_page
        end
      end

    end
  end
end

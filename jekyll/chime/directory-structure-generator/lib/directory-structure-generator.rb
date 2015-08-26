module Jekyll
    class DirectoryStructureGenerator < Jekyll::Generator
        safe true
        priority :lowest

        def generate(site)
            ''' Build column and breadcrumb data and inject it into site pages.
            '''
            pages = []

            # step through all the pages in the site
            for check_page in site.pages
                # ignore pages that aren't created by chime
                if is_chime_page_layout(check_page.data['layout'])
                    path_list = make_path_split(check_page.path)
                    cat_path = path_list.join("/")
                    # copy data from the page's front matter
                    page_info = check_page.data.clone
                    # protect against missing values
                    page_info['order'] = page_info['order'] ? page_info['order'].to_i : 0
                    page_info['description'] = "" if not page_info['description']
                    page_info['title'] = "" if not page_info['title']
                    # add our own values
                    page_info['path_list'] = path_list
                    page_info['depth'] = path_list.length
                    page_info['path'] = cat_path
                    page_info['link_path'] = "/#{cat_path}/"
                    page_info['selected'] = false

                    pages << page_info
                end
            end

            # sort the pages by depth
            pages = pages.sort_by { |hsh| hsh['depth'] }
            lowest_depth = pages[0]['depth']

            # build columns
            all_columns = []
            for check_page in pages
                if all_columns.length < check_page['depth'] - lowest_depth + 1
                    all_columns << []
                end
                all_columns[check_page['depth'] - lowest_depth] << check_page
            end
            # sort the root pages within their column, so
            # non-category pages can use them
            all_columns[0] = all_columns[0].sort_by { |hsh| hsh['title'] }

            # step through all the pages
            for target_page in site.pages
                if !is_chime_page_layout(target_page.data['layout'])
                    # send non-category and -article pages just the root pages and no breadcrumbs
                    target_page.data['columns'] = [{"title" => "", "pages" => all_columns[0]}]
                    target_page.data['breadcrumbs'] = []
                    next
                end

                target_path_list = make_path_split(target_page.path)
                target_page_cat_path = target_path_list.join("/")
                target_page_depth = target_path_list.length

                # build the columns and breadcrumbs
                display_columns = []
                breadcrumbs = []
                next_column_title = ""
                # don't go any deeper in the site structure than the target page
                end_range = 0
                end_depth = [target_page_depth - lowest_depth + 1, all_columns.length - 1].min
                for check_depth in (0..end_depth)
                    check_column = all_columns[check_depth]
                    show_pattern = target_path_list[0..end_range].join("/")
                    select_pattern = target_path_list[0..end_range + 1].join("/")
                    # the column title is the title of the page selected in the last column
                    column_info = {"title" => next_column_title}
                    column_pages = []
                    for check_page in check_column
                        clone_page = check_page.clone
                        if select_pattern == clone_page['path']
                            clone_page['selected'] = true
                            next_column_title = clone_page['title']
                            breadcrumbs << clone_page
                        end

                        # only show pages that share the target page's path
                        if /^#{show_pattern}/.match(clone_page['path'])
                            column_pages << clone_page
                        end
                    end

                    # sort and assign
                    column_info['pages'] = column_pages.sort_by { |hsh| hsh['title'] }
                    display_columns << column_info
                    end_range += 1
                end

                target_page.data['columns'] = display_columns
                target_page.data['breadcrumbs'] = breadcrumbs
            end
        end

        def is_chime_page_layout(layout)
            ''' Return true if the page layout is chime-specific
            '''
            return (layout == "category" or layout == "article")
        end

        def make_path_split(path_string)
            ''' Split a page path, removing the index file.
            '''
            path_list = path_string.split("/")
            if path_list.length > 1 and path_list[-1] == "index.markdown"
                path_list.pop()
            end
            return path_list
        end
    end
end

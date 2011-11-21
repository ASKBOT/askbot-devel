var prevSortMethod = sortMethod;
var liveSearch = function(){
    var query = undefined;
    var prev_text = undefined;
    var running = false;
    var q_list_sel = 'question-list';//id of question listing div
    var search_url = undefined;
    var restart_query = function(){};
    var process_query = function(){};
    var render_result = function(){};

    var refresh_x_button = function(){
        if ($.trim(query.val()).length > 0){
            if (query.attr('class') === 'searchInput'){
                query.attr('class', 'searchInputCancelable');
                x_button = $('<input class="cancelSearchBtn" type="button" name="reset_query"/>');
                //x_button.click(reset_query);
                x_button.val('X');
                x_button.click(
                    function(){
                        query.val('');
                        if (sortMethod === 'relevance-desc'){
                            sortMethod = prevSortMethod;
                        }
                        refresh_x_button();
                        reset_query(sortMethod);
                    }
                );
                query.after(x_button);
            }
        } else {
            $('input[name=reset_query]').remove();
            query.attr('class', 'searchInput');
        }
    };

    var reset_sort_method = function(){
        if (sortMethod === 'relevance-desc'){
            sortMethod = prevSortMethod;
            if (sortMethod === 'relevance-desc'){
                sortMethod = 'activity-desc';
            }
        } else {
            sortMethod = 'activity-desc';
            prevSortMethod = 'activity-desc';
        }
    };

    var eval_query = function(){
        cur_text = $.trim(query.val());
        if (cur_text !== prev_text && running === false){
            if (cur_text.length >= minSearchWordLength){
                process_query();
                running = true;
            } else if (cur_text.length === 0){
                restart_query();
            }
        }
    };

    var ask_page_search_listen = function(){
        running = false;
        var ask_page_eval_handle;
        query.keyup(function(e){
            if (running === false){
                clearTimeout(ask_page_eval_handle);
                ask_page_eval_handle = setTimeout(eval_query, 400);
            }
        });
    };

    var main_page_search_listen = function(){
        running = false;
        refresh_x_button();
        var main_page_eval_handle;
        query.keyup(function(e){
            refresh_x_button();
            if (running === false){
                clearTimeout(main_page_eval_handle);
                main_page_eval_handle = setTimeout(eval_query, 400);
            }
        });
    };

    var render_counter = function(count, word, counter_class, counter_subclass){
        var output = '<div class="' + counter_class + ' ' + counter_subclass + '">' +
                    '<span class="item-count">' +
                        count;
        if (counter_class === 'accepted'){
            output += '&#10003;';
        }
        output +=   '</span>' +
                    '<div>' + word + '</div>' +
                '</div>';
        return output;
    };

    var render_title = function(result){
        return '<h2>' +
                    '<a href="' + 
                            askbot['urls']['question_url_template']
                            .replace('{{QuestionID}}', result['id']) +
                    '" onmouseover="load_question_body(this,' + result['id'] + ')">' +
                        result['title'] +
                    '</a>' +
                '</h2>';
    };

    var render_user_link = function(result){
        if (result['u_id'] !== false){
            if (result['u_is_anonymous'] === true){
                return '<span class="anonymous">' + 
                            askbot['messages']['name_of_anonymous_user'] +
                       '</span>';
            } else {
                var u_slug = result['u_name'].toLowerCase().replace(/ +/g, '-');
                return '<a ' +
                            'href="' + 
                                askbot['urls']['user_url_template']
                                .replace('{{user_id}}', result['u_id'])
                                .replace('{{slug}}', u_slug) +
                        '">' +
                            result['u_name'] +
                        '</a> ';
            }
        }
        else {
            return '';
        }
    };

    var render_badge = function(result, key){
        return '<span ' + 
                    'title="' + result[key + '_title'] + '"' +
                '>' +
                '<span ' +
                    'class="' + result[key + '_css_class'] + '"' +
                '>' + result[key + '_badge_symbol'] + '</span>' +
                '<span class="badgecount">' + result[key] + '</span>';
    };

    var render_user_badge_and_karma = function(result){
        var rep_title = result['u_rep'] + ' ' + result['u_rep_word'];
        var html = '<span ' +
                        'class="reputation-score" ' +
                        'title="' + rep_title + '"' +
                    '>' + result['u_rep'] + '</span>';
        if (result['u_gold'] > 0){
            html += render_badge(result, 'u_gold');
        }
        if (result['u_silver'] > 0){
            html += render_badge(result, 'u_silver');
        }
        if (result['u_bronze'] > 0){
            html += render_badge(result, 'u_bronze');
        }
        return html;
    };

    var render_user_flag = function(result){
        var country_code = result['u_country_code'];
        if (country_code) {
            return '<img class="flag" src="'+ 
                   mediaUrl(
                        'media/images/flags/' + 
                        country_code.toLowerCase() +
                        '.gif'
                   ) +
                   '"/>';
        } else {
            return '';
        }
    };

    var render_user_info = function(result){
        var user_html = 
        '<div class="userinfo">' +
            '<span class="relativetime" ' +
                'title="' + result['timestamp'] + '"' +
            '>' +
            result['timesince'] +
            '</span> ' +
            render_user_link(result);
        if (result['u_is_anonymous'] === false){
            user_html += render_user_flag(result);
            //render_user_badge_and_karma(result) +
        }
        user_html += '</div>';
        return user_html;
    };

    var render_tag = function(tag_name, linkable, deletable){
        var tag = new Tag();
        tag.setName(tag_name);
        tag.setDeletable(deletable);
        tag.setLinkable(linkable);
        return tag.getElement().outerHTML();
    };

    var render_tags = function(tags, linkable, deletable){
        var tags_html = '<ul class="tags">';
        $.each(tags, function(idx, item){
            tags_html += render_tag(item, linkable, deletable);
        });
        tags_html += '</ul>';
        return tags_html;
    };

    var render_faces = function(faces){
        if (faces.length === 0){
            return;
        }
        $('#contrib-users>a').remove();
        var html = '';
        for (var i=0; i<faces.length; i++){
            html += faces[i];
        }
        $('#contrib-users').append(html);
    };

    var render_related_tags = function(tags){
        if (tags.length === 0){
            return;
        }
        var html = '';
        for (var i=0; i<tags.length; i++){
            html += render_tag(tags[i]['name'], true, false);
            html += '<span class="tag-number">&#215; ' +
                        tags[i]['used_count'] +
                    '</span>' +
                    '<br />';
        }
        $('#related-tags').html(html);
    };

    var render_paginator = function(paginator){
        var pager = $('#pager');
        if (paginator === ''){
            pager.hide();
            return;
        }
        else {
            pager.show();
            pager.html(paginator);
        }
    };

    var set_question_count = function(count_html){
        $('#questionCount').html(count_html);
    };

    var get_old_tags = function(container){
        var tag_elements = container.find('.tag');
        var old_tags = [];
        tag_elements.each(function(idx, element){
            old_tags.push($(element).html());
        });
        return old_tags;
    };

    var render_search_tags = function(tags){
        var search_tags = $('#searchTags');
        search_tags.children().remove();
        if (tags.length == 0){
            $('#listSearchTags').hide();
            $('#search-tips').hide();//wrong - if there are search users
        } else {
            $('#listSearchTags').show();
            $('#search-tips').show();
            var tags_html = '';
            $.each(tags, function(idx, tag_name){
                var tag = new Tag();
                tag.setName(tag_name);
                tag.setDeletable(true);
                tag.setLinkable(false);
                tag.setDeleteHandler(
                    function(){
                        remove_search_tag(tag_name);
                    }
                );
                search_tags.append(tag.getElement());
            });
        }
    };

    var create_relevance_tab = function(){
        relevance_tab = $('<a></a>');
        relevance_tab.attr('href', '?sort=relevance-desc');
        relevance_tab.attr('id', 'by_relevance');
        relevance_tab.html('<span>' + sortButtonData['relevance']['label'] + '</span>');
        return relevance_tab;
    }

    var set_active_sort_tab = function(sort_method){
        var tabs = $('#sort_tabs>a');
        tabs.attr('class', 'off');
        tabs.each(function(index, element){
            var tab = $(element);
            var tab_name = tab.attr('id').replace(/^by_/,'');
            if (tab_name in sortButtonData){
                tab.attr(
                    'href',
                    '?sort=' + tab_name + '-desc'
                );
                tab.attr(
                    'title',
                    sortButtonData[tab_name]['desc_tooltip']
                );
                tab.html(sortButtonData[tab_name]['label']);
            }
        });
        var bits = sort_method.split('-', 2);
        var name = bits[0];
        var sense = bits[1];//sense of sort
        var antisense = (sense == 'asc' ? 'desc':'asc');
        var arrow = (sense == 'asc' ? ' &#9650;':' &#9660;');
        var active_tab = $('#by_' + name);
        active_tab.attr('class', 'on');
        active_tab.attr('title', sortButtonData[name][antisense + '_tooltip']);
        active_tab.html(sortButtonData[name]['label'] + arrow);
    };

    var render_relevance_sort_tab = function(){
        if (showSortByRelevance === false){
            return;
        }
        var relevance_tab = $('#by_relevance');
        if (prev_text && prev_text.length > 0){
            if (relevance_tab.length == 0){
                relevance_tab = create_relevance_tab();
                $('#sort_tabs>span').after(relevance_tab);
            }
        }
        else {
            if (relevance_tab.length > 0){
                relevance_tab.remove();
            }
        }
    };

    var change_rss_url = function(feed_url){
        if(feed_url){
            $("#ContentLeft a.rss:first").attr("href", feed_url);
        }
    }

    var remove_search_tag = function(tag_name){
        $.ajax({
            url: askbot['urls']['questions'],
            data: {remove_tag: tag_name},
            dataType: 'json',
            success: render_result,
            complete: try_again
        });
    };

    var activate_search_tags = function(){
        var search_tags = $('#searchTags .tag-left');
        $.each(search_tags, function(idx, element){
            var tag = new Tag();
            tag.decorate($(element));
            //todo: setDeleteHandler and setHandler
            //must work after decorate & must have getName
            tag.setDeleteHandler(
                function(){
                    remove_search_tag(tag.getName());
                }
            );
        });
    };

    var render_ask_page_result = function(data, text_status, xhr){
        var container = $('#' + q_list_sel);
        container.fadeOut(200, function() {
            container.children().remove();
            $.each(data, function(idx, question){
                var url = question['url'];
                var title = question['title'];
                var answer_count = question['answer_count'];
                var list_item = $('<h2></h2>');
                var count_element = $('<span class="item-count"></span>');
                count_element.html(answer_count);
                list_item.append(count_element);
                var link = $('<a></a>');
                link.attr('href', url);
                list_item.append(link);
                title_element = $('<span class="title"></span>');
                title_element.html(title);
                link.append(title)
                container.append(list_item);
            });
            container.show();//show just to measure
            var unit_height = container.children(':first').outerHeight();
            container.hide();//now hide
            if (data.length > 5){
                container.css('overflow-y', 'scroll');
                container.css('height', unit_height*5 + 'px');
            } else {
                container.css('height', data.length*unit_height + 'px');
                container.css('overflow-y', 'hidden');
            }
            container.fadeIn();
        });
    };

    var render_main_page_result = function(data, text_status, xhr){
        var old_list = $('#' + q_list_sel);
        var new_list = $('<div></div>').hide();
        if (data['questions'].length > 0){
            old_list.stop(true);

            new_list.html(data['questions']);
            //old_list.hide();
            old_list.after(new_list);
            //old_list.remove();
            //rename new div to old
            render_paginator(data['paginator']);
            set_question_count(data['question_counter']);
            render_search_tags(data['query_data']['tags']);
            render_faces(data['faces']);
            render_related_tags(data['related_tags']);
            render_relevance_sort_tab();
            change_rss_url(data['feed_url']);
            set_active_sort_tab(sortMethod);
            query.focus();

            //show new div with a fadeIn effect
            old_list.fadeOut(200, function() {
                old_list.remove();
                new_list.attr('id', q_list_sel);
                new_list.fadeIn(400);            
            });
        }
    }

    var try_again = function(){
        running = false;
        eval_query();
    }

    var send_query = function(query_text, sort_method){
        var post_data = {query: query_text};
        $.ajax({
            url: search_url,
            data: {query: query_text, sort: sort_method},
            dataType: 'json',
            success: render_result,
            complete: try_again
        });
        prev_text = query_text;
    }

    var reset_query = function(sort_method){
        $.ajax({
            url: search_url,
            data: {reset_query: true, sort: sort_method},
            dataType: 'json',
            success: render_result,
            complete: try_again
        });
        prev_text = '';
    }

    var refresh_main_page = function(){
        $.ajax({
            url: askbot['urls']['questions'],
            data: {preserve_state: true},
            dataType: 'json',
            success: render_main_page_result
        });
    };

    return {
        refresh: function(){
            query = $('input#keywords');
            refresh_main_page();
        },
        init: function(mode){
            if (mode === 'main_page'){
                //live search for the main page
                query = $('input#keywords');
                search_url = askbot['urls']['questions'];
                render_result = render_main_page_result;

                process_query = function(){
                    if (prev_text.length === 0 && showSortByRelevance){
                        if (sortMethod === 'activity-desc'){
                            prevSortMethod = sortMethod;
                            sortMethod = 'relevance-desc';
                        }
                    }
                    send_query(cur_text, sortMethod);
                };
                restart_query = function() {
                    reset_sort_method();
                    refresh_x_button();
                    reset_query(sortMethod);
                    running = true;
                };

                activate_search_tags();
                main_page_search_listen();
            } else {
                query = $('input#id_title.questionTitleInput');
                search_url = askbot['urls']['api_get_questions'];
                render_result = render_ask_page_result;
                process_query = function(){
                    send_query(cur_text);
                };
                restart_query = function(){
                    $('#' + q_list_sel).css('height',0).children().remove();
                    running = false;
                    prev_text = '';
                    //ask_page_search_listen();
                };
                ask_page_search_listen();
            }
            prev_text = $.trim(query.val());
            running = false;
        }
    };

};

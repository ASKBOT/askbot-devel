function initEditor(){
  $('#editor').TextAreaResizer();
  //highlight code synctax when editor has new text

  var display = true;
  var txt = gettext("hide preview");
  $('#pre-collapse').text(txt);
  $('#pre-collapse').bind('click', function(){
    txt = display ? gettext("show preview") : gettext("hide preview");
    display = !display;
    $('#previewer').toggle();
    $('#pre-collapse').text("[" + txt + "]");
  });
  var formElement = $('.js-answer-form');
  if (formElement.length) {
    var answerForm = new AnswerForm();
    answerForm.decorate(formElement);
  }
}

PostVote.init();

$(document).ready(function(){
  $("#js-answers-sort-" + askbot['data']['answersSortTab']).attr('class',"js-active");

  if (askbot['data']['threadIsClosed'] === false) {
    initEditor();
  }

  if (askbot['data']['userIsAuthenticated'] && askbot['data']['threadId']) {
    var draftHandler = new DraftAnswer();
    draftHandler.setThreadId(askbot['data']['threadId']);
    draftHandler.decorate($('body'));
  }

  var expanders = $('.js-expander');
  expanders.each(function(idx, item) {
    var expanderElement = $(item);
    var post = expanderElement.closest('.js-post,.js-comment');
    if (post.length === 1) {
      var expander = new PostExpander();
      expander.setPostId(post.data('postId'));
      expander.decorate(expanderElement);
    }
  });
});

function animate_hashes(){
  var id_value = window.location.hash;
  if (id_value != ""){
    var previous_color = $(id_value).css('background-color');
    $(id_value).css('backgroundColor', '#FFF8C6');
    $(id_value).animate({
      backgroundColor: '#ff7f2a'
    }, 1000).animate({backgroundColor: '#FFF8C6'}, 1000, function(){
      $(id_value).css('backgroundColor', previous_color);
    });
  }
}

$(window).bind('hashchange', animate_hashes);

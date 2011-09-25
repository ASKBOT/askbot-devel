$(document).ready(function() {
  function moderateIP() {
    var classes = $(this).attr('class').split(' ');
    var type = classes[1];
    var ip = classes[2];
    if (type == 'block')
      var new_type = 'unblock';
    else
      var new_type = 'block';

    $.ajax({
      type: 'POST',
      url: askbot['urls']['moderate_ip'],
      data: {'type':type, 'ip': ip},
      complete: function(data, status){
        if (status == 'error')
          return;
        $('span.moderate-ip.'+type).each(function(index){
          if ($(this).hasClass(ip)){
            $(this).attr('class', 'moderate-ip '+new_type+' '+ip).attr('title', new_type + ' IP '+ip).html('<a>'+new_type+' IP</a>');
          }
        });
      },
      error: function(data) {
        alert('There was an error during moderating this IP!');
      }
    });
  }

  $('span.moderate-ip').bind('click', moderateIP);
});

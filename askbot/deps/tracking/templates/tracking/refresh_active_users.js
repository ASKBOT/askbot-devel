var trackingUsers;
var refreshTimeout = 5000;

$(document).ready(function () {
    trackingUsers = $('#tracking-active-users');
    if (trackingUsers) {
        refreshActiveUsers();
    }
});

function refreshActiveUsers() {
    $.ajax({
        'url': updateActiveURL,
        'type': 'GET',
        'data': {},
        'dataType': 'json',
        'error': function (xhr, status, msg) {
            // do nothing
        },
        'success': function (json) {
            trackingUsers.html(json.users)
        }
    });

    setTimeout(refreshActiveUsers, refreshTimeout);
}
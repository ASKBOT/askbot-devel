/**
 * Askbot timeago customization
 */
(function($, gettext, ngettext, interpolate) {

    "use strict";

    var A_YEAR_IN_MILLIS = 365 * 24 * 60 * 60 * 1000,
        months = [
            gettext('Jan'),
            gettext('Feb'),
            gettext('Mar'),
            gettext('Apr'),
            gettext('May'),
            gettext('Jun'),
            gettext('Jul'),
            gettext('Aug'),
            gettext('Sep'),
            gettext('Oct'),
            gettext('Nov'),
            gettext('Dec')
        ],

        displayDate = function(nb, distanceMillis) {
            var date = new Date(new Date().getTime() - distanceMillis);
            var month_date = months[date.getMonth()] + ' ' + date.getDate()
            if (distanceMillis > A_YEAR_IN_MILLIS) {
                return month_date;
            } else {
                return month_date + ' ' + "'" + date.getYear() % 20;
            }
        },

        displayDays = function(days, distanceMillis) {
            switch(days) {
                case 2:
                    return gettext('2 days ago');
                case 1:
                    return gettext('yesterday');
                default:
                    return displayDate(days, distanceMillis);
            }
        },

        displayHours = function(hours) {
            return interpolate(
                ngettext('%s hour ago', '%s hours ago', hours),
                [hours,]
            )
        },

        displayMinutes = function(minutes) {
            return interpolate(
                ngettext('%s min ago', '%s mins ago', minutes),
                [minutes,]
            );
        }


    $.timeago.settings.strings = {
        prefixAgo: null,
        prefixFromNow: null,
        suffixAgo: null,
        suffixFromNow: null,
        seconds: gettext("just now"),
        minute: displayMinutes,
        minutes: displayMinutes,
        hour: displayHours,
        hours: displayHours,
        day: displayDays,
        days: displayDays,
        month: displayDate,
        months: displayDate,
        year: displayDate,
        years: displayDate,
        wordSeparator: "",
        numbers: []
    };

}(window.jQuery, window.gettext, window.ngettext, window.interpolate));

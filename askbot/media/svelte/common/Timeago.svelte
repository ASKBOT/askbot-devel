<script>
    let { timestamp } = $props();

    let display = $state('');

    function parse(iso8601) {
        var s = (iso8601 || '').trim();
        s = s.replace(/\.\d\d\d+/, '');
        s = s.replace(/-/, '/').replace(/-/, '/');
        s = s.replace(/T/, ' ').replace(/Z/, ' UTC');
        s = s.replace(/([\+\-]\d\d)\:?(\d\d)/, ' $1$2');
        return new Date(s);
    }

    function inWords(date) {
        var distanceMillis = new Date() - date;
        var seconds = Math.abs(distanceMillis) / 1000;
        var minutes = seconds / 60;
        var hours = minutes / 60;
        var days = hours / 24;
        var wholeYears = Math.floor(days / 365);
        var months = [
            gettext('Jan'), gettext('Feb'), gettext('Mar'),
            gettext('Apr'), gettext('May'), gettext('Jun'),
            gettext('Jul'), gettext('Aug'), gettext('Sep'),
            gettext('Oct'), gettext('Nov'), gettext('Dec')
        ];

        if (days > 2) {
            var month_date = months[date.getMonth()] + ' ' + date.getDate();
            if (wholeYears == 0) {
                return month_date;
            } else {
                return interpolate(ngettext('%s year ago', '%s years ago', wholeYears), [wholeYears]);
            }
        } else if (days >= 2) {
            return gettext('2 days ago');
        } else if (days >= 1) {
            return gettext('yesterday');
        } else if (minutes >= 60) {
            var wholeHours = Math.floor(hours);
            return interpolate(ngettext('%s hour ago', '%s hours ago', wholeHours), [wholeHours]);
        } else if (seconds > 90) {
            var wholeMinutes = Math.floor(minutes);
            return interpolate(ngettext('%s min ago', '%s mins ago', wholeMinutes), [wholeMinutes]);
        } else {
            return gettext('just now');
        }
    }

    function update() {
        var date = parse(timestamp);
        if (!isNaN(date)) {
            display = inWords(date);
        } else {
            display = timestamp;
        }
    }

    $effect(() => {
        update();
        var interval = setInterval(update, 60000);
        return () => clearInterval(interval);
    });
</script>

<span class="js-timeago" style="display: inline" title={timestamp}>{display}</span>

/**
 * Video modal player for video embeds.
 *
 * Opens a modal with an iframe video player when clicking on video links.
 * Extends ModalDialog without modifying the base class.
 *
 * Usage: Singleton is created and initialized automatically when videoEmbeddingEnabled is true.
 * Click handlers are delegated on $(document) for .js-video-link elements.
 */

var VideoModal = function() {
    ModalDialog.call(this);
    this._className = 'js-video-modal';
    this._headerEnabled = true;
    this._currentService = null;
    this._currentVideoId = null;
    this._iframeContainer = null;
};
inherits(VideoModal, ModalDialog);

/**
 * Video service configuration with embed URLs.
 */
VideoModal.VIDEO_SERVICES = {
    youtube: {
        url: 'https://www.youtube.com/embed/{0}'
    },
    vimeo: {
        url: 'https://player.vimeo.com/video/{0}'
    },
    dailymotion: {
        url: 'https://www.dailymotion.com/embed/video/{0}'
    }
};

/**
 * Open the modal with a specific video.
 * @param {string} service - Video service (youtube, vimeo, dailymotion)
 * @param {string} videoId - Video ID
 * @param {string} [title] - Optional video title
 */
VideoModal.prototype.openVideo = function(service, videoId, title) {
    this._currentService = service;
    this._currentVideoId = videoId;

    // Set heading
    var headingText = title || gettext('Video');
    this.setHeadingText(headingText);

    // Create iframe
    this._createIframe();

    // Show modal
    this.show();
};

/**
 * Create and insert the video iframe.
 */
VideoModal.prototype._createIframe = function() {
    var config = VideoModal.VIDEO_SERVICES[this._currentService];
    if (!config) return;

    var url = config.url.replace('{0}', this._currentVideoId);

    // Clear any existing iframe
    this._destroyIframe();

    // Create iframe element
    var iframe = $('<iframe></iframe>');
    iframe.attr({
        src: url,
        frameborder: '0',
        allowfullscreen: 'allowfullscreen',
        allow: 'autoplay; fullscreen'
    });

    // Insert into container
    if (this._iframeContainer) {
        this._iframeContainer.append(iframe);
    }
};

/**
 * Destroy the iframe to stop video playback and free memory.
 */
VideoModal.prototype._destroyIframe = function() {
    if (this._iframeContainer) {
        this._iframeContainer.empty();
    }
};

/**
 * Override hide to destroy iframe when closing.
 */
VideoModal.prototype.hide = function() {
    this._destroyIframe();
    this._currentService = null;
    this._currentVideoId = null;
    ModalDialog.prototype.hide.call(this);
};

/**
 * Create the modal DOM structure.
 * Overrides base createDom to remove footer buttons and add video container.
 */
VideoModal.prototype.createDom = function() {
    this._element = this.makeElement('div');
    var element = this._element;

    element.addClass('js-modal');
    element.addClass(this._className);

    // Header with title
    var header = this.makeElement('div');
    header.addClass('js-modal-header');
    element.append(header);

    var title = this.makeElement('h3');
    title.text(this._heading_text || gettext('Video'));
    header.append(title);
    this._title = title;

    var me = this;

    // Body with iframe container (no footer buttons needed)
    var body = this.makeElement('div');
    body.addClass('js-modal-body');
    element.append(body);

    var iframeWrapper = this.makeElement('div');
    iframeWrapper.addClass('js-video-modal-iframe-wrapper');
    body.append(iframeWrapper);

    this._iframeContainer = iframeWrapper;
    this._content_element = body;

    // Stop playback when modal is closed via backdrop click
    $(document).on($.modal.CLOSE, function() {
        me._destroyIframe();
    });

    this.hide();
    $(document).trigger('askbot.afterModalDialogCreateDom', [this]);
};


/**
 * Singleton instance and initialization.
 */
(function() {
    'use strict';

    var videoModalInstance = null;

    /**
     * Get or create the singleton VideoModal instance.
     * @returns {VideoModal}
     */
    function getVideoModal() {
        if (!videoModalInstance) {
            videoModalInstance = new VideoModal();
            videoModalInstance.createDom();
            $('body').append(videoModalInstance.getElement());
        }
        return videoModalInstance;
    }

    /**
     * Handle clicks on video links.
     * @param {Event} evt - Click event
     */
    function handleVideoLinkClick(evt) {
        evt.preventDefault();

        var link = $(evt.currentTarget);
        var service = link.data('video-service');
        var videoId = link.data('video-id');
        var title = link.data('video-title') || null;

        if (!service || !videoId) return;

        var modal = getVideoModal();
        modal.openVideo(service, videoId, title);
    }

    /**
     * Initialize video modal functionality.
     * Called when DOM is ready and videoEmbeddingEnabled is true.
     */
    function initVideoModal() {
        // Delegate click handler to document for dynamic content support
        // (works for both rendered posts and live preview)
        $(document).on('click', '.js-video-link', handleVideoLinkClick);
    }

    // Initialize when DOM is ready, if video embedding is enabled
    $(document).ready(function() {
        if (askbot && askbot.settings && askbot.settings.videoEmbeddingEnabled) {
            initVideoModal();
        }
    });

})();

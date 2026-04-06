import QtQuick
import QtQml
import QtWebView

Rectangle {
    id: root
    color: "#1a1a1a"

    WebView {
        id: webView
        objectName: "chatWebView"
        anchors.fill: parent

        onLoadingChanged: function(loadRequest) {
            if (loadRequest.status === WebView.LoadSucceededStatus) {
                bridge.notifyLoadSucceeded()
                return
            }
            if (loadRequest.status === WebView.LoadFailedStatus) {
                bridge.notifyLoadFailed(loadRequest.errorString || "Failed to load chat HTML.")
            }
        }

        onTitleChanged: function() {
            var prefix = "__babka_anchor__:"
            if (!title || title.indexOf(prefix) !== 0) {
                return
            }

            var payload = title.substring(prefix.length)
            var separator = payload.lastIndexOf("::")
            if (separator >= 0) {
                payload = payload.substring(0, separator)
            }

            bridge.notifyAnchor(payload)
            webView.runJavaScript("document.title = '';", function() {})
        }
    }

    Connections {
        target: bridge

        function onSetHtmlRequested(html) {
            webView.loadHtml(html, "https://chat.invalid/")
        }

        function onScrollRequested() {
            webView.runJavaScript(
                "window.scrollTo(0, document.body.scrollHeight);",
                function() {}
            )
        }
    }
}
